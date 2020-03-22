#!/usr/bin/python3
import datetime
import glob
import os
import shutil
import sys
from pathlib import Path, PurePath
from typing import Set, List, Optional

from queue import Queue
from threading import Thread, Lock
import crayons

import pytranscoder

from pytranscoder import __version__
from pytranscoder.cluster import manage_clusters
from pytranscoder.config import ConfigFile
from pytranscoder.ffmpeg import FFmpeg
from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile, ProfileSKIP
from pytranscoder.utils import filter_threshold, files_from_file, calculate_progress, dump_stats, is_mounted

DEFAULT_CONFIG = os.path.expanduser('~/.transcode.yml')


class LocalJob:
    """One file with matched profile to be encoded"""

    def __init__(self, inpath: str, profile: Profile, info: MediaInfo):
        self.inpath = Path(os.path.abspath(inpath))
        self.profile = profile
        self.info = info


class QueueThread(Thread):
    """One transcoding thread associated to a queue"""

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
        self.ffmpeg = FFmpeg(self.config.ffmpeg_path)

    @property
    def lock(self):
        return self._manager.lock

    def complete(self, path: Path, elapsed_seconds):
        self._manager.complete.append((str(path), elapsed_seconds))

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

        while not self.queue.empty():
            try:
                job: LocalJob = self.queue.get()
                oinput = job.profile.input_options.as_shell_params()
                ooutput = job.profile.output_options.as_shell_params()

                fls = False
                if is_mounted(job.inpath) and self.config.fls_path():
                    # lets write output to local storage, for efficiency
                    outpath = PurePath(self.config.fls_path(), job.inpath.with_suffix(job.profile.extension).name)
                    fls = True
                else:
                    outpath = job.inpath.with_suffix(job.profile.extension + '.tmp')

                #
                # check if we need to exclude any streams
                #
                if job.info.is_multistream() and self.config.automap and job.profile.automap:
                    ooutput = ooutput + job.info.ffmpeg_streams(job.profile)
                cli = ['-y', *oinput, '-i', str(job.inpath), *ooutput, str(outpath)]

                #
                # display useful information
                #
                self.lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
                try:
                    print('-' * 40)
                    print('Filename : ' + crayons.green(os.path.basename(str(job.inpath))))
                    print(f'Profile  : {job.profile.name}')
                    print('ffmpeg   : ' + ' '.join(cli) + '\n')
                finally:
                    self.lock.release()

                if pytranscoder.dry_run:
                    continue

                basename = job.inpath.name

                def log_callback(stats):
                    pct_done, pct_comp = calculate_progress(job.info, stats)
                    self.log(f'{basename}: speed: {stats["speed"]}x, comp: {pct_comp}%, done: {pct_done:3}%')
                    if job.profile.threshold_check < 100:
                        if pct_done >= job.profile.threshold_check and pct_comp < job.profile.threshold:
                            # compression goal (threshold) not met, kill the job and waste no more time...
                            self.log(f'Encoding of {basename} cancelled and skipped due to threshold not met')
                            return True
                    # continue
                    return False

                job_start = datetime.datetime.now()
                code = self.ffmpeg.run(cli, log_callback)
                job_stop = datetime.datetime.now()
                elapsed = job_stop - job_start

                if code == 0:
                    if not filter_threshold(job.profile, str(job.inpath), outpath):
                        # oops, this transcode didn't do so well, lets keep the original and scrap this attempt
                        self.log(f'Transcoded file {job.inpath} did not meet minimum savings threshold, skipped')
                        self.complete(job.inpath, (job_stop - job_start).seconds)
                        os.unlink(str(outpath))
                        continue

                    self.complete(job.inpath, elapsed.seconds)
                    if not pytranscoder.keep_source:
                        if pytranscoder.verbose:
                            self.log(f'replacing {job.inpath} with {outpath}')
                        job.inpath.unlink()

                        if fls:
                            shutil.move(outpath, job.inpath.with_suffix(job.profile.extension))
                        else:
                            outpath.rename(job.inpath.with_suffix(job.profile.extension))

                        self.log(crayons.green(f'Finished {job.inpath}'))
                    else:
                        self.log(crayons.yellow(f'Finished {outpath}, original file unchanged'))
                elif code is not None:
                    self.log(f' Did not complete normally: {self.ffmpeg.last_command}')
                    self.log(f'Output can be found in {self.ffmpeg.log_path}')
                    try:
                        outpath.unlink()
                    except:
                        pass
            finally:
                self.queue.task_done()


class LocalHost:
    """Encapsulates functionality for local encoding"""

    lock:       Lock = Lock()
    complete:   List = list()            # list of completed files, shared across threads

    def __init__(self, configfile: ConfigFile):
        self.queues = dict()
        self.configfile = configfile
        self.ffmpeg = FFmpeg(self.configfile.ffmpeg_path)
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
                sys.exit(1)

            if len(path) == 0:
                continue

            if not os.path.isfile(path):
                print(crayons.red('file not found, skipping: ' + path))
                continue

            media_info = self.ffmpeg.fetch_details(path)
            if media_info is None:
                print(crayons.red(f'File not found: {path}'))
                continue
            if media_info.valid:

                if pytranscoder.verbose:
                    print(str(media_info))

                if forced_profile is None:
                    rule = self.configfile.match_rule(media_info)
                    if rule is None:
                        print(crayons.green(os.path.basename(path)), crayons.yellow(f'No matching profile found - skipped'))
                        continue
                    if rule.is_skip():
                        print(crayons.green(os.path.basename(path)), f'SKIPPED ({rule.name})')
                        self.complete.append((path, 0))
                        continue
                    profile_name = rule.profile
                    the_profile = self.configfile.get_profile(profile_name)
                else:
                    #
                    # looks good, add this file to the thread queue
                    #
                    the_profile = self.configfile.get_profile(forced_profile)
                    profile_name = forced_profile

                qname = the_profile.queue_name
                if pytranscoder.verbose:
                    print('Matched with profile {profile_name}')
                if qname is not None:
                    if not self.configfile.has_queue(the_profile.queue_name):
                        print(crayons.red(
                            f'Profile "{profile_name}" indicated queue "{qname}" that has not been defined')
                        )
                        sys.exit(1)
                    else:
                        self.queues[qname].put(LocalJob(path, the_profile, media_info))
                        if pytranscoder.verbose:
                            print('Added to queue {qname}')
                else:
                    self.queues['_default_'].put(LocalJob(path, the_profile, media_info))

    def notify_plex(self):
        """If plex notifications enabled, tell it to refresh"""

        if self.configfile.plex_server is not None and not pytranscoder.dry_run:
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


def cleanup_queuefile(queue_path: str, completed: Set):
    if not pytranscoder.dry_run and queue_path is not None:
        # pick up any newly added files
        files = set(files_from_file(queue_path))
        # subtract out the ones we've completed
        files = files - completed
        if len(files) > 0:
            # rewrite the queue file with just the pending ones
            with open(queue_path, 'w') as f:
                for path in files:
                    f.write(path + '\n')
        else:
            # processed them all, just remove the file
            try:
                os.remove(queue_path)
            except FileNotFoundError:
                pass


def install_sigint_handler():
    import signal
    import sys

    def signal_handler(signal, frame):
        print('Process terminated')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


def main():
    start()


def start():

    if len(sys.argv) == 2 and sys.argv[1] == '-h':
        print(f'pytrancoder (ver {__version__})')
        print('usage: pytrancoder [OPTIONS]')
        print('  or   pytrancoder [OPTIONS] --from-file <filename>')
        print('  or   pytrancoder [OPTIONS] file ...')
        print('  or   pytrancoder -c <cluster> file... -c <cluster> file...')
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
        sys.exit(0)

    install_sigint_handler()
    files = list()
    profile = None
    queue_path = None
    cluster = None
    configfile: Optional[ConfigFile] = None
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
            elif sys.argv[arg] == '-k':                 # keep original
                pytranscoder.keep_source = True
            elif sys.argv[arg] == '--dry-run':
                pytranscoder.dry_run = True
            elif sys.argv[arg] == '--host':             # run all cluster encodes on specific host
                host_override = sys.argv[arg + 1]
                arg += 1
            elif sys.argv[arg] == '-v':                 # verbose
                pytranscoder.verbose = True
            elif sys.argv[arg] == '-c':                 # cluster
                cluster = sys.argv[arg + 1]
                arg += 1
            else:
                if os.name == "nt":
                    expanded_files: List = glob.glob(sys.argv[arg])     # handle wildcards in Windows
                else:
                    expanded_files = [sys.argv[arg]]
                for f in expanded_files:
                    if cluster is None:
                        files.append((f, profile))
                    else:
                        files.append((f, cluster, profile))
            arg += 1

    if configfile is None:
        configfile = ConfigFile(DEFAULT_CONFIG)

    if 'sonarr_eventtype' in os.environ and os.environ['sonarr_eventtype'] == 'Download':
        sonarr_handler(configfile.default_queue_file)

    if not configfile.colorize:
        crayons.disable()
    else:
        crayons.enable()

    if len(files) == 0 and queue_path is None and configfile.default_queue_file is not None:
        tmpfiles = files_from_file(configfile.default_queue_file)
        queue_path = configfile.default_queue_file
        if cluster is None:
            files.extend([(f, profile) for f in tmpfiles])
        else:
            files.extend([(f, cluster, profile) for f in tmpfiles])

    if len(files) == 0:
        print(crayons.yellow(f'Nothing to do'))
        sys.exit(0)

    if cluster is not None:
        if host_override is not None:
            # disable all other hosts in-memory only - to force encodes to the designated host
            cluster_config = configfile.settings['clusters']
            for cluster in cluster_config.values():
                for name, this_config in cluster.items():
                    if name != host_override:
                        this_config['status'] = 'disabled'
        completed: List = manage_clusters(files, configfile)
        if len(completed) > 0:
            qpath = queue_path if queue_path is not None else configfile.default_queue_file
            pathlist = [p for p, _ in completed]
            cleanup_queuefile(qpath, set(pathlist))
            dump_stats(completed)
        sys.exit(0)

    host = LocalHost(configfile)
    host.enqueue_files(files)
    #
    # start all threads and wait for work to complete
    #
    host.start()
    if len(host.complete) > 0:
        completed_paths = [p for p, _ in host.complete]
        cleanup_queuefile(queue_path, set(completed_paths))
        dump_stats(host.complete)

        host.notify_plex()

    os.system("stty sane")


if __name__ == '__main__':
    start()
