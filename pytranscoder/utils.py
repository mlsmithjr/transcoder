import importlib
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict

import pytranscoder
from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile


def filter_threshold(profile: Profile, inpath, outpath):
    if profile.threshold > 0:
        # see if size reduction matches minimum requirement
        pct_threshold = profile.threshold
        orig_size = os.path.getsize(inpath)
        new_size = os.path.getsize(outpath)
        pct_savings = 100 - math.floor((new_size * 100) / orig_size)
        if pct_savings < pct_threshold:
            return False
    return True


def files_from_file(queuepath) -> list:
    if not os.path.exists(queuepath):
        print(f'Queue file {queuepath} not found')
        return []
    with open(queuepath, 'r') as qf:
        _files = [fn.rstrip() for fn in qf.readlines()]
        return _files


def get_local_os_type():
    return {'Windows': 'win10', 'Linux': 'linux', 'Darwin': 'macos'}.get(platform.system(), 'unknown')


def calculate_progress(info: MediaInfo, stats: Dict) -> (int, int):
    # pct done calculation only works if video duration >= 1 minute
    if info.runtime > 0:
        pct_done = int((stats['time'] / info.runtime) * 100)
    else:
        pct_done = 0

    # extrapolate current compression %

    filesize = info.filesize_mb * 1024000
    pct_source = int(filesize * (pct_done / 100.0))
    if pct_source <= 0:
        return 0, 0
    pct_dest = int((stats['size'] / pct_source) * 100)
    pct_comp = 100 - pct_dest

    return pct_done, pct_comp


def run(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    output = p.communicate()[0].decode('utf-8')
    return p.returncode, output


def dump_stats(completed):

    if pytranscoder.dry_run:
        return

    paths = [p for p, _ in completed]
    max_width = len(max(paths, key=len))
    print("-" * (max_width + 9))
    for path, elapsed in completed:
        pathname = path.rjust(max_width)
        _min = int(elapsed / 60)
        _sec = int(elapsed % 60)
        print(f"{pathname}  ({_min:3}m {_sec:2}s)")
    print()


def is_mounted(filepath: Path) -> bool:
    if get_local_os_type() == "win10":
        # mounted filesystem detection not available in Windows
        return False
    p = filepath.resolve()
    for part in p.parents:
        if str(part) != str(part.root) and part.is_mount():
            return True
    return False

