"""
    Cluster support
"""
import os
import shutil
import subprocess
import sys
from pathlib import PureWindowsPath, PosixPath
from queue import Queue
from tempfile import gettempdir
from threading import Thread, Lock
from typing import Dict, List, Optional

import crayons

import pytranscoder

from pytranscoder import verbose
from pytranscoder.config import ConfigFile
from pytranscoder.ffmpeg import FFmpeg
from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile
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
    def profiles(self) -> [str]:
        return self.props.get('profiles', None)

    @property
    def working_dir(self):
        return self.props.get('working_dir', None)

    @property
    def host_type(self):
        return self.props['type']

    @property
    def ffmpeg_path(self):
        return self.props['ffmpeg']

    @property
    def is_enabled(self):
        return self.props.get('status', 'enabled') == 'enabled'

    @property
    def has_path_subst(self):
        return 'path-substitutions' in self.props

    @property
    def queues(self) -> Dict:
        return self.props.get('queues', {'_default': 1})

    def substitute_paths(self, in_path, out_path) -> (str, str):
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
    inpath:     str
    media_info: MediaInfo
    profile_name: str

    def __init__(self, inpath: str, info: MediaInfo, profile_name: str):
        self.inpath = os.path.abspath(inpath)
        self.media_info = info
        self.profile_name = profile_name


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
        self._complete = set()
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

    def complete(self, source):
        self._complete.add(source)

    def log(self, *args):
        self.lock.acquire()
        try:
            #msg = crayons.blue(f'[{self._manager.name}]') + crayons.white(f'({self.hostname}): ')
            msg = crayons.blue(f'({self.hostname}): ')
            print(msg, *args)
            sys.stdout.flush()
        finally:
            self.lock.release()

    def testrun(self):
        pass

    def converted_path(self, path):
        if self.props.is_windows():
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
        remote_cmd = 'dir' if self.props.is_windows() else 'ls'
        sshtest = subprocess.run([*self.ssh_cmd(), remote_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 shell=False, timeout=5)
        if sshtest.returncode != 0:
            self.log('ssh test failed with the following output: ' + sshtest.stderr)
            return False
        return True

    def host_ok(self):
        return self.ping_test_ok() and self.ssh_test_ok()

    def run_process(self, *args):
        p = subprocess.run(*args)
        if self._manager.verbose:
            self.log(' '.join(*args))
            if p.returncode != 0:
                self.log(p.stderr)
        return p


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
                # Got to do the rule matching again.
                # This time we narrow down the available profiles based on host definition
                #
                if job.profile_name is None:
                    if pytranscoder.verbose:
                        self.log('matching ' + inpath)
                    rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
                    if rule is None:
                        self.log(crayons.yellow(
                            f'Failed to match rule/profile for host {self.name} for file {inpath} - skipped'))
                        continue
                    job.profile_name = rule.profile
                _profile: Profile = self._manager.profiles[job.profile_name]

                #
                # calculate full input and output paths
                #
                remote_working_dir = self.props.working_dir
                remote_inpath = os.path.join(remote_working_dir, os.path.basename(inpath))
                remote_outpath = os.path.join(remote_working_dir, os.path.basename(inpath) + '.tmp')

                #
                # build remote ffmpeg commandline
                #
                oinput = _profile.input_options
                ooutput = _profile.output_options
#                quiet = ['-nostats', '-hide_banner']

                if job.media_info.is_multistream() and self.configfile.automap and _profile.automap:
                    ooutput = ooutput + job.media_info.ffmpeg_streams()

                cmd = ['-y', *oinput, '-i', self.converted_path(remote_inpath),
                       *ooutput, self.converted_path(remote_outpath)]
                cli = [*ssh_cmd, *cmd]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (streaming)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))
                    print(f'Profile  : {job.profile_name}')
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
                    self.log(f'{basename}: speed: {stats["speed"]}x, comp: {pct_comp}%, done: {pct_done:3}%')
                    if _profile.threshold_check < 100:
                        if pct_done >= _profile.threshold_check and pct_comp < _profile.threshold:
                            # compression goal (threshold) not met, kill the job and waste no more time...
                            self.log('Encoding of {basename} cancelled and skipped due to threshold not met')
                            return True
                    # continue
                    return False

                #
                # Start remote ffmpeg
                #
                code = self.ffmpeg.run_remote(self._manager.ssh, self.props.user, self.props.ip, cmd, log_callback)

                if code != 0:
                    self.log(crayons.red('Unknown error encoding on remote'))
                    continue

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
                if code == 0:
                    if not filter_threshold(_profile, inpath, retrieved_copy_name):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath)
                        os.remove(retrieved_copy_name)
                        continue
                    self.complete(inpath)

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
                    remote_outpath = self.converted_path(remote_outpath)
                    remote_inpath = self.converted_path(remote_inpath)
                    self.run_process([*ssh_cmd, f'"del {remote_outpath}"'])
                    self.run_process([*ssh_cmd, f'"del {remote_inpath}"'])
                else:
                    self.run_process([*ssh_cmd, f'"rm {remote_outpath}"'])
                    self.run_process([*ssh_cmd, f'"rm {remote_inpath}"'])

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
                # Got to do the rule matching again.
                # This time we narrow down the available profiles based on host definition
                #
                if pytranscoder.verbose:
                    self.log('matching ' + inpath)

                if job.profile_name is None:
                    rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
                    if rule is None:
                        self.log(crayons.yellow(
                            f'Failed to match rule/profile for host {self.name} for file {inpath} - skipped'))
                        continue
                    job.profile_name = rule.profile
                _profile: Profile = self._manager.profiles[job.profile_name]

                #
                # calculate paths
                #
                outpath = inpath[0:inpath.rfind('.')] + _profile.extension + '.tmp'
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
                oinput = _profile.input_options
                ooutput = _profile.output_options
#                quiet = ['-nostats', '-hide_banner']

                remote_inpath = self.converted_path(remote_inpath)
                remote_outpath = self.converted_path(remote_outpath)

                if job.media_info.is_multistream() and self.configfile.automap and _profile.automap:
                    ooutput = ooutput + job.media_info.ffmpeg_streams()
                cmd = ['-y', *oinput, '-i', f'"{remote_inpath}"', *ooutput, f'"{remote_outpath}"']

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (mounted)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))
                    print(f'Profile  : {_profile.name}')
                    print('ffmeg    : ' + ' '.join(cmd) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                basename = os.path.basename(job.inpath)

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.media_info, stats)
                    self.log(f'{basename}: speed: {stats["speed"]}x, comp: {pct_comp}%, done: {pct_done:3}%')
                    if _profile.threshold_check < 100:
                        if pct_done >= _profile.threshold_check and pct_comp < _profile.threshold:
                            # compression goal (threshold) not met, kill the job and waste no more time...
                            self.log('Encoding of {basename} cancelled and skipped due to threshold not met')
                            return True
                    # continue
                    return False

                #
                # Start remote ffmpeg
                #
                code = self.ffmpeg.run_remote(self._manager.ssh, self.props.user, self.props.ip, cmd, log_callback)

                #
                # process completed, check results and finish
                #
                if code == 0:
                    if not filter_threshold(_profile, inpath, outpath):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath)
                        os.remove(outpath)
                        continue

                    if not pytranscoder.keep_source:
                        if verbose:
                            self.log('removing ' + inpath)
                        os.remove(inpath)
                        if verbose:
                            self.log('renaming ' + outpath)
                        os.rename(outpath, outpath[0:-4])
                        self.complete(inpath)
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
                # Got to do the rule matching again.
                # This time we narrow down the available profiles based on host definition
                #
                if pytranscoder.verbose:
                    self.log('matching ' + inpath)

                if job.profile_name is None:
                    rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
                    if rule is None:
                        self.log(crayons.yellow(
                            f'Failed to match rule/profile for host {self.name} for file {inpath} - skipped'))
                        continue
                    job.profile_name = rule.profile
                _profile: Profile = self._manager.profiles[job.profile_name]

                #
                # calculate paths
                #
                outpath = inpath[0:inpath.rfind('.')] + _profile.extension + '.tmp'

                #
                # build command line
                #
                oinput = _profile.input_options
                ooutput = _profile.output_options
#                quiet = ['-nostats', '-hide_banner']

                remote_inpath = self.converted_path(inpath)
                remote_outpath = self.converted_path(outpath)

                if job.media_info.is_multistream() and self.configfile.automap and _profile.automap:
                    ooutput = ooutput + job.media_info.ffmpeg_streams()
                cli = ['-y', *oinput, '-i', remote_inpath, *ooutput, remote_outpath]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (local)')
                    print('Filename : ' + crayons.green(os.path.basename(remote_inpath)))
                    print(f'Profile  : {_profile.name}')
                    print('ffmpeg   : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                basename = os.path.basename(job.inpath)

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.media_info, stats)
                    self.log(f'{basename}: speed: {stats["speed"]}x, comp: {pct_comp}%, done: {pct_done:3}%')
                    if _profile.threshold_check < 100:
                        if pct_done >= _profile.threshold_check and pct_comp < _profile.threshold:
                            # compression goal (threshold) not met, kill the job and waste no more time...
                            self.log('Encoding of {basename} cancelled and skipped due to threshold not met')
                            return True
                    # continue
                    return False

                #
                # Start ffmpeg
                #
                code = self.ffmpeg.run(cli, log_callback)

                #
                # process completed, check results and finish
                #
                if code == 0:
                    if not filter_threshold(_profile, inpath, outpath):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath)
                        os.remove(outpath)
                        continue

                    if not pytranscoder.keep_source:
                        if verbose:
                            self.log('removing ' + inpath)
                        os.remove(inpath)
                        if verbose:
                            self.log('renaming ' + outpath)
                        os.rename(outpath, outpath[0:-4])
                        self.complete(inpath)
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

    hosts:          List[ManagedHost]
    terminal_lock:  Lock = Lock()       # class-level

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
        self.hosts = list()
        self.config = config
        self.verbose = verbose
        self.ffmpeg = FFmpeg(config.ffmpeg_path)
        self.lock = Cluster.terminal_lock

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

            else:
                print(crayons.red(f'Unknown cluster host type "{hosttype}" - skipping'))

    def enqueue(self, file, profile_name: Optional[str]) -> (str, Optional[EncodeJob]):
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

            if profile_name is None:
                #
                # just interested in SKIP rule matches and queue designations here
                #
                rule = self.config.match_rule(media_info)
                if rule is None:
                    print(crayons.yellow(f'No matching profile found - skipped'))
                    return None, None
                if rule.is_skip():
                    print(f'Skipping due to profile rule: {rule.name}')
                    return None, None
                profile_name = rule.profile

            profile = self.profiles[profile_name]
            # not short circuited by a skip rule, add to appropriate queue
            queue_name = profile.queue_name if profile.queue_name is not None else '_default'
            if queue_name not in self.queues:
                print(crayons.red('Error: ') +
                      f'Queue "{queue_name}" referenced in profile "{profile.name}" not defined in any host')
                exit(1)
            job = EncodeJob(file, media_info, profile_name)
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

        # wait for queue to process
        # self.queue.join()

    @property
    def profiles(self):
        return self.config.profiles


def manage_clusters(files, config: ConfigFile, testing=False):
    """Main entry point for setup and execution of all clusters

        There is one thread per cluster, and each cluster manages multiple hosts, each having their own thread.
    """

    cluster_config = config.settings.get('clusters', None)
    if cluster_config is None:
        print('Error: no clusters defined')
        return
    clusters = dict()
    for name, this_config in cluster_config.items():
        for item in files:
            filepath, target_cluster, profile_name = item
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

    if not testing:
        #
        # wait for each cluster thread to complete
        #
        for _, cluster in clusters.items():
            cluster.join()
