#!/usr/bin/python3
import math
import os
import re
import sys
import yaml
import subprocess
from queue import Queue
from threading import Thread, Lock
from pytranscoder import __version__
from pytranscoder.cluster import manage_clusters
from pytranscoder.utils import filter_threshold

DEFAULT_CONFIG = os.path.expanduser('~/.transcode.yml')

valid_predicates = ['vcodec', 'res_height', 'res_width', 'runtime', 'filesize_mb', 'fps', 'path']
numeric_predicates = ['res_height', 'res_width', 'runtime', 'filesize_mb', 'fps']
video_re = re.compile(r'^.*Duration: (\d+):(\d+):.* Stream #0:0.*: Video: (\w+).*, (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
                      re.DOTALL)

complete = set()
single_mode = False
queue_path = None
profiles = dict()
matching_rules = dict()
config = dict()
queues = dict()
keep_source = False
dry_run = False
verbose = False


class MediaInfo:
    filesize_mb: int
    path: str
    res_height: int
    res_width: int
    runtime: int
    fps: int
    vcodec: str

    def __init__(self, path, vcodec, res_width, res_height, runtime, source_size, fps):
        self.path = path
        self.vcodec = vcodec
        self.res_height = res_height
        self.res_width = res_width
        self.runtime = runtime
        self.filesize_mb = source_size
        self.fps = fps

    def eval_numeric(self, rulename, pred, value) -> bool:
        attr = self.__dict__.get(pred, None)
        if attr is None:
            print(f'Error: Rule "{rulename}" unknown attribute: {pred} ')
            raise ValueError(value)

        if '-' in value:
            # this is a range expression
            parts = value.split('-')
            if len(parts) != 2:
                print(f'Error: Rule "{rulename}" bad range expression: {value} ')
                raise ValueError(value)
            rangelow, rangehigh = parts
            expr = f'{rangelow} < {attr} < {rangehigh}'
        elif value.isnumeric():
            # simple numeric equality test
            expr = f'{attr} == {value}'
        elif value[0] in '<>':
            op = value[0]
            value = value[1:]
            expr = f'{attr} {op} {value}'
        else:
            print(f'Error: Rule "{rulename}" valid value: {value}')
            return False

        if not eval(expr):
            if verbose:
                print(f'  >> predicate {pred} ("{value}") did not match {attr}')
            return False
        return True


class LocalJob:
    inpath: str
    outpath: str
    profile_name: str

    def __init__(self, inpath, outpath, profile_name):
        self.inpath = inpath
        self.outpath = outpath
        self.profile_name = profile_name


def match_profile(mediainfo: MediaInfo, rules) -> (str, str):
    global verbose

    for description, body in rules.items():
        if verbose:
            print(f' > evaluating "{description}"')
        if 'rules' not in body:
            # no rules section, match by default
            if verbose:
                print(f'  >> rule {description} selected by default (no criteria)')
            return body['profile'], description
        for pred, value in body['rules'].items():
            inverted = False
            if pred not in valid_predicates:
                print(f'Invalid predicate {pred} in rule {description}')
                exit(1)
            if isinstance(value, str) and len(value) > 1 and value[0] == '!':
                inverted = True
                value = value[1:]
            if pred == 'vcodec' and mediainfo.vcodec != value and not inverted:
                if verbose:
                    print(f'  >> predicate vcodec ("{value}") did not match {mediainfo.vcodec}')
                break
            if pred == 'path':
                try:
                    m = re.match(mediainfo.path, value)
                    if m is None:
                        if verbose:
                            print(f'  >> predicate path ("{value}") did not match {mediainfo.path}')
                        break
                except Exception as ex:
                    print(f'invalid regex {mediainfo.path} in rule {description}')
                    if verbose:
                        print(str(ex))
                    exit(0)

            if pred in numeric_predicates:
                comp = mediainfo.eval_numeric(description, pred, value)
                if not comp and not inverted:
                    # mismatch
                    break
                if comp and inverted:
                    # mismatch
                    break
        else:
            # didn't bail out on any predicates, have a match
            return body['profile'], description
    return None, None


def loadq(queuepath) -> list:
    if not os.path.exists(queuepath):
        print(f'Queue file {queuepath} not found')
        return []
    with open(queuepath, 'r') as qf:
        _files = [fn.rstrip() for fn in qf.readlines()]
        return _files


def fetch_details(_path: str) -> MediaInfo:
    with subprocess.Popen([config['ffmpeg'], '-i', _path], stderr=subprocess.PIPE) as proc:
        output = proc.stderr.read().decode(encoding='utf8')
        return parse_details(_path, output)


def parse_details(_path, output):
    match = video_re.match(output)
    if match is None or len(match.groups()) < 6:
        print(f'>>>> regex match on video stream data failed: ffmpeg -i {_path}')
        return MediaInfo(_path, None, 0, 0, 0, 0, 0)
    else:
        _dur_hrs, _dur_mins, _codec, _res_width, _res_height, fps = match.group(1, 2, 3, 4, 5, 6)
        filesize = os.path.getsize(_path) / (1024 * 1024)
        return MediaInfo(_path, _codec, int(_res_width), int(_res_height), (int(_dur_hrs) * 60) + int(_dur_mins),
                         filesize, int(fps))


def thread_runner(lock, queue):
    global keep_source, config, dry_run

    while not queue.empty():
        try:
            job: LocalJob = queue.get()
            _profile = profiles[job.profile_name]
            if 'input_options' in _profile and _profile['input_options'] is not None:
                oinput = _profile['input_options'].split()
            else:
                oinput = []
            ooutput = _profile['output_options'].split()
            if single_mode and sys.stdout.isatty():
                quiet = ''
            else:
                quiet = ['-nostats', '-loglevel', 'quiet']
            cli = [config['ffmpeg'], '-y', *quiet, *oinput, '-i', job.inpath, *ooutput, job.outpath]

            #
            # display useful information
            #
            lock.acquire()  # used to synchronize threads so multiple threads don't create a jumble of output
            try:
                print('-' * 40)
                print(f'Filename : {job.inpath}')
                print(f'Profile  : {job.profile_name}')
                print('ffmpeg   : ' + ' '.join(cli) + '\n')
            finally:
                lock.release()

            if dry_run:
                continue
            p = subprocess.Popen(cli)
            p.wait()
            if p.returncode == 0:
                if not filter_threshold(_profile, job.inpath, job.outpath):
                    # oops, this transcode didn't do so well, lets keep the original and scrap this attempt
                    print(f'Transcoded file {job.inpath} did not meet minimum savings threshold, skipped')
                    complete.add(job.inpath)
                    os.remove(job.outpath)
                    continue

                complete.add(job.inpath)
                if not keep_source:
                    print('removing ' + job.inpath)
                    os.remove(job.inpath)
                    print('renaming ' + job.outpath)
                    os.rename(job.outpath, job.outpath[:-4])
            else:
                print(f'error during transcode of {job.inpath}, .tmp file removed')
                os.remove(job.outpath)
        finally:
            queue.task_done()


def load_config(_path):
    """load configuration file (defaults to $HOME/.transcode.yml)"""

    global profiles, matching_rules, config

    with open(_path, 'r') as f:
        yml = yaml.load(f)
        profiles = yml['profiles']
        matching_rules = yml['rules']
        config = yml['config']
        if 'queues' not in config:
            print('"queues" definition missing from transcode.yml configuration file')
            sys.exit(1)


def notify_plex():
    """If plex notifications enabled, tell it to refresh"""

    global config

    if 'plex_server' in config and config['plex_server'] is not None and not dry_run:
        plex_server = config['plex_server']
        try:
            from plexapi.server import PlexServer

            plex = PlexServer('http://{}'.format(plex_server))
            plex.library.update()
            # plex.library.section(PLEX_DEFAULT_REFRESH_LIBRARY).update()
        except ModuleNotFoundError:
            print(
                'Library not installed. To use Plex notifications please install the Python 3 Plex API ' +
                '("pip3 install plexapi")')
        except Exception as ex2:
            print(f'Unable to connect to Plex server at {plex_server}')
            if verbose:
                print(str(ex2))


def enqueue_files(files: list):
    """Add requested files to the appropriate queue

    :param files: list of (path,profile) tuples
    :return:
    """
    global queues

    for path, forced_profile in files:
        #
        # do some prechecks...
        #
        if forced_profile is not None and forced_profile not in profiles:
            print(f'profile "{forced_profile}" referenced from command line not found')
            exit(1)

        if len(path) == 0:
            continue
        if not os.path.isfile(path):
            print('path not found, skipping: ' + path)
            continue

        path = os.path.abspath(path)  # convert to full path so that rule filtering can work
        print('matching ' + path)
        minfo = fetch_details(path)
        if minfo.vcodec is not None:

            if forced_profile is None:
                profile_name, rule = match_profile(minfo, matching_rules)
                if profile_name is None:
                    print(f'No matching profile found - skipped')
                    continue
                if profile_name.upper() == 'SKIP':
                    print(f'Skipping due to profile rule: {rule}')
                    complete.add(path)
                    continue
                if profile_name not in profiles:
                    print(f'profile "{profile_name}" referenced from rule "{rule}" not found')
                    exit(1)
                the_profile = profiles[profile_name]
            else:
                #
                # looks good, add this file to the thread queue
                #
                the_profile = profiles[forced_profile]
                profile_name = forced_profile

            outpath = path[0:path.rfind('.')] + the_profile['extension'] + '.tmp'
            if 'queue' in the_profile:
                qname = the_profile['queue']
                if qname not in queues:
                    print(f'Profile "{profile_name}" indicated queue "{qname}" that has not been defined - skipping {path}')
                else:
                    queues[qname].put(LocalJob(path, outpath, profile_name))
            else:
                queues['_default_'].put(LocalJob(path, outpath, profile_name))


def sonarr_handler():
    """Handle Sonarr as caller"""

    global config

    # Being called from Sonarr after download/import.
    # It is not a good idea to start transcoding since this may be called rapidly during
    # an import, in which case the concurrency model fails.
    # Solution is to log the incoming file to the queue and let user run the transcode at an
    # appropriate time.
    path = os.environ['sonarr_episodefile_path']
    print(f'Writing "{path}" to default queue')
    if 'default_queue_file' in config:
        qfilename = config['default_queue_file']
        try:
            with open(qfilename, 'a+') as qfile:
                qfile.write(f'{path}\n')
        except Exception as ex:
            print(f'Unable to write to {qfilename}')
            print(ex)
        exit(0)


def main():
    start()


def start():
    global single_mode, keep_source, verbose, dry_run, queues, queue_path

    if len(sys.argv) == 2 and sys.argv[1] == '-h':
        print('usage: {} [OPTIONS]'.format(sys.argv[0], ))
        print('  or   {} [OPTIONS] --from-file <filename>'.format(sys.argv[0], ))
        print('  or   {} [OPTIONS] file ...'.format(sys.argv[0], ))
        print('  or   {} -c <cluster> file ... -r <cluster> ...'.format(sys.argv[0], ))
        print('No parameters indicates to process the default queue files using profile matching rules.')
        print(
            'The --from-file filename is a file containing a list of full paths to files for transcoding. ' +
            'If full paths not used, defaults to current directory')
        print('OPTIONS:')
        print('  -s         Process files sequentially even if configured for multiple concurrent jobs')
        print('  --dry-run  Run without actually transcoding or modifying anything, useful to test rules and profiles')
        print('  -v         Verbose output, helpful in debugging profiles and rules')
        print(
            '  -k         Keep source files after transcoding. If used, the transcoded file will have the same name and .tmp extension')
        print('  -y <file>  Full path to configuration file.  Default is ~/.transcode.yml')
        print('  -p         profile to use. If used with --from-file, applies to all listed media in <filename>')
        print('             Otherwise, applies to all following files up to the next occurrance')
        print(
            '                 Ex: {} --from-file /home/me/batch.txt -p hevc_hd /tmp/testvid1.mp4 /tmp/testvid2.mp4'.format(
                sys.argv[0]))
        print(
            '                   This will transcode all videos listed in batch.txt using the rules, using hevc_hd profile for the others')
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
    cluster_mode = False
    cluster = None
    if len(sys.argv) > 1:
        files = []
        arg = 1
        while arg < len(sys.argv):
            if sys.argv[arg] == '--from-file':
                queue_path = sys.argv[arg + 1]
                arg += 1
                tmpfiles = loadq(queue_path)
                if not cluster_mode:
                    files.extend([(f, profile) for f in tmpfiles])
                else:
                    files.extend([(f, cluster) for f in tmpfiles])
            elif sys.argv[arg] == '-p':
                profile = sys.argv[arg + 1]
                arg += 1
            elif sys.argv[arg] == '-y':
                arg += 1
                load_config(sys.argv[arg])
            elif sys.argv[arg] == '-s':
                single_mode = True
            elif sys.argv[arg] == '-k':
                keep_source = True
            elif sys.argv[arg] == '--dry-run':
                dry_run = True
            elif sys.argv[arg] == '-v':
                verbose = True
            elif sys.argv[arg] == '-c':
                cluster = sys.argv[arg + 1]
                arg += 1
                cluster_mode = True
            else:
                if not cluster_mode:
                    files.append((sys.argv[arg], profile))
                else:
                    files.append((sys.argv[arg], cluster))
            arg += 1

    if len(profiles) == 0:
        load_config(DEFAULT_CONFIG)

    if 'sonarr_eventtype' in os.environ and os.environ['sonarr_eventtype'] == 'Download':
        sonarr_handler()

    if len(files) == 0 and queue_path is None and 'default_queue_file' in config:
        queue_path = config['default_queue_file']
        tmpfiles = loadq(queue_path)
        files.extend([(f, profile) for f in tmpfiles])

    if files is None:
        exit(0)

    if cluster_mode:
        manage_clusters(files, config, profiles, dry_run, verbose)
        sys.exit(0)

    if len(files) == 1:
        single_mode = True

    config['queues']['_default_'] = 1
    for qname in config['queues'].keys():
        queues[qname] = Queue()
    enqueue_files(files)

    #
    # all files are listed in the queues so start the threads
    #
    lock = Lock()
    jobs = list()
    for name, queue in queues.items():

        # determine the number of threads to allocate for this queue, minimum of defined max and pending jobs

        cmax = min(config['queues'][name], queue.qsize())

        #
        # Create (n) threads and assign them a queue
        #
        for _ in range(cmax):
            t = Thread(target=thread_runner, daemon=True, args=(lock, queue))
            jobs.append(t)
            t.start()

    # wait for all queues to drain and all jobs to complete
    for _, queue in queues.items():
        queue.join()

    if not dry_run and queue_path is not None:
        # pick up any newly added files
        files = set(loadq(queue_path))
        # subtract out the ones we've completed
        files = files - complete
        if len(files) > 0:
            # rewrite the queue file with just the pending ones
            with open(queue_path, 'w') as f:
                for path in files:
                    f.write(path + '\n')
        else:
            # processed them all, just remove the file
            os.remove(queue_path)

    notify_plex()
    os.system("stty sane")


if __name__ == '__main__':
    start()

