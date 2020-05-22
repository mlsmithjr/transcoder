import subprocess
from pathlib import PurePath
from typing import Optional

from pytranscoder.media import MediaInfo


class Processor:

    def __init__(self, path: str):
        self.path = path
        self.log_path: PurePath = None
        self.last_command = ''

    @property
    def is_available(self) -> bool:
        return self.path is not None

    def is_ffmpeg(self) -> bool:
        return False

    def is_hbcli(self) -> bool:
        return False

    def fetch_details(self, _path: str) -> MediaInfo:
        return None

    def run(self, params, event_callback) -> Optional[int]:
        return None

    def run_remote(self, sshcli: str, user: str, ip: str, params: list, event_callback) -> Optional[int]:
        return None

    def execute_and_monitor(self, params, event_callback, monitor) -> Optional[int]:
        self.last_command = ' '.join([self.path, *params])
        with subprocess.Popen([self.path,
                               *params],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True,
                              shell=False) as p:

            for stats in monitor(p):
                if event_callback is not None:
                    veto = event_callback(stats)
                    if veto:
                        p.kill()
                        return None
            return p.returncode

    def remote_execute_and_monitor(self, sshcli: str, user: str, ip: str, params: list, event_callback, monitor) -> Optional[int]:
        cli = [sshcli, '-v', user + '@' + ip, self.path, *params]
        self.last_command = ' '.join(cli)
        with subprocess.Popen(cli,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True,
                              shell=False) as p:
            try:
                for stats in monitor(p):
                    if event_callback is not None:
                        veto = event_callback(stats)
                        if veto:
                            p.kill()
                            return None
                return p.returncode
            except KeyboardInterrupt:
                p.kill()
