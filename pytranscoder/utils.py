import math
import os


def filter_threshold(profile, inpath, outpath):
    if 'threshold' in profile:
        # see if size reduction matches minimum requirement
        pct_threshold = profile['threshold']
        orig_size = os.path.getsize(inpath)
        new_size = os.path.getsize(outpath)
        pct_savings = 100 - math.floor((new_size * 100) / orig_size)
        if pct_savings < pct_threshold:
            return False
        return True


