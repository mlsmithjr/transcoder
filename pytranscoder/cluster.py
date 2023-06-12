"""
    Cluster support
"""
import datetime
import os
import shutil
import signal
import subprocess
import sys
from pathlib import PureWindowsPath, PosixPath
from queue import Queue, Empty
import socket
from tempfile import gettempdir
from threading import Thread, Lock
from typing import Dict, List, Optional

import crayons

import pytranscoder

from pytranscoder import verbose
from pytranscoder.config import ConfigFile
from pytranscoder.ffmpeg import FFmpeg
from pytranscoder.media import MediaInfo
from pytranscoder.profile import Directives
from pytranscoder.utils import filter_threshold, get_local_os_type, calculate_progress, run


class RemoteHostProperties:
    name: str
    props: Dict

    def __init__(self, name: str, props: Dict):
        self.props = props
        self.name = name

    @property
    def user(self):
        return self.props['user']

    @property
    def ip(self):
        return self.props['ip']

    @property
    def os(self):
        return self.props['os']

    @property
    def profiles(self) -> List[str]:
        return self.props.get('profiles', None)

    @property
    def working_dir(self):
        return self.props.get('working_dir', None)

    @property
    def host_type(self):
        return self.props['type']

    @property
    def ffmpeg_path(self):
        return self.props.get('ffmpeg', None)

    @property
    def is_enabled(self):
        return self.props.get('status', 'enabled') == 'enabled'

    @property
    def has_path_subst(self):
        return 'path-substitutions' in self.props

    @property
    def queues(self) -> Dict:
        return self.props.get('queues', {'_default': 1})

    def substitute_paths(self, in_path, out_path):
        lst = self.props['path-substitutions']
        for item in lst:
            src, dest = item.split(' ')
            if src in in_path:
                in_path = in_path.replace(src, dest)
                out_path = out_path.replace(src, dest)
                break
        return in_path, out_path

    def is_windows(self):
        if self.props['type'] == 'local':
            return get_local_os_type() == 'win10'
        return self.props.get('os', None) == 'win10'

    def is_linux(self):
        if self.props['type'] == 'local':
            return get_local_os_type() == 'linux'
        return self.props.get('os', None) == 'linux'

    def escaped_filename(self, filename):
        """Find all special characters typically found in media names and escape to be shell-friendly"""
        if self.is_windows():
            return filename
        if self.is_linux():
            filename = filename.replace(r' ', r'\ ')
            filename = filename.replace(r'(', r'\(')
            filename = filename.replace(r')', r'\)')
            filename = filename.replace(r"'", r"\'")
            filename = filename.replace(r'"', r'\"')
            filename = filename.replace(r'!', r'\!')
            return "'" + filename + "'"
        return filename

    def validate_settings(self):
        """Validate required settings"""
        msg = list()
        'type' in self.props or msg.append(f'Missing "type"')
        'status' in self.props or msg.append(f'Missing "status"')
        if self.props['type'] in ['mounted', 'streaming']:
            'ip' in self.props or msg.append(f'Missing "ip"')
            'user' in self.props or msg.append(f'Missing "user"')
            'os' in self.props or msg.append(f'Missing "os"')
            if 'os' in self.props:
                _os = self.props['os']
                _os in ['macos', 'linux', 'win10'] or msg.append(f'Unsupported "os" type {_os}')
        if self.props['type'] == 'streaming':
            'working_dir' in self.props or msg.append(f'Missing "working_dir"')
        if len(msg) > 0:
            print(f'Validation error(s) for host {self.name}:')
            print('\n'.join(msg))
            return False
        return True


class EncodeJob:
    """One file to be encoded"""
    inpath: str
    media_info: MediaInfo
    directive_name: str

    def __init__(self, inpath: str, info: MediaInfo, directive: Directives, mixins: Optional[List[str]]):
        self.inpath = os.path.abspath(inpath)
        self.media_info = info
        self.directive = directive
        self.mixins = mixins

    def should_abort(self, pct_comp) -> bool:
        if self.directive.threshold_check() < 100:
            return self.directive.threshold_check() <= pct_comp < self.directive.threshold()
        return False


class ManagedHost(Thread):
    """
        Base thread class for all remote host types.
    """

    def __init__(self, hostname, props, queue, cluster):
        """
        :param hostname:    name of host from config/clusters
        :param props:       dictionary of properties from config/clusters
        :param queue:       Work queue assigned to this thread, could be many-to-one in the future.
        :param cluster:     Reference to parent Cluster object
        """
        super().__init__(name=hostname, group=None, daemon=True)
        self.hostname = hostname
        self.props = props
        self.queue = queue
        self._complete = list()
        self._manager = cluster
        self.ffmpeg = FFmpeg(props.ffmpeg_path)

    def validate_settings(self):
        return self.props.validate_settings()

    @property
    def lock(self):
        return self._manager.lock

    @property
    def configfile(self) -> ConfigFile:
        return self._manager.config

    def complete(self, source, elapsed=0):
        self._complete.append((source, elapsed))

    @property
    def completed(self) -> List:
        return self._complete

    def log(self, *args):
        self.lock.acquire()
        try:
            msg = crayons.blue(f'({self.hostname}): ')
            print(msg, *args)
            sys.stdout.flush()
        finally:
            self.lock.release()

    def testrun(self):
        pass

    def converted_path(self, path):
        if self.props.is_windows():
            path = '"' + path + '"'
            return str(PureWindowsPath(path))
        else:
            return str(PosixPath(path))

    def ssh_cmd(self):
        return [self._manager.ssh, self.props.user + '@' + self.props.ip]

    def ping_test_ok(self):
        addr = self.props.ip
        if os.name == "nt":
            ping = [r'C:\WINDOWS\system32\ping.exe', '-n', '1', '-w', '5', addr]
        else:
            ping = ['ping', '-c', '1', '-W', '5', addr]
        p = subprocess.Popen(ping, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        p.communicate()
        if p.returncode != 0:
            self.log(crayons.yellow(f'Host at address {addr} cannot be reached - skipped'))
            return False
        return True

    def ssh_test_ok(self):
        try:
            remote_cmd = 'dir' if self.props.is_windows() else 'ls'
            # remote_cmd = 'ls'
            sshtest = subprocess.run([*self.ssh_cmd(), remote_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     shell=False, timeout=10)
            if sshtest.returncode != 0:
                self.log('ssh test failed with the following output: ' + str(sshtest.stderr))
                return False
            return True
        except subprocess.TimeoutExpired:
            return False

    def host_ok(self):
        return self.ping_test_ok() and self.ssh_test_ok()

    def run_process(self, *args):
        p = subprocess.run(*args)
        if self._manager.verbose:
            self.log(' '.join(*args))
            if p.returncode != 0:
                self.log(p.stderr)
        return p

    # def match_profile(self, job: EncodeJob, name: str) -> Optional[Profile]:
    #     if job.directive_name is None:
    #         rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
    #         if rule is None:
    #             self.log(crayons.yellow(
    #                 f'Failed to match rule/profile for host {name} for file {job.inpath} - skipped'))
    #             return None
    #         job.directive_name = rule.profile
    #     return self._manager.profiles[job.directive_name]

    def terminate(self):
        pass


class AgentManagedHost(ManagedHost):
    """Implementation of a agent host worker thread"""

    def __init__(self, hostname, props: RemoteHostProperties, queue: Queue, cluster):
        super().__init__(hostname, props, queue, cluster)

    #
    # initiate tests through here to avoid a new thread
    #
    def testrun(self):
        self.go()

    #
    # normal threaded entry point
    #
    def run(self):
        if self.host_ok():
            self.go()
        else:
            self.log(f"{self.props.name} not available")

    def go(self):

        while not self.queue.empty():
            try:
                job: EncodeJob = self.queue.get()
                inpath = job.inpath

                #
                # build command line
                #

                remote_inpath = inpath

                stream_map = []
                if job.media_info.is_multistream() and self._manager.config.automap:
                    stream_map = job.directive.stream_map(job.media_info.stream, job.media_info.audio,
                                                          job.media_info.subtitle)

                cmd = [self.props.ffmpeg_path, '-y', *job.directive.input_options_list(), '-i', '{FILENAME}',
                       *job.directive.output_options_list(self._manager.config, job.mixins), *stream_map]

                #
                # display useful information
                #
                self.lock.acquire()
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (agent)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))
                    print(f'Directive: {job.directive.name()}')
                    print('Command  : ' + ' '.join(cmd) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                basename = os.path.basename(job.inpath)

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.media_info, stats)
                    pytranscoder.status_queue.put({'host': self.hostname,
                                                   'file': basename,
                                                   'speed': stats['speed'],
                                                   'comp': pct_comp,
                                                   'done': pct_done})

                    if job.should_abort(pct_done):
                        # compression goal (threshold) not met, kill the job and waste no more time...
                        self.log(f'Encoding of {basename} cancelled and skipped due to threshold not met')
                        return True
                    return False

                #
                # Send to agent
                #
                s = socket.socket()

                if self._manager.verbose:
                    self.log(f"connect to '{self.props.ip}'")

                s.connect((self.props.ip, 9567))
                inputsize = os.path.getsize(inpath)
                tmpdir = self.props.working_dir
                cmd_str = "$".join(cmd)
                hello = f"HELLO|{inputsize}|{tmpdir}|{basename}|{cmd_str}"
                if self._manager.verbose:
                    self.log("handshaking")
                s.send(bytes(hello.encode()))
                rsp = s.recv(1024).decode()
                if rsp != hello:
                    self.log("Received unexpected response from agent: " + rsp)
                    continue
                # send the file
                self.log(f"sending {inpath}")
                with open(inpath, "rb") as f:
                    while True:
                        buf = f.read(1_000_000)
                        s.send(buf)
                        if len(buf) < 1_000_000:
                            break

                job_start = datetime.datetime.now()
                finished, stats = self.ffmpeg.monitor_agent_ffmpeg(s, log_callback, self.ffmpeg.monitor_agent)
                job_stop = datetime.datetime.now()

                try:
                    if finished:
                        parts = stats.split(r"|")
                        if parts[0] == "DONE":
                            s.send(bytes("ACK!".encode()))
                            tag, exitcode, sfilesize = parts
                            filesize = int(sfilesize)
                            tmpfile = inpath + ".tmp"
                            if self._manager.verbose:
                                self.log(f"receiving results ({filesize} bytes)")

                            with open(tmpfile, "wb") as out:
                                while filesize > 0:
                                    blk = s.recv(1_000_000)
                                    out.write(blk)
                                    filesize -= len(blk)

                            if not pytranscoder.keep_source:
                                os.unlink(inpath)
                                os.rename(tmpfile, inpath)
                            self.log(crayons.green(f'Finished {inpath}'))
                        elif parts[0] == "ERR":
                            self.log(f"Agent returned process error code '{parts[1]}'")
                        else:
                            self.log(f"Unknown process code from agent: '{parts[0]}'")
                        self.complete(inpath, (job_stop - job_start).seconds)

                except KeyboardInterrupt:
                    s.send(bytes("STOP".encode()))

            except Exception as ex:
                self.log(ex)
            finally:
                self.queue.task_done()

    def host_ok(self):
        s = socket.socket()
        s.connect((self.props.ip, 9567))
        s.send(bytes("PING".encode()))
        s.settimeout(5)
        try:
            results = s.recv(4)
            return results == "PONG"
        except Exception:
            return False


class StreamingManagedHost(ManagedHost):
    """Implementation of a streaming host worker thread"""

    def __init__(self, hostname, props: RemoteHostProperties, queue: Queue, cluster):
        super().__init__(hostname, props, queue, cluster)

    #
    # initiate tests through here to avoid a new thread
    #
    def testrun(self):
        self.go()

    #
    # normal threaded entry point
    #
    def run(self):
        if self.host_ok():
            self.go()

    def go(self):

        ssh_cmd = [self._manager.ssh, self.props.user + '@' + self.props.ip]

        #
        # Keep pulling items from the queue until done. Other threads will be pulling from the same queue
        # if multiple hosts configured on the same cluster.
        #
        while not self.queue.empty():
            try:
                job: EncodeJob = self.queue.get()
                inpath = job.inpath

                #
                # Convert escaped spaces back to normal. Typical for bash to escape spaces and special characters
                # in filenames.
                #
                inpath = inpath.replace('\\ ', ' ')

                #
                # calculate full input and output paths
                #
                remote_working_dir = self.props.working_dir
                remote_inpath = os.path.join(remote_working_dir, os.path.basename(inpath))
                remote_outpath = os.path.join(remote_working_dir, os.path.basename(inpath) + '.tmp')

                #
                # build remote commandline
                #
                stream_map = []
                if job.media_info.is_multistream() and self._manager.config.automap:
                    stream_map = job.directive.stream_map(job.media_info.stream, job.media_info.audio,
                                                          job.media_info.subtitle)

                cmd = ['-y', *job.directive.input_options_list(), '-i', self.converted_path(remote_inpath),
                       *job.directive.output_options_list(self._manager.config, job.mixins), *stream_map,
                       self.converted_path(remote_outpath)]
                cli = [*ssh_cmd, *cmd]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (streaming)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))
                    print(f'Directive: {job.directive.name()}')
                    print('ssh      : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                #
                # Copy source file to remote
                #
                target_dir = remote_working_dir
                if self.props.is_windows():
                    # trick to make scp work on the Windows side
                    target_dir = '/' + remote_working_dir

                scp = ['scp', inpath, self.props.user + '@' + self.props.ip + ':' + target_dir]
                self.log(' '.join(scp))

                code, output = run(scp)
                if code != 0:
                    self.log(crayons.red('Unknown error copying source to remote - media skipped'))
                    if self._manager.verbose:
                        self.log(output)
                    continue

                basename = os.path.basename(job.inpath)

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.media_info, stats)
                    pytranscoder.status_queue.put({'host': self.hostname,
                                                   'file': basename,
                                                   'speed': stats['speed'],
                                                   'comp': pct_comp,
                                                   'done': pct_done})
                    if job.should_abort(pct_done):
                        # compression goal (threshold) not met, kill the job and waste no more time...
                        self.log(f'Encoding of {basename} cancelled and skipped due to threshold not met')
                        return True
                    return False

                #
                # Start remote
                #
                job_start = datetime.datetime.now()
                code = self.ffmpeg.run_remote(self._manager.ssh, self.props.user, self.props.ip, cmd, log_callback)
                job_stop = datetime.datetime.now()

                #                if code != 0:
                #                    self.log(crayons.red('Unknown error encoding on remote'))
                #                    continue

                #
                # copy results back to local
                #
                retrieved_copy_name = os.path.join(gettempdir(), os.path.basename(remote_outpath))
                cmd = ['scp', self.props.user + '@' + self.props.ip + ':' + remote_outpath, retrieved_copy_name]
                self.log(' '.join(cmd))

                code, output = run(cmd)

                #
                # process completed, check results and finish
                #
                if code is None:
                    # was vetoed by threshold checker, clean up
                    self.complete(inpath, (job_stop - job_start).seconds)
                    os.remove(retrieved_copy_name)
                    continue

                if code == 0:
                    if not filter_threshold(job.directive, inpath, retrieved_copy_name):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath, (job_stop - job_start).seconds)
                        os.remove(retrieved_copy_name)
                        continue
                    self.complete(inpath, (job_stop - job_start).seconds)

                    if not pytranscoder.keep_source:
                        os.rename(retrieved_copy_name, retrieved_copy_name[0:-4])
                        retrieved_copy_name = retrieved_copy_name[0:-4]
                        if verbose:
                            self.log(f'moving media to {inpath}')
                        shutil.move(retrieved_copy_name, inpath)
                    self.log(crayons.green(f'Finished {inpath}'))
                elif code is not None:
                    self.log(crayons.red(f'error during remote transcode of {inpath}'))
                    self.log(f' Did not complete normally: {self.ffmpeg.last_command}')
                    self.log(f'Output can be found in {self.ffmpeg.log_path}')

                # self.log(f'Removing temporary media copies from {remote_working_dir}')
                if self.props.is_windows():
                    #                    remote_outpath = self.converted_path(remote_outpath)
                    #                    remote_inpath = self.converted_path(remote_inpath)
                    remote_outpath = remote_outpath.replace("/", "\\")
                    remote_inpath = remote_inpath.replace("/", "\\")
                    if get_local_os_type() == "linux":
                        remote_outpath = remote_outpath.replace(r"\\", "\\")
                        remote_inpath = remote_inpath.replace(r"\\", "\\")
                    self.run_process([*ssh_cmd, f'del "{remote_outpath}"'])
                else:
                    self.run_process([*ssh_cmd, f'"rm {remote_outpath}"'])

            finally:
                self.queue.task_done()


class MountedManagedHost(ManagedHost):
    """Implementation of a mounted host worker thread"""

    def __init__(self, hostname, props: RemoteHostProperties, queue: Queue, cluster):
        super().__init__(hostname, props, queue, cluster)

    #
    # initiate tests through here to avoid a new thread
    #
    def testrun(self):
        self.go()

    #
    # normal threaded entry point
    #
    def run(self):
        if self.host_ok():
            self.go()

    def go(self):

        while not self.queue.empty():
            try:
                job: EncodeJob = self.queue.get()
                inpath = job.inpath

                #
                # calculate paths
                #
                outpath = inpath[0:inpath.rfind('.')] + job.directive.extension() + '.tmp'
                remote_inpath = inpath
                remote_outpath = outpath
                if self.props.has_path_subst:
                    #
                    # fix the input path to match what the remote machine expects
                    #
                    remote_inpath, remote_outpath = self.props.substitute_paths(inpath, outpath)

                #
                # build command line
                #
                remote_inpath = self.converted_path(remote_inpath)
                remote_outpath = self.converted_path(remote_outpath)

                stream_map = []
                if job.media_info.is_multistream() and self._manager.config.automap:
                    stream_map = job.directive.stream_map(job.media_info.stream, job.media_info.audio,
                                                          job.media_info.subtitle)
                cmd = ['-y', *job.directive.input_options_list(), '-i', f'"{remote_inpath}"',
                       *job.directive.output_options_list(self._manager.config, job.mixins), *stream_map,
                       f'"{remote_outpath}"']

                #
                # display useful information
                #
                self.lock.acquire()
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (mounted)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))

                    print(f'Directive: {job.directive.name()}')
                    print('ssh      : ' + ' '.join(cmd) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                basename = os.path.basename(job.inpath)

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.media_info, stats)
                    pytranscoder.status_queue.put({'host': self.hostname,
                                                   'file': basename,
                                                   'speed': stats['speed'],
                                                   'comp': pct_comp,
                                                   'done': pct_done})

                    if job.should_abort(pct_done):
                        # compression goal (threshold) not met, kill the job and waste no more time...
                        self.log(f'Encoding of {basename} cancelled and skipped due to threshold not met')
                        return True
                    return False

                #
                # Start remote
                #
                job_start = datetime.datetime.now()
                code = self.ffmpeg.run_remote(self._manager.ssh, self.props.user, self.props.ip, cmd, log_callback)
                job_stop = datetime.datetime.now()

                #
                # process completed, check results and finish
                #
                if code is None:
                    # was vetoed by threshold checker, clean up
                    self.complete(inpath, (job_stop - job_start).seconds)
                    os.remove(outpath)
                    continue

                if code == 0:
                    if not filter_threshold(job.directive, inpath, outpath):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath, (job_stop - job_start).seconds)
                        os.remove(outpath)
                        continue

                    if not pytranscoder.keep_source:
                        if verbose:
                            self.log('removing ' + inpath)
                        os.remove(inpath)
                        if verbose:
                            self.log('renaming ' + outpath)
                        os.rename(outpath, outpath[0:-4])
                        self.complete(inpath, (job_stop - job_start).seconds)
                    self.log(crayons.green(f'Finished {job.inpath}'))
                elif code is not None:
                    self.log(f'Did not complete normally: {self.ffmpeg.last_command}')
                    self.log(f'Output can be found in {self.ffmpeg.log_path}')
                    try:
                        os.remove(outpath)
                    except:
                        pass

            except Exception as ex:
                self.log(ex)
            finally:
                self.queue.task_done()


class LocalHost(ManagedHost):
    """Implementation of a worker thread when the local machine is in the same cluster.
    Pretty much the same as the LocalHost class but without multiple dedicated queues"""

    def __init__(self, hostname, props: RemoteHostProperties, queue: Queue, cluster):
        super().__init__(hostname, props, queue, cluster)

    #
    # initiate tests through here to avoid a new thread
    #
    def testrun(self):
        self.go()

    #
    # normal threaded entry point
    #
    def run(self):
        self.go()

    def go(self):

        while not self.queue.empty():
            try:
                job: EncodeJob = self.queue.get()
                inpath = job.inpath

                #
                # calculate paths
                #
                outpath = inpath[0:inpath.rfind('.')] + job.directive.extension() + '.tmp'

                #
                # build command line
                #
                remote_inpath = self.converted_path(inpath)
                remote_outpath = self.converted_path(outpath)

                stream_map = []
                if job.media_info.is_multistream() and self._manager.config.automap:
                    stream_map = job.directive.stream_map(job.media_info.stream, job.media_info.audio,
                                                          job.media_info.subtitle)
                cli = ['-y', *job.directive.input_options_list(), '-i', remote_inpath,
                       *job.directive.output_options_list(self._manager.config, job.mixins), *stream_map,
                       remote_outpath]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (local)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))
                    print(f'Directive: {job.directive.name()}')
                    print('ffmpeg   : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                basename = os.path.basename(job.inpath)

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.media_info, stats)
                    pytranscoder.status_queue.put({'host': 'local',
                                                   'file': basename,
                                                   'speed': stats['speed'],
                                                   'comp': pct_comp,
                                                   'done': pct_done})

                    if job.should_abort(pct_done):
                        # compression goal (threshold) not met, kill the job and waste no more time...
                        self.log(f'Encoding of {basename} cancelled and skipped due to threshold not met')
                        return True
                    return False

                #
                # Start process
                #
                job_start = datetime.datetime.now()
                code = self.ffmpeg.run(cli, log_callback)
                job_stop = datetime.datetime.now()

                #
                # process completed, check results and finish
                #
                if code is None:
                    # was vetoed by threshold checker, clean up
                    self.complete(inpath, (job_stop - job_start).seconds)
                    os.remove(outpath)
                    continue

                if code == 0:
                    if not filter_threshold(job.directive, inpath, outpath):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath, (job_stop - job_start).seconds)
                        os.remove(outpath)
                        continue

                    if not pytranscoder.keep_source:
                        if verbose:
                            self.log('removing ' + inpath)
                        os.remove(inpath)
                        if verbose:
                            self.log('renaming ' + outpath)
                        os.rename(outpath, outpath[0:-4])
                        self.complete(inpath, (job_stop - job_start).seconds)
                    self.log(crayons.green(f'Finished {job.inpath}'))
                elif code is not None:
                    self.log(f' Did not complete normally: {self.ffmpeg.last_command}')
                    self.log(f'Output can be found in {self.ffmpeg.log_path}')
                    try:
                        os.remove(outpath)
                    except:
                        pass

            except Exception as ex:
                self.log(ex)
            finally:
                self.queue.task_done()


class Cluster(Thread):
    """Thread to create host threads and wait for their completion."""

    terminal_lock: Lock = Lock()  # class-level

    def __init__(self, name, configs: Dict, config: ConfigFile, ssh: str):
        """
        :param name:        Cluster name, used only for thread naming
        :param configs:     The "clusters" section of the global config
        :param config:      The full configuration object
        :param ssh:         Path to local ssh
        """
        super().__init__(name=name, group=None, daemon=True)
        self.queues: Dict[str, Queue] = dict()
        self.ssh = ssh
        self.hosts: List[ManagedHost] = list()
        self.config = config
        self.verbose = verbose
        self.ffmpeg = FFmpeg(config.ffmpeg_path)
        self.lock = Cluster.terminal_lock
        self.completed: List = list()

        for host, props in configs.items():
            hostprops = RemoteHostProperties(host, props)
            if not hostprops.is_enabled:
                continue
            hosttype = hostprops.host_type

            #
            # make sure Queue exists for name
            #
            host_queues: Dict = hostprops.queues
            if len(host_queues) > 0:
                for host_queue in host_queues:
                    if host_queue not in self.queues:
                        self.queues[host_queue] = Queue()

            _h = None
            if hosttype == 'local':
                # special case - using pytranscoder host also as cluster host
                for host_queue, slots in host_queues.items():
                    #
                    # for each queue configured for this host create a dedicated thread for each slot
                    #
                    for slot in range(0, slots):
                        _h = LocalHost(host, hostprops, self.queues[host_queue], self)
                        if not _h.validate_settings():
                            sys.exit(1)
                        self.hosts.append(_h)

            elif hosttype == 'mounted':
                for host_queue, slots in host_queues.items():
                    #
                    # for each queue configured for this host create a dedicated thread for each slot
                    #
                    for slot in range(0, slots):
                        _h = MountedManagedHost(host, hostprops, self.queues[host_queue], self)
                        if not _h.validate_settings():
                            sys.exit(1)
                        self.hosts.append(_h)

            elif hosttype == 'streaming':
                for host_queue, slots in host_queues.items():
                    #
                    # for each queue configured for this host create a dedicated thread for each slot
                    #
                    for slot in range(0, slots):
                        _h = StreamingManagedHost(host, hostprops, self.queues[host_queue], self)
                        if not _h.validate_settings():
                            sys.exit(1)
                        self.hosts.append(_h)

            elif hosttype == 'agent':
                for host_queue, slots in host_queues.items():
                    #
                    # for each queue configured for this host create a dedicated thread for each slot
                    #
                    for slot in range(0, slots):
                        _h = AgentManagedHost(host, hostprops, self.queues[host_queue], self)
                        if not _h.validate_settings():
                            sys.exit(1)
                        self.hosts.append(_h)

            else:
                print(crayons.red(f'Unknown cluster host type "{hosttype}" - skipping'))

    def enqueue(self, file, forced_directive: Optional[str]):
        """Add a media file to this cluster queue.
           This is different than in local mode in that we only care about handling skips here.
           The profile will be selected once a host is assigned to the work
        """

        path = os.path.abspath(file)  # convert to full path so that rule filtering can work
        if pytranscoder.verbose:
            print('matching ' + path)

        media_info = self.ffmpeg.fetch_details(path)

        if media_info is None:
            print(crayons.red(f'File not found: {path}'))
            return None, None
        if media_info.valid:
            directive = None

            if pytranscoder.verbose:
                print(str(media_info))

            if forced_directive is None:
                #
                # just interested in SKIP rule matches and queue designations here
                #

                rule = self.config.match_rule(media_info)
                if rule is None:
                    print(crayons.yellow(f'No matching profile found - skipped'))
                    return None, None
                if rule.is_skip():
                    basename = os.path.basename(path)
                    print(f'{basename}: Skipping due to profile rule - {rule.name}')
                    return None, None
                directive = self.directives[rule.profile]
            else:
                if forced_directive in self.directives:
                    directive = self.directives[forced_directive]
                else:
                    print(f"{forced_directive} not found")
                    return None, None

            if pytranscoder.verbose:
                print(f"Matched to profile {directive.name()}")

            # not short circuited by a skip rule, add to appropriate queue
            queue_name = directive.queue_name() if directive.queue_name() is not None else '_default'
            if queue_name not in self.queues:
                print(crayons.red('Error: ') +
                      f'Queue "{queue_name}" referenced in "{directive.name()}" not defined in any host')
                exit(1)
            job = EncodeJob(file, media_info, directive, None)
            self.queues[queue_name].put(job)
            return queue_name, job
        return None, None

    def testrun(self):
        for host in self.hosts:
            host.testrun()

    def run(self):
        """Start all host threads and wait until queue is drained"""

        if len(self.hosts) == 0:
            print(f'No hosts available in cluster "{self.name}"')
            return

        for host in self.hosts:
            host.start()

        # all hosts running, wait for them to finish
        for host in self.hosts:
            host.join()
            self.completed.extend(host.completed)

    def terminate(self):
        for host in self.hosts:
            host.terminate()

    @property
    def directives(self):
        return self.config.directives


def manage_clusters(files, config: ConfigFile, testing=False) -> List:
    """Main entry point for setup and execution of all clusters

        There is one thread per cluster, and each cluster manages multiple hosts, each having their own thread.
    """
    completed = list()

    cluster_config = config.settings.get('clusters', None)
    if cluster_config is None:
        print('Error: no clusters defined')
        return completed
    clusters = dict()
    for name, this_config in cluster_config.items():
        for item in files:
            filepath, target_cluster, profile_name, mixins = item
            if target_cluster != name:
                continue
            if target_cluster not in clusters:
                clusters[target_cluster] = Cluster(target_cluster, this_config, config,
                                                   config.ssh_path)
            clusters[target_cluster].enqueue(filepath, profile_name)

    #
    # Start clusters, which will start hosts too
    #
    for _, cluster in clusters.items():
        if testing:
            cluster.testrun()
        else:
            cluster.start()

    def sig_handler(signal, frame):
        for _, acluster in clusters.items():
            if acluster.is_alive():
                acluster.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)

    if not testing:

        busy = True
        while busy:
            try:
                report = pytranscoder.status_queue.get(block=True, timeout=2)
                host = report['host']
                basename = report['file']
                speed = report['speed']
                comp = report['comp']
                done = report['done']
                print(f'{host:20}|{basename}: speed: {speed}x, comp: {comp}%, done: {done:3}%')
                sys.stdout.flush()
                pytranscoder.status_queue.task_done()
            except Empty:
                busy = False
                for _, cluster in clusters.items():
                    if cluster.is_alive():
                        busy = True

        #
        # wait for each cluster thread to complete
        #
    #        for _, cluster in clusters.items():
    #            cluster.join()
    #            completed.extend(cluster.completed)
    return completed
