#!/usr/bin/python3

import os
import re
import sys
import yaml
import subprocess
from queue import Queue
from threading import Thread


DEFAULT_CONFIG = os.path.expanduser('~/.transcode.yml')

valid_predicates = ['vcodec', 'res_height', 'res_width', 'runtime', 'filesize_mb', 'fps']
video_re = re.compile('^.*Duration: (\d+):(\d+):.* Stream #0:0.*: Video: (\w+).*, (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
                      re.DOTALL)
thread_queue = Queue(10)
complete = set()
queue_path = None
profiles = dict()
matching_rules = dict()
config = dict()
concurrent_jobs = 2
keep_source = False
dry_run = False
verbose = False

class MediaInfo:
    filesize_mb : int
    path : str
    res_height : int
    res_width : int
    runtime : int
    fps : int
    vcoded : str

    def __init__(self, path, vcodec, res_width, res_height, runtime, source_size, fps):
        self.path = path
        self.vcodec = vcodec
        self.res_height = res_height
        self.res_width = res_width
        self.runtime = runtime
        self.filesize_mb = source_size
        self.fps = fps



def match_profile(mediainfo: MediaInfo) -> (str, str):
    global verbose

    for description, body in matching_rules.items():
        if verbose: print(f' > evaluating "{description}"')
        if 'rules' not in body:
            # no rules section, match by default
            if verbose: print(f'  >> rule {description} selected by default (no criteria)')
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
                    exit(0)
            if pred == 'res_height' and len(value) > 1:
                if value.isnumeric():
                    value = '==' + value  # make python-friendly
                if not eval(f'{mediainfo.res_height}{value}'):
                    if verbose:
                        print(f'  >> predicate res_height ("{value}") did not match {mediainfo.res_height}')
                    break
            if pred == 'res_width' and len(value) > 1:
                if value.isnumeric():
                    value = '==' + value  # make python-friendly
                if not eval(f'{mediainfo.res_width}{value}'):
                    if verbose:
                        print(f'  >> predicate res_width ("{value}") did not match {mediainfo.res_width}')
                    break
            if pred == 'runtime' and len(value) > 1:
                if value.isnumeric():
                    value = '==' + value  # make python-friendly
                if not eval(f'{mediainfo.runtime}{value}'):
                    if verbose:
                        print(f'  >> predicate runtime ("{value}") did not match {mediainfo.runtime}')
                    break
            if pred == 'fps' and len(value) > 1:
                if value.isnumeric():
                    value = '==' + value  # make python-friendly
                if not eval(f'{mediainfo.fps}{value}'):
                    if verbose:
                        print(f'  >> predicate fps ("{value}") did not match {mediainfo.fps}')
                    break
            if pred == 'filesize_mb' and len(value) > 1:
                if value.isnumeric():
                    value = '==' + value  # make python-friendly
                if not eval(f'{mediainfo.filesize_mb}{value}'):
                    if verbose:
                        print(f'  >> predicate filesize_mb ("{value}") did not match {mediainfo.filesize_mb}')
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
    with subprocess.Popen(['ffmpeg', '-i', _path], stderr=subprocess.PIPE) as proc:
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


def perform_transcodes():
    global keep_source, config, dry_run

    while not thread_queue.empty():
        try:
            _inpath, _outpath, profile_name = thread_queue.get()
            print(f'transcoding {_inpath}:')
            _profile = profiles[profile_name]
            oinput = _profile['input_options'].split()
            ooutput = _profile['output_options'].split()
            cli = [config['ffmpeg']] + oinput + ['-i', _inpath] + ooutput + [_outpath]
            # cli = [FFMPEG, '-hide_banner', '-nostats', '-hwaccel', 'cuvid', '-i', _inpath, '-c:v', 'hevc_nvenc',
            #       '-profile:v', 'main', '-preset', 'medium', '-crf', '22', '-c:a', 'copy', '-c:s', 'copy', '-f',
            #       'matroska',
            #       _outpath]
            print(profile_name + ' -->  ' + ' '.join(cli) + '\n')
            if dry_run:
                continue
            p = subprocess.Popen(cli)
            p.wait()
            if p.returncode == 0:
                complete.add(_inpath)
                if not keep_source:
                    print('removing ' + _inpath)
                    os.remove(_inpath)
                    print('renaming ' + _outpath)
                    os.rename(_outpath, _outpath[:-4])
            else:
                print('error during transcode, .tmp file removed')
                os.remove(_outpath)
        finally:
            thread_queue.task_done()


def load_config(_path):
    global profiles, matching_rules, config, concurrent_jobs

    with open(_path, 'r') as f:
        yml = yaml.load(f)
        profiles = yml['profiles']
        matching_rules = yml['rules']
        config = yml['config']
        concurrent_jobs = config['concurrent_jobs']


def notify_plex():
    global config

    if 'plex_server' in config and config['plex_server'] is not None and not dry_run:
        plex_server = config['plex_server']
        try:
            from plexapi.server import PlexServer

            plex = PlexServer('http://{}'.format(plex_server))
            plex.library.update()
            # plex.library.section(PLEX_DEFAULT_REFRESH_LIBRARY).update()
        except ModuleNotFoundError as ex:
            print(
                'Library not installed. To use Plex notifications please install the Python 3 Plex API ' +
                '("pip3 install plexapi")')
        except Exception as ex2:
            print(f'Unable to connect to Plex server at {plex_server}')


def enqueue_files(files: list):

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
        print('processing ' + path)
        minfo = fetch_details(path)
        if minfo.vcodec is not None:
            if forced_profile is None:
                matched_profile, rule = match_profile(minfo)
                if matched_profile is None:
                    print(f'No matching profile found - skipped')
                    continue
                if matched_profile.upper() == 'SKIP':
                    print(f'Skipping due to profile rule: {rule}')
                    complete.add(path)
                    continue
                if matched_profile not in profiles:
                    print(f'profile "{matched_profile}" referenced from rule "{rule}" not found')
                    exit(1)
                the_profile = profiles[matched_profile]
                outpath = path[0:path.rfind('.')] + the_profile['extension'] + '.tmp'
                thread_queue.put((path, outpath, matched_profile))
            else:
                #
                # looks good, add this file to the thread queue
                #
                the_profile = profiles[forced_profile]
                outpath = path[0:path.rfind('.')] + the_profile['extension'] + '.tmp'
                thread_queue.put((path, outpath, forced_profile))

            # if vcodec in ('hevc', 'x265', 'h265'):
            #     print('found h265, skipping: ' + path)
            #     complete.add(path)
            #     continue
            # if int(res_height) < 720:
            #     print('low resolution video will not be transcoded')
            #     complete.add(path)
            #     continue

if __name__ == '__main__':

    if len(sys.argv) == 2 and sys.argv[1] == '-h':
        print('usage: {} [OPTIONS]'.format(sys.argv[0], ))
        print('  or   {} [OPTIONS] --from-file <filename>'.format(sys.argv[0], ))
        print('  or   {} [OPTIONS] file ...'.format(sys.argv[0], ))
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
        sys.exit(0)

    files = list()
    profile = None
    queue_path = None
    if len(sys.argv) > 1:
        files = []
        arg = 1
        while arg < len(sys.argv):
            if sys.argv[arg] == '--from-file':
                queue_path = sys.argv[arg + 1]
                arg += 1
                tmpfiles = loadq(queue_path)
                files.extend([(f, profile) for f in tmpfiles])
            elif sys.argv[arg] == '-p':
                profile = sys.argv[arg + 1]
                arg += 1
            elif sys.argv[arg] == '-y':
                arg += 1
                load_config(sys.argv[arg])
            elif sys.argv[arg] == '-s':
                concurrent_jobs = 1
            elif sys.argv[arg] == '-k':
                keep_source = True
            elif sys.argv[arg] == '--dry-run':
                dry_run = True
            elif sys.argv[arg] == '-v':
                verbose = True
            else:
                files.append((sys.argv[arg], profile))
            arg += 1

    if len(profiles) == 0:
        load_config(DEFAULT_CONFIG)

    if len(files) == 0 and queue_path is None and 'default_queue_file' in config:
        queue_path = config['default_queue_file']
        tmpfiles = loadq(queue_path)
        files.extend([(f, profile) for f in tmpfiles])

    if files is None:
        exit(0)

    enqueue_files(files)
    print()

    #
    # all files are listed in the queue so start the threads
    #
    jobs = list()
    concurrent_jobs = min(concurrent_jobs, thread_queue.qsize())
    for _ in range(concurrent_jobs):
        t = Thread(target=perform_transcodes)
        jobs.append(t)
        t.start()

    # wait for all jobs to complete
    thread_queue.join()

    if not dry_run and queue_path is not None:
        # pick up any newly added files
        files = set(loadq(queue_path))
        files = files - complete
        if len(files) > 0:
            with open(queue_path, 'w') as f:
                for path in files:
                    f.write(path + '\n')
        else:
            os.remove(queue_path)

    notify_plex()



SAMPLE_YAML = """
##
# global configuration
##
config:
  default_queue_file: '/volume1/config/sonarr/transcode_queue.txt'
  ffmpeg: '/usr/bin/ffmpeg'
  concurrent_jobs: 2
  plex_server: null           # can be 'server:port'

##
# profile definitions.  You can model all your transcoding combinations here.
##
profiles:
  hevc_hd_preserved:          # what I use for almost everything
      input_options: |
        -hide_banner
        -nostats
        -loglevel quiet
        -hwaccel cuvid
      output_options: |
        -c:v hevc_nvenc
        -profile:v main
        -preset medium
        -crf 20
        -c:a copy
        -c:s copy
        -f matroska
      extension: '.mkv'

  hevc_25fps:               # when movie source is just too big, cut down fps
      input_options: |
         -hide_banner
         -nostats
         -loglevel quiet
         -hwaccel cuvid
      output_options: |
        -c:v hevc_nvenc
        -profile:v main
        -preset medium
        -crf 20
        -c:a copy
        -c:s copy
        -f matroska
        -r 25
      extension: '.mkv'

  hevc_30fps:               # when movie source is just too big, cut down fps
      input_options: |
         -hide_banner
         -nostats
         -loglevel quiet
         -hwaccel cuvid
      output_options: |
        -c:v hevc_nvenc
        -profile:v main
        -preset medium
        -crf 20
        -c:a copy
        -c:s copy
        -f matroska
        -r 30
      extension: '.mkv'

  hevc_hd_lq:                 # lower quality, for when source material isn't that good anyhow
      input_options: |
         -hide_banner
         -nostats
         -loglevel quiet
         -hwaccel cuvid
      output_options: |
        -c:v hevc_nvenc
        -profile:v main
        -preset medium
        -crf 23
        -c:a copy
        -c:s copy
        -f matroska
      extension: '.mkv'
  x264:                    # basic x264 transcode using CPU (no CUDA support)
      input_options: |
         -hide_banner
         -nostats
         -loglevel quiet
      output_options: |
        -c:v x264
        -crf 22
        -c:a copy
        -c:s copy
        -f mp4
      extension: '.mp4'

#
# Automatching happens when a profile isn't provided on the command line.  These rules are evalulated to find the
# most appropriate profile for each video to be transcoded.
#
# rule predicates:
#
#            vcodec         Video codec of the source ('ffmpeg -codecs' to see full list), may preceed with ! for not-equal test
#            res_height     Source video resolution height, operators < and > allowed
#            res_width      Source video resolution width, operators < and > allowed
#            filesize_mb    Size of the source file (in megabytes), operators allowed
#            runtime        Source runtime in minutes, operators allowed
#            fps            Framerate of the source
#            path           Full path of the source file. Value can be a regular expression (ie. '.*/Television/.*').
#
# Rules are evaluated in order.  First matching rule wins so order wisely.
# Rules with a profile of "SKIP" mean to skip processing of the matched video
#
rules:
  'skip video if already encoded in hevc/h265':
      profile: SKIP
      rules:
        vcodec: 'hevc'

  'high frame rate':
      profile: hevc_30fps
      rules:
        fps: '>30'
        filesize_mb: '>500'

  'skip video if resolution < 700':
      profile: SKIP
      rules:
        res_height: '<700'

  'content just too big and framey':
      profile: hevc_hd_25fps
      rules:
        runtime:      '<180'      # less than 3 hours
        filesize_mb:  '>6000'  # ..and larger than 6 gigabytes
        fps: '>25'

  'default':    # this will be the DEFAULT (no rules implies a match)
      profile: hevc_hd_preserved
      rules:
        vcodec: '!hevc'



"""
