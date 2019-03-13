"""
    Cluster support
"""

import os
import shutil
import subprocess
import sys
from queue import Queue
from threading import Thread, Lock
from typing import Dict, List, Set
from pathlib import Path, PureWindowsPath

import pytranscoder

from pytranscoder import verbose
from pytranscoder.config import ConfigFile
from pytranscoder.media import MediaInfo, fetch_details
from pytranscoder.profile import Profile
from pytranscoder.utils import filter_threshold, get_local_os_type, monitor_ffmpeg


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
        return 'path-substitution' in self.props and \
            'src' in self.props['path-substitution'] and \
            'dest' in self.props['path-substitution']

    @property
    def path_subst_src(self):
        return self.props['path-substitution']['src']

    @property
    def path_subst_dest(self):
        return self.props['path-substitution']['dest']

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
            _os = self.props['os']
            _os in ['macos', 'linux', 'win10'] or msg.append(f'Unsupported "os" type {_os}')
        if self.props['type'] == 'streaming':
            'working_dir' in self.props or msg.append(f'Missing "working_dir"')
        if len(msg) > 0:
            print(f'Validation error(s) for host {self.name}:')
            print('\n'.join(msg))
            return False
        return True


class RemoteJob:
    """One file to be encoded"""
    inpath:     str
    media_info: MediaInfo

    def __init__(self, inpath, info: MediaInfo):
        self.inpath = inpath
        self.media_info = info


class RemoteHost(Thread):
    """
        Base thread class for all remote host types.
    """

    hostname: str
    props: RemoteHostProperties
    queue: Queue
    _complete: Set
    _manager = None

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

    def validate_settings(self):
        return self.props.validate_settings()

    @property
    def lock(self):
        return self._manager.lock

    @property
    def configfile(self):
        return self._manager.config

    def complete(self, source):
        self._complete.add(source)

    def log(self, *args):
        self.lock.acquire()
        try:
            print(f'[{self._manager.name}]({self.hostname}): ', *args)
            sys.stdout.flush()
        finally:
            self.lock.release()

    def testrun(self):
        pass

    def converted_path(self, path):
        if self.props.is_windows():
            return str(PureWindowsPath(path))
        else:
            return str(Path(path))

    def ssh_cmd(self):
        return [self._manager.ssh, self.props.user + '@' + self.props.ip]

    def ping_test_ok(self):
        addr = self.props.ip
        ping = ['ping', '-c', '1', '-W', '5', addr]
        p = subprocess.Popen(ping, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        p.communicate()
        if p.returncode != 0:
            self.log(f'Host at address {addr} cannot be reached - skipped')
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


class StreamingRemoteHost(RemoteHost):
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
                job: RemoteJob = self.queue.get()
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
                inpath = os.path.abspath(inpath)
                if pytranscoder.verbose:
                    self.log('matching ' + inpath)
                rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
                if rule is None:
                    self.log(f'Failed to match rule/profile for host {self.name} for file {inpath} - skipped')
                    continue
                profile_name = rule.profile
                _profile: Profile = self._manager.profiles[profile_name]

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

                cmd = [self.props.ffmpeg_path, '-y', *oinput, '-i', self.converted_path(remote_inpath),
                       *ooutput, self.converted_path(remote_outpath)]
                cli = [*ssh_cmd, *cmd]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (streaming)')
                    print(f'Filename : {remote_inpath}')
                    print(f'Profile  : {profile_name}')
                    print('ssh      : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if self._manager.dry_run:
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
                p = subprocess.Popen(scp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
                output = p.communicate()[0].decode('utf-8')

                if p.returncode != 0:
                    self.log('Unknown error copying source to remote - media skipped')
                    if self._manager.verbose:
                        self.log(output)
                    continue

                #
                # run remote shell to ffmpeg
                #
                p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                     shell=False)
                for name, stats in monitor_ffmpeg(os.path.basename(job.inpath), p):
                    pct_done = int((stats['time'] / job.media_info.runtime) * 100)
                    self.log(f'{name}: {pct_done:3}%, speed: {stats["speed"]}x')

                if p.returncode != 0:
                    self.log('Unknown error encoding on remote')
                    if self._manager.verbose:
                        self.log(output)
                    continue

                #
                # copy results back to local
                #
#                self.log(f'Retrieving media from {working_dir} on host')
                retrieved_copy_name = os.path.join('/tmp', os.path.basename(remote_outpath))
                cmd = ['scp', self.props.user + '@' + self.props.ip + ':' + remote_outpath, retrieved_copy_name]
                self.log(' '.join(cmd))
                p = subprocess.Popen(cmd)
                p.wait()

                #
                # process completed, check results and finish
                #
                if p.returncode == 0:
                    if not filter_threshold(_profile, inpath, retrieved_copy_name):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath)
                        os.remove(retrieved_copy_name)
                        continue
                    self.complete(inpath)

                    os.rename(retrieved_copy_name, retrieved_copy_name[0:-4])
                    retrieved_copy_name = retrieved_copy_name[0:-4]
                    self.log(f'moving media to {inpath}')
                    shutil.move(retrieved_copy_name, inpath)
                else:
                    self.log(f'error during remote transcode of {inpath}')

                self.log(f'Removing temporary media copies from {remote_working_dir}')
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


class MountedRemoteHost(RemoteHost):
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
                job: RemoteJob = self.queue.get()
                inpath = job.inpath

                #
                # Got to do the rule matching again.
                # This time we narrow down the available profiles based on host definition
                #
                inpath = os.path.abspath(inpath)
                if pytranscoder.verbose:
                    self.log('matching ' + inpath)
                rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
                if rule is None:
                    self.log(f'Failed to match rule/profile for host {self.name} for file {inpath} - skipped')
                    continue
                profile_name = rule.profile
                _profile: Profile = self._manager.profiles[profile_name]

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
                    src = self.props.path_subst_src
                    dest = self.props.path_subst_dest
                    remote_inpath = inpath.replace(src, dest)
                    remote_outpath = outpath.replace(src, dest)

                #
                # build command line
                #
                oinput = _profile.input_options
                ooutput = _profile.output_options
#                quiet = ['-nostats', '-hide_banner']

                remote_inpath = self.converted_path(remote_inpath)
                remote_outpath = self.converted_path(remote_outpath)

                cmd = [self.props.ffmpeg_path, '-y', *oinput, '-i', f'"{remote_inpath}"',
                       *ooutput, f'"{remote_outpath}"']
                cli = [self._manager.ssh, self.props.user + '@' + self.props.ip, *cmd]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (mounted)')
                    print(f'Filename : {remote_inpath}')
                    print(f'Profile  : {_profile.name}')
                    print('ssh      : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if self._manager.dry_run:
                    continue

                #
                # Start remote ffmpeg
                #
                p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                     shell=False)
                for name, stats in monitor_ffmpeg(os.path.basename(job.inpath), p):
                    pct_done = int((stats['time'] / job.media_info.runtime) * 100)
                    self.log(f'{name}: {pct_done:3}%, speed: {stats["speed"]}x')
                #
                # process completed, check results and finish
                #
                if p.returncode == 0:
                    if not filter_threshold(_profile, inpath, outpath):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath)
                        os.remove(outpath)
                        continue
                    self.log('removing ' + inpath)
                    os.remove(inpath)
                    self.log('renaming ' + outpath)
                    os.rename(outpath, outpath[0:-4])
                    self.complete(inpath)
                else:
                    self.log(f'error during encode of {inpath}, .tmp file removed')
                    self.log(p.stdout.read())
                    os.remove(outpath)
            except Exception as ex:
                self.log(ex)
            finally:
                self.queue.task_done()


class ManagerHost(RemoteHost):
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
                job: RemoteJob = self.queue.get()
                inpath = job.inpath

                #
                # Got to do the rule matching again.
                # This time we narrow down the available profiles based on host definition
                #
                inpath = os.path.abspath(inpath)
                if pytranscoder.verbose:
                    self.log('matching ' + inpath)
                rule = self.configfile.match_rule(job.media_info, restrict_profiles=self.props.profiles)
                if rule is None:
                    self.log(f'Failed to match rule/profile for host {self.name} for file {inpath} - skipped')
                    continue
                profile_name = rule.profile
                _profile: Profile = self._manager.profiles[profile_name]

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

                cli = [self.props.ffmpeg_path, '-y', *oinput, '-i', remote_inpath,
                       *ooutput, remote_outpath]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (local)')
                    print(f'Filename : {remote_inpath}')
                    print(f'Profile  : {_profile.name}')
                    print('ssh      : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if self._manager.dry_run:
                    continue

                #
                # Start ffmpeg
                #
                p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                     shell=False)
                for name, stats in monitor_ffmpeg(os.path.basename(job.inpath), p):
                    pct_done = int((stats['time'] / job.media_info.runtime) * 100)
                    self.log(f'{name}: {pct_done:3}%, speed: {stats["speed"]}x')

                #
                # process completed, check results and finish
                #
                if p.returncode == 0:
                    if not filter_threshold(_profile, inpath, outpath):
                        self.log(
                            f'Transcoded file {inpath} did not meet minimum savings threshold, skipped')
                        self.complete(inpath)
                        os.remove(outpath)
                        continue
                    self.log('removing ' + inpath)
                    os.remove(inpath)
                    self.log('renaming ' + outpath)
                    os.rename(outpath, outpath[0:-4])
                    self.complete(inpath)
                else:
                    self.log(f'error during encode of {inpath}, .tmp file removed')
                    self.log(p.stdout.read())
                    os.remove(outpath)
            except Exception as ex:
                self.log(ex)
            finally:
                self.queue.task_done()


class Cluster(Thread):
    """Thread to create host threads and wait for their completion."""

    hosts:          List[RemoteHost]
    queue:          Queue
    terminal_lock:  Lock
    config:         ConfigFile
    ssh:            str
    lock:           Lock
    dry_run:        bool
    verbose:        bool

    def __init__(self, name, configs: Dict, config: ConfigFile, lock: Lock, ssh: str, dry_run: bool):
        """
        :param name:        Cluster name, used only for thread naming
        :param configs:     The "clusters" section of the global config
        :param config:      The full configuration object
        :param lock:        Lock used to synchronize terminal output only
        :param ssh:         Path to local ssh
        :param dry_run:     True or False, is this a dry run.
        """
        super().__init__(name=name, group=None, daemon=True)
        self.queue = Queue()
        self.terminal_lock = lock
        self.dry_run = dry_run
        self.ssh = ssh
        self.lock = lock
        self.hosts = list()
        self.config = config
        self.verbose = verbose
        for host, props in configs.items():
            hostprops = RemoteHostProperties(host, props)
            if not hostprops.is_enabled:
                print(f'Host {host} disabled - skipping')
                continue
            hosttype = hostprops.host_type

            _h = None
            if hosttype == 'local':
                # special case - using pytranscoder host also as cluster host
                _h = ManagerHost(host, hostprops, self.queue, self)
                self.hosts.append(_h)

            elif hosttype == 'mounted':
                _h = MountedRemoteHost(host, hostprops, self.queue, self)
                self.hosts.append(_h)

            elif hosttype == 'streaming':
                _h = StreamingRemoteHost(host, hostprops, self.queue, self)
                self.hosts.append(_h)

            else:
                print(f'Unknown cluster host type "{hosttype}" - skipping')

            if _h is not None and not _h.validate_settings():
                sys.exit(1)

    def enqueue(self, file) -> bool:
        """Add a media file to this cluster queue.
           This is different than in local mode in that we only care about handling skips here.
           The profile will be selected once a host is assigned to the work
        """

        path = os.path.abspath(file)  # convert to full path so that rule filtering can work
        if pytranscoder.verbose:
            print('matching ' + path)

        media_info = fetch_details(path, self.config.ffmpeg_path)
        if media_info.vcodec is not None:

            rule = self.config.match_rule(media_info)
            if rule is None:
                print(f'No matching profile found - skipped')
                return False
            if rule.is_skip():
                print(f'Skipping due to profile rule: {rule.name}')
                return False

            # not short circuited by a skip rule, continue
            self.queue.put(RemoteJob(file, media_info))
            return True

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
        # wait for queue to process
        self.queue.join()

    @property
    def profiles(self):
        return self.config.profiles


def manage_clusters(files, config: ConfigFile, dry_run: bool = False, testing=False):
    """Main entry point for setup and execution of all clusters

        There is one thread per cluster, and each cluster manages multiple hosts, each having their own thread.
    """

    cluster_config = config.settings['clusters']
    terminal_lock = Lock()
    clusters = dict()
    for name, this_config in cluster_config.items():
        for item in files:
            filepath, target_cluster = item
            if target_cluster != name:
                continue
            if target_cluster not in clusters:
                clusters[target_cluster] = Cluster(target_cluster, this_config, config, terminal_lock,
                                                   config.ssh_path, dry_run)
            clusters[target_cluster].enqueue(filepath)

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
