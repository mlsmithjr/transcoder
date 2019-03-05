import math
import os
import shutil
import subprocess
import sys
from queue import Queue
from threading import Thread, Lock
from typing import Dict, List, Set
from pathlib import Path, PureWindowsPath

from pytranscoder.utils import filter_threshold


class Host(Thread):
    hostname: str
    props: Dict
    queue: Queue
    lock: Lock
    _complete: Set
    _cluster = None

    def __init__(self, hostname, props, queue, lock, cluster):
        super().__init__(name = hostname, group = None, daemon=True)
        self.hostname = hostname
        self.props = props
        self.queue = queue
        self.lock = lock
        self._complete = set()
        self._cluster = cluster

    def complete(self, source):
        self._complete.add(source)

    def log(self, *args):
        self.lock.acquire()
        try:
            print(f'[{self._cluster.name}]({self.hostname}): ', *args)
        finally:
            self.lock.release()

    def testrun(self):
        pass

    def is_windows(self):
        return 'os' in self.props and self.props['os'] == 'win10'

    def converted_path(self, path):
        if self.is_windows():
            return str(PureWindowsPath(path))
        else:
            return str(Path(path))

    def ssh_cmd(self):
        return ['/usr/bin/ssh', self.props['user'] + '@' + self.props['ip']]

    def ping_test_ok(self):
        addr = self.props['ip']
        p = subprocess.Popen(['ping', '-c', '1', '-W', '5', addr], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        p.communicate()
        if p.returncode != 0:
            print(f'Host {self.hostname} at address {addr} cannot be reached - skipped')
            return False
        return True

    def ssh_test_ok(self):
        remote_cmd = 'dir' if self.is_windows() else 'ls'
        sshtest = subprocess.run([*self.ssh_cmd(), remote_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, timeout=5)
        if sshtest.returncode != 0:
            self.log('ssh test failed with the following output: ' + sshtest.stderr)
            return False
        return True

    def host_ok(self):
        return self.ping_test_ok() and self.ssh_test_ok()

    def run_process(self, *args):
        p = subprocess.run(*args)
        if self._cluster.verbose:
            self.log(' '.join(*args))
            if p.returncode != 0:
                self.log(p.stderr)
        return p


class StreamingHost(Host):

    def __init__(self, hostname, props, queue, lock, cluster):
        super().__init__(hostname, props, queue, lock, cluster)

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

        if 'working_dir' not in self.props:
            print(f'Missing "working_dir" setting for host {self.hostname}')
            return
        ssh_cmd = ['/usr/bin/ssh', self.props['user'] + '@' + self.props['ip']]

        while not self.queue.empty():
            profile_name = self.props['profile']
            try:
                _profile = self._cluster.profiles[profile_name]
                inpath = self.queue.get()
                #
                # for escaped spaces convert back to normal
                #
                inpath = inpath.replace('\\ ', ' ')

                #
                # calculate paths
                #
                working_dir = self.props['working_dir']
                remote_inpath = os.path.join(working_dir, os.path.basename(inpath))
                remote_outpath = os.path.join(working_dir, os.path.basename(inpath) + '.tmp')

                #
                # build remote ffmpeg commandline
                #
                if 'input_options' in _profile and _profile['input_options'] is not None:
                    oinput = _profile['input_options'].split()
                else:
                    oinput = []
                ooutput = _profile['output_options'].split()
                quiet = ['-nostats', '-hide_banner']

                cmd = [self.props['ffmpeg'], '-y', *quiet, *oinput, '-i', self.converted_path(remote_inpath),
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

                if self._cluster.dry_run:
                    continue

                #
                # Copy source file to remote
                #
                target_dir = working_dir
                if self.is_windows():
                    # trick to make scp work on the Windows side
                    target_dir = '/' + working_dir
                scp = ['scp', inpath, self.props['user'] + '@' + self.props['ip'] + ':' + target_dir]
                self.log(' '.join(scp))
                p = subprocess.Popen(scp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
                output = p.communicate()[0].decode('utf-8')
                if p.returncode != 0:
                    self.log('Unknown error copying source to remote - media skipped')
                    if self._cluster.verbose:
                        self.log(output)
                    continue

                #
                # run remote shell to ffmpeg
                #
                self.log(f'Starting transcode')
                p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
                output = p.communicate()[0].decode('utf-8')
                if p.returncode != 0:
                    self.log('Unknown error encoding on remote')
                    if self._cluster.verbose:
                        self.log(output)
                    continue

                #
                # copy results back to local
                #
#                self.log(f'Retrieving media from {working_dir} on host')
                retrieved_copy_name = os.path.join('/tmp', os.path.basename(remote_outpath))
                cmd = ['scp', self.props['user'] + '@' + self.props['ip'] + ':' + remote_outpath, retrieved_copy_name]
                self.log(' '.join(cmd))
                p = subprocess.Popen(cmd)
                p.wait()
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

                self.log(f'Removing temporary media copies from {working_dir}')
                if self.is_windows():
                    remote_outpath = self.converted_path(remote_outpath)
                    remote_inpath = self.converted_path(remote_inpath)
                    self.run_process([*ssh_cmd,  f'"del {remote_outpath}"'])
                    self.run_process([*ssh_cmd, f'"del {remote_inpath}"'])
                else:
                    self.run_process([*ssh_cmd, f'"rm {remote_outpath}"'])
                    self.run_process([*ssh_cmd, f'"rm {remote_inpath}"'])

            finally:
                self.queue.task_done()


class MountedHost(Host):

    def __init__(self, hostname, props, queue, lock, cluster):
        super().__init__(hostname, props, queue, lock, cluster)

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
            profile_name = self.props['profile']
            try:
                _profile = self._cluster.profiles[profile_name]

                #
                # calculate paths
                #
                inpath = self.queue.get()
                outpath = inpath[0:inpath.rfind('.')] + _profile['extension'] + '.tmp'
                remote_inpath = inpath
                remote_outpath = outpath
                if 'path-substitution' in self.props:
                    #
                    # fix the input path to match what the remote machine expects
                    #
                    src = self.props['path-substitution']['src']
                    dest = self.props['path-substitution']['dest']
                    remote_inpath = inpath.replace(src, dest)
                    remote_outpath = outpath.replace(src, dest)

                #
                # build command line
                #
                if 'input_options' in _profile and _profile['input_options'] is not None:
                    oinput = _profile['input_options'].split()
                else:
                    oinput = []
                ooutput = _profile['output_options'].split()
                quiet = ['-nostats', '-hide_banner']
                cmd = [self.props['ffmpeg'], '-y', *quiet, *oinput, '-i', f'"{remote_inpath}"', *ooutput, f'"{remote_outpath}"']
                cli = ['/usr/bin/ssh', self.props['user'] + '@' + self.props['ip'], *cmd]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Host     : {self.hostname} (mounted)')
                    print(f'Filename : {remote_inpath}')
                    print(f'Profile  : {profile_name}')
                    print('ssh      : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if self._cluster.dry_run:
                    continue

                #
                # Start remote ffmpeg
                #
                self.log('Starting transcode')
                p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
                output = p.communicate()[0].decode('utf-8')
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
                    self.log(output)
                    os.remove(outpath)
            except Exception as ex:
                self.log(ex)
            finally:
                self.queue.task_done()


class Cluster(Thread):
    hosts: List[Host]
    queue: Queue
    lock: Lock
    profiles: List
    dry_run: bool
    verbose: bool

    def __init__(self, name, configs: Dict, profiles: Dict, lock: Lock, dry_run: bool, verbose: bool):
        super().__init__(name=name, group=None, daemon=True)
        self.queue = Queue()
        self.lock = lock
        self.dry_run = dry_run
        self.verbose = verbose
        self.hosts = list()
        self.profiles = profiles
        for host, props in configs.items():
            if props.get('status', 'enabled') != 'enabled':
                continue
            hosttype = props['type']
            if hosttype == 'mounted':
                _h = MountedHost(host, props, self.queue, self.lock, self)
                if not _h.host_ok():
                    continue

                if _h.is_windows():
                    print('Mounted hosts currently not supported for Windows. Switch to streaming type.')
                    continue

                self.hosts.append(_h)
            elif hosttype == 'streaming':
                _h = StreamingHost(host, props, self.queue, self.lock, self)
                if not _h.host_ok():
                    continue
                self.hosts.append(_h)
            else:
                print(f'Unknown cluster host type "{hosttype}"')
                sys.exit(1)

    def enqueue(self, file):
        self.queue.put(file)

    def testrun(self):
        for host in self.hosts:
            host.testrun()

    def run(self):
        if len(self.hosts) == 0:
            print(f'No hosts available in cluster "{self.name}"')
            return

        for host in self.hosts:
            host.start()
        # wait for queue to process
        self.queue.join()


def manage_cluster(files, config, profiles, dry_run: bool = False, verbose: bool = False, testing=False):

    cluster_config = config['clusters']
    lock = Lock()
    clusters = dict()
    for name, this_config in cluster_config.items():
        for item in files:
            filepath, target_cluster = item
            if target_cluster != name:
                continue
            if target_cluster not in clusters:
                clusters[target_cluster] = Cluster(target_cluster, this_config, profiles, lock, dry_run, verbose)
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
