import datetime
import re
import subprocess
from typing import Dict, Any

from pytranscoder import verbose
from pytranscoder.media import MediaInfo

status_re = re.compile(
    r'^.* fps=\s*(?P<fps>.+?) q=(?P<q>.+\.\d) size=\s*(?P<size>\d+?)kB time=(?P<time>\d\d:\d\d:\d\d\.\d\d) .*speed=(?P<speed>.*?)x')


class FFmpeg:

    def __init__(self, ffmpeg_path):
        self.ffmpeg = ffmpeg_path

    def fetch_details(self, _path: str) -> MediaInfo:
        """Use ffmpeg to get media information

        :param _path:   Absolute path to media file
        :return:        Instance of MediaInfo
        """
        with subprocess.Popen([self.ffmpeg, '-i', _path], stderr=subprocess.PIPE) as proc:
            output = proc.stderr.read().decode(encoding='utf8')
            return MediaInfo.parse_details(_path, output)

    @staticmethod
    def monitor_ffmpeg(proc: subprocess.Popen):
        diff = datetime.timedelta(seconds=30)
        event = datetime.datetime.now() + diff
        while proc.poll() is None:
            line = proc.stdout.readline()
            if verbose:
                print(line, end='')
            match = status_re.match(line)
            if match is not None and len(match.groups()) >= 5:
                if datetime.datetime.now() > event:
                    event = datetime.datetime.now() + diff
                    info: Dict[str, Any] = match.groupdict()
                    info['size'] = int(info['size'].strip()) * 1024
                    hh, mm, ss = info['time'].split(':')
                    info['time'] = (int(hh) * 60) + int(mm)
                    yield info

    def run(self, params, event_callback) -> subprocess.Popen:
        with subprocess.Popen([self.ffmpeg,
                               *params],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True,
                              shell=False) as p:
            for stats in FFmpeg.monitor_ffmpeg(p):
                if event_callback is not None:
                    event_callback(stats)
            return p

    def run_remote(self, sshcli: str, user: str, ip: str, params: list, event_callback) -> subprocess.Popen:
        cli = [sshcli, user + '@' + ip, self.ffmpeg, *params]
        with subprocess.Popen(cli,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True,
                              shell=False) as p:
            for stats in FFmpeg.monitor_ffmpeg(p):
                if event_callback is not None:
                    event_callback(stats)
            return p
