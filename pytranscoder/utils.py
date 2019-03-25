import math
import os
import platform
from typing import Dict

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
    if platform.system() == 'Windows':
        return 'win10'
    elif platform.system() == 'Linux':
        return 'linux'
    elif platform.system() == 'Darwin':
        return 'macos'
    return 'unknown'


def calculate_progress(info: MediaInfo, stats: Dict) -> (int, int):
    pct_done = int((stats['time'] / info.runtime) * 100)

    # extrapolate current compression %

    filesize = info.filesize_mb * 1024000
    pct_source = int(filesize * (pct_done / 100.0))
    pct_dest = int((stats['size'] / pct_source) * 100)
    pct_comp = 100 - pct_dest

    return pct_done, pct_comp
