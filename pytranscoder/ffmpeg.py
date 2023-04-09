import datetime
import os
import re
import subprocess
import sys
import threading
from pathlib import PurePath
from random import randint
from tempfile import gettempdir
from typing import Dict, Any, Optional
import json

from pytranscoder.media import MediaInfo
from pytranscoder.processor import Processor

status_re = re.compile(
    r'^.* fps=\s*(?P<fps>.+?) q=(?P<q>.+\.\d) size=\s*(?P<size>\d+?)kB time=(?P<time>\d\d:\d\d:\d\d\.\d\d) .*speed=(?P<speed>.*?)x')

_CHARSET: str = sys.getdefaultencoding()


class FFmpeg(Processor):

    def __init__(self, ffmpeg_path: str):
        super().__init__(ffmpeg_path)
        self.monitor_interval = 30

    def fetch_details(self, _path: str) -> MediaInfo:
        """Use ffmpeg to get media information

        :param _path:   Absolute path to media file
        :return:        Instance of MediaInfo
        """
        with subprocess.Popen([self.path, '-i', _path], stderr=subprocess.PIPE) as proc:
            output = proc.stderr.read().decode(encoding='utf8')
            mi = MediaInfo.parse_ffmpeg_details(_path, output)
            if mi.valid:
                return mi
        # try falling back to ffprobe, if it exists
        try:
            return self.fetch_details_ffprobe(_path)
        except Exception as ex:
            print("Unable to fallback to ffprobe - " + str(ex))
            return MediaInfo(None)

    def fetch_details_ffprobe(self, _path: str) -> MediaInfo:
        ffprobe_path = str(PurePath(self.path).parent.joinpath('ffprobe'))
        if not os.path.exists(ffprobe_path):
            return MediaInfo(None)

        args = [ffprobe_path, '-v', '1', '-show_streams', '-print_format', 'json', '-i', _path]
        with subprocess.Popen(args, stdout=subprocess.PIPE) as proc:
            output = proc.stdout.read().decode(encoding='utf8')
            info = json.loads(output)
            return MediaInfo.parse_ffmpeg_details_json(_path, info)

    def monitor_ffmpeg(self, proc: subprocess.Popen):
        diff = datetime.timedelta(seconds=self.monitor_interval)
        event = datetime.datetime.now() + diff

        #
        # Create a transaction log for this run, to be left behind if an error is encountered.
        #
        suffix = randint(100, 999)
        self.log_path: PurePath = PurePath(gettempdir(), 'pytranscoder-' + threading.current_thread().getName() + '-' +
                                           str(suffix) + '.log')

        with open(str(self.log_path), 'w') as logfile:
            while proc.poll() is None:
                line = proc.stdout.readline()
                logfile.write(line)
                logfile.flush()

                match = status_re.match(line)
                if match is not None and len(match.groups()) >= 5:
                    if datetime.datetime.now() > event:
                        event = datetime.datetime.now() + diff
                        info: Dict[str, Any] = match.groupdict()

                        info['size'] = int(info['size'].strip()) * 1024
                        hh, mm, ss = info['time'].split(':')
                        ss = ss.split('.')[0]
                        info['time'] = (int(hh) * 3600) + (int(mm) * 60) + int(ss)
                        yield info

        if proc.returncode == 0:
            # if we got here then everything went fine, so remove the transaction log
            try:
                os.remove(str(self.log_path))
            except Exception:
                pass
            self.log_path = None

    def monitor_agent(self, sock):
        diff = datetime.timedelta(seconds=self.monitor_interval)
        event = datetime.datetime.now() + diff
        while True:
            c = sock.recv(1024).decode()
            if c.startswith("DONE|") or c.startswith("ERR|"):
                print("Transcode complete, receiving results..")
                # found end of processing marker
                try:
                    os.remove(str(self.log_path))
                    self.log_path = None
                except Exception:
                    pass

                yield c

            sock.send(bytes("ACK!".encode()))
            line = c

            match = status_re.match(line)
            if match is not None and len(match.groups()) >= 5:
                if datetime.datetime.now() > event:
                    event = datetime.datetime.now() + diff
                    info: Dict[str, Any] = match.groupdict()

                    info['size'] = int(info['size'].strip()) * 1024
                    hh, mm, ss = info['time'].split(':')
                    ss = ss.split('.')[0]
                    info['time'] = (int(hh) * 3600) + (int(mm) * 60) + int(ss)
                    yield info

    def run(self, params, event_callback) -> Optional[int]:
        return self.execute_and_monitor(params, event_callback, self.monitor_ffmpeg)

    def run_remote(self, sshcli: str, user: str, ip: str, params: list, event_callback) -> Optional[int]:
        return self.remote_execute_and_monitor(sshcli, user, ip, params, event_callback, self.monitor_ffmpeg)
