#!/usr/bin/python3
import os
import sys
from typing import Dict

import subprocess
from queue import Queue
from threading import Thread, Lock

import pytranscoder

from pytranscoder import __version__
from pytranscoder.cluster import manage_clusters
from pytranscoder.config import ConfigFile
from pytranscoder.media import MediaInfo, fetch_details
from pytranscoder.profile import Profile
from pytranscoder.utils import filter_threshold, files_from_file, monitor_ffmpeg

DEFAULT_CONFIG = os.path.expanduser('~/.transcode.yml')

single_mode = False
keep_source = False
dry_run = False


class LocalJob:
    """One file with matched profile to be encoded"""
    inpath: str
    outpath: str
    profile: Profile
    info: MediaInfo

    def __init__(self, inpath, outpath, profile: Profile, info: MediaInfo):
        self.inpath = inpath
        self.outpath = outpath
        self.profile = profile
        self.info = info


class QueueThread(Thread):
    """One transcoding thread associated to a queue"""

    queue: Queue
    config: ConfigFile
    _manager = None

    def __init__(self, queuename, queue: Queue, configfile: ConfigFile, manager):
        """
        :param queuename:   Name of the queue, for thread naming purposes only
        :param queue:       Thread-safe queue containing files to be encoded
        :param configfile:  Instance of the parsed configuration (transcode.yml)
        :param manager:     Reference to object that manages this thread
        """
        super().__init__(name=queuename, group=None, daemon=True)
        self.queue = queue
        self.config = configfile
        self._manager = manager

    @property
    def lock(self):
        return self._manager.lock

    def complete(self, path):
        self._manager.complete.add(path)

    def start_test(self):
        self.go()

    def run(self):
        self.go()

    def log(self, *args, **kwargs):
        self.lock.acquire()
        print(*args, **kwargs)
        sys.stdout.flush()
        self.lock.release()

    def go(self):
        global keep_source, dry_run

        while not self.queue.empty():
            try:
                job: LocalJob = self.queue.get()
                oinput = job.profile.input_options
                ooutput = job.profile.output_options
#                if single_mode and sys.stdout.isatty():
#                    quiet = ''
#                else:
#                    quiet = ['-nostats', '-loglevel', 'quiet']
                cli = [self.config.ffmpeg_path, '-y', *oinput, '-i', job.inpath, *ooutput, job.outpath]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print(f'Filename : {job.inpath}')
                    print(f'Profile  : {job.profile.name}')
                    print('ffmpeg   : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if dry_run:
                    continue

                p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                     shell=False)
                for name, stats in monitor_ffmpeg(os.path.basename(job.inpath), p):
                    pct_done = int((stats['time'] / job.info.runtime) * 100)
                    self.log(f'{name}: {pct_done:3}%, speed: {stats["speed"]}x')

                if p.returncode == 0:
                    if not filter_threshold(job.profile, job.inpath, job.outpath):
                        # oops, this transcode didn't do so well, lets keep the original and scrap this attempt
                        self.log(f'Transcoded file {job.inpath} did not meet minimum savings threshold, skipped')
                        self.complete(job.inpath)
                        os.remove(job.outpath)
                        continue

                    self.complete(job.inpath)
                    if not keep_source:
                        self.log('removing ' + job.inpath)
                        os.remove(job.inpath)
                        self.log('renaming ' + job.outpath)
                        os.rename(job.outpath, job.outpath[:-4])
                else:
                    self.log(f'error during transcode of {job.inpath}, .tmp file removed')
                    os.remove(job.outpath)
            finally:
                self.queue.task_done()


class LocalHost:
    """Encapsulates functionality for local encoding"""

    config: Dict
    configfile: ConfigFile
    queues: Dict[str, Queue]
    lock: Lock
    complete = set()              # list of completed files, shared across threads

    def __init__(self, configfile: ConfigFile):
        self.queues = dict()
        self.configfile = configfile
        #
        # initialize the queues
        #
        self.queues['_default_'] = Queue()
        for qname in configfile.queues.keys():
            self.queues[qname] = Queue()

    def start(self):
        """After initialization this is where processing begins"""
        #
        # all files are listed in the queues so start the threads
        #
        self.lock = Lock()
        jobs = list()
        for name, queue in self.queues.items():

            # determine the number of threads to allocate for each queue, minimum of defined max and queued jobs

            if name == '_default_':
                concurrent_max = 1
            else:
                concurrent_max = min(self.configfile.queues[name], queue.qsize())

            #
            # Create (n) threads and assign them a queue
            #
            for _ in range(concurrent_max):
                t = QueueThread(name, queue, self.configfile, self)
                jobs.append(t)
                t.start()

        # wait for all queues to drain and all jobs to complete
        for _, queue in self.queues.items():
            queue.join()

    def enqueue_files(self, files: list):
        """Add requested files to the appropriate queue

        :param files: list of (path,profile) tuples
        :return:
        """

        for path, forced_profile in files:
            #
            # do some prechecks...
            #
            if forced_profile is not None and not self.configfile.has_profile(forced_profile):
                print(f'profile "{forced_profile}" referenced from command line not found')
                exit(1)

            if len(path) == 0:
                continue

            if not os.path.isfile(path):
                print('path not found, skipping: ' + path)
                continue

            path = os.path.abspath(path)  # convert to full path so that rule filtering can work
            if pytranscoder.verbose:
                print('matching ' + path)
            media_info = fetch_details(path, self.configfile.ffmpeg_path)
            if media_info.vcodec is not None:

                if forced_profile is None:
                    rule = self.configfile.match_rule(media_info)
                    if rule is None:
                        print(f'No matching profile found - skipped')
                        continue
                    if rule.is_skip():
                        print(f'Skipping due to profile rule: {rule.name}')
                        self.complete.add(path)
                        continue
                    profile_name = rule.profile
                    the_profile = self.configfile.get_profile(profile_name)
                else:
                    #
                    # looks good, add this file to the thread queue
                    #
                    the_profile = self.configfile.get_profile(forced_profile)
                    profile_name = forced_profile

                outpath = path[0:path.rfind('.')] + the_profile.extension + '.tmp'
                qname = the_profile.queue_name
                if qname is not None:
                    if not self.configfile.has_queue(the_profile.queue_name):
                        print(
                            f'Profile "{profile_name}" indicated queue "{qname}" that has not been defined')
                        sys.exit(1)
                    else:
                        self.queues[qname].put(LocalJob(path, outpath, the_profile, media_info))
                else:
                    self.queues['_default_'].put(LocalJob(path, outpath, the_profile, media_info))

    def notify_plex(self):
        """If plex notifications enabled, tell it to refresh"""

        if self.configfile.plex_server is not None and not dry_run:
            plex_server = self.configfile.plex_server
            try:
                from plexapi.server import PlexServer

                plex = PlexServer('http://{}'.format(plex_server))
                plex.library.update()
            except ModuleNotFoundError:
                print(
                    'Library not installed. To use Plex notifications please install the Python 3 Plex API ' +
                    '("pip3 install plexapi")')
            except Exception as ex2:
                print(f'Unable to connect to Plex server at {plex_server}')
                if pytranscoder.verbose:
                    print(str(ex2))


def sonarr_handler(qfilename: str):
    """Handle Sonarr as caller"""

    # Being called from Sonarr after download/import.
    # It is not a good idea to start transcoding since this may be called rapidly during
    # an import, in which case the concurrency model fails.
    # Solution is to log the incoming file to the queue and let user run the transcode at an
    # appropriate time.
    if qfilename is not None:
        path = os.environ['sonarr_episodefile_path']
        print(f'Writing "{path}" to default queue')
        try:
            with open(qfilename, 'a+') as qfile:
                qfile.write(f'{path}\n')
        except Exception as ex:
            print(f'Unable to write to {qfilename}')
            print(ex)
    sys.exit(0)


def main():
    start()


def start():
    global single_mode, keep_source, dry_run

    if len(sys.argv) == 2 and sys.argv[1] == '-h':
        print('usage: {} [OPTIONS]'.format(sys.argv[0], ))
        print('  or   {} [OPTIONS] --from-file <filename>'.format(sys.argv[0], ))
        print('  or   {} [OPTIONS] file ...'.format(sys.argv[0], ))
        print('  or   {} -c <cluster> file ... -c <cluster> ...'.format(sys.argv[0], ))
        print('No parameters indicates to process the default queue files using profile matching rules.')
        print(
            'The --from-file filename is a file containing a list of full paths to files for transcoding. ' +
            'If full paths not used, defaults to current directory')
        print('OPTIONS:')
        print('  -s         Process files sequentially even if configured for multiple concurrent jobs')
        print('  --dry-run  Run without actually transcoding or modifying anything, useful to test rules and profiles')
        print('  -v         Verbose output, helpful in debugging profiles and rules')
        print(
            '  -k         Keep source files after transcoding. If used, the transcoded file will have the same '
            'name and .tmp extension')
        print('  -y <file>  Full path to configuration file.  Default is ~/.transcode.yml')
        print('  -p         profile to use. If used with --from-file, applies to all listed media in <filename>')
        print('             Otherwise, applies to all following files up to the next occurrance')
        print(
            '                 Ex: {} --from-file /home/me/batch.txt -p hevc_hd /tmp/testvid1.mp4 '
            '/tmp/testvid2.mp4'.format(sys.argv[0]))
        print(
            '                   This will transcode all videos listed in batch.txt using the rules, using '
            'hevc_hd profile for the others')
        print('                 Ex: {} -p hevc_25fps --from-file /home/me/batch.txt'.format(sys.argv[0]))
        print('                   This will transcode all videos listed in batch.txt using the the hevc_25fps profile')
        print('                 Ex: {} -p hevc_25fps /tmp/vid1.mp4 -p hevc_hd /tmp/vid2.mp4'.format(sys.argv[0]))
        print('                   This will transcode the given videos using different profiles')
        print('Individual files may be listed on the command line for processing\n')
        print('** Version ' + __version__)
        sys.exit(0)

    files = list()
    profile = None
    queue_path = None
    cluster = None
    configfile: ConfigFile = None
    host_override = None
    if len(sys.argv) > 1:
        files = []
        arg = 1
        while arg < len(sys.argv):
            if sys.argv[arg] == '--from-file':          # load filenames to encode from given file
                queue_path = sys.argv[arg + 1]
                arg += 1
                tmpfiles = files_from_file(queue_path)
                if cluster is None:
                    files.extend([(f, profile) for f in tmpfiles])
                else:
                    files.extend([(f, cluster) for f in tmpfiles])
            elif sys.argv[arg] == '-p':                 # specific profile
                profile = sys.argv[arg + 1]
                arg += 1
            elif sys.argv[arg] == '-y':                 # specify yaml config file
                arg += 1
                configfile = ConfigFile(sys.argv[arg])
            elif sys.argv[arg] == '-s':                 # force single threading/sequential
                single_mode = True
            elif sys.argv[arg] == '-k':                 # keep original
                keep_source = True
            elif sys.argv[arg] == '--dry-run':
                dry_run = True
            elif sys.argv[arg] == '--host':             # run all cluster encodes on specific host
                host_override = sys.argv[arg + 1]
                arg += 1
            elif sys.argv[arg] == '-v':                 # verbose
                pytranscoder.verbose = True
            elif sys.argv[arg] == '-c':                 # cluster
                cluster = sys.argv[arg + 1]
                arg += 1
            else:
                if cluster is None:
                    files.append((sys.argv[arg], profile))
                else:
                    files.append((sys.argv[arg], cluster))
            arg += 1

    if configfile is None:
        configfile = ConfigFile(DEFAULT_CONFIG)

    if 'sonarr_eventtype' in os.environ and os.environ['sonarr_eventtype'] == 'Download':
        sonarr_handler(configfile.default_queue_file)

    if len(files) == 0 and queue_path is None and configfile.default_queue_file is not None:
        tmpfiles = files_from_file(configfile.default_queue_file)
        files.extend([(f, profile) for f in tmpfiles])

    if files is None:
        print(f'Nothing to do')
        exit(0)

    if cluster is not None:
        if host_override is not None:
            # disable all other hosts in-memory only to force encodes to the designated host
            cluster_config = configfile.settings['clusters']
            for name, this_config in cluster_config.items():
                if name != host_override:
                    this_config['status'] = 'disabled'
        manage_clusters(files, configfile, dry_run)
        sys.exit(0)

    if len(files) == 1:
        single_mode = True

    host = LocalHost(configfile)
    host.enqueue_files(files)
    #
    # start all threads and wait for work to complete
    #
    host.start()

    if not dry_run and queue_path is not None:
        # pick up any newly added files
        files = set(files_from_file(queue_path))
        # subtract out the ones we've completed
        files = files - host.complete
        if len(files) > 0:
            # rewrite the queue file with just the pending ones
            with open(queue_path, 'w') as f:
                for path in files:
                    f.write(path + '\n')
        else:
            # processed them all, just remove the file
            os.remove(queue_path)

    host.notify_plex()
    os.system("stty sane")


if __name__ == '__main__':
    start()
