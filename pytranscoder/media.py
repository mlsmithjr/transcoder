import csv
import os
import re
from pathlib import Path

from pytranscoder import verbose
from pytranscoder.profile import Profile

#video_re = re.compile(r'^.*Duration: (\d+):(\d+):.* Stream .*: Video: (\w+).*, (\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
#                      re.DOTALL)
video_re1 = re.compile(r".*Duration: (\d+):(\d+):(\d+)", re.DOTALL)
video_re2 = re.compile(r'.*Stream .+: Video: (\w+).*, (yuv\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps', re.DOTALL)


class MediaInfo:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, path, vcodec, res_width, res_height, runtime, source_size, fps, colorspace):
        self.path = path
        self.vcodec = vcodec
        self.res_height = res_height
        self.res_width = res_width
        self.runtime = runtime
        self.filesize_mb = source_size
        self.fps = fps
        self.colorspace = colorspace

    def eval_numeric(self, rulename: str, pred: str, value: str) -> bool:
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

            if pred == 'runtime':
                rangelow = str(int(rangelow) * 60)
                rangehigh = str(int(rangehigh) * 60)

            expr = f'{rangelow} <= {attr} <= {rangehigh}'
        elif value.isnumeric():
            # simple numeric equality test

            if pred == 'runtime':
                value = str(int(value) * 60)

            expr = f'{attr} == {value}'
        elif value[0] in '<>':
            op = value[0]
            value = value[1:]

            if pred == 'runtime':
                value = str(int(value) * 60)

            expr = f'{attr} {op} {value}'
        else:
            print(f'Error: Rule "{rulename}" valid value: {value}')
            return False

        if not eval(expr):
            if verbose:
                print(f'  >> predicate {pred} ("{value}") did not match {attr}')
            return False
        return True

    @staticmethod
    def parse_details(_path, output):
        match1 = video_re1.match(output)
        if match1 is None or len(match1.groups()) < 3:
            print(f'>>>> regex match on video stream data failed: ffmpeg -i {_path}')
            return MediaInfo(_path, None, 0, 0, 0, 0, 0, None)
        match2 = video_re2.match(output)
        if match2 is None or len(match2.groups()) < 4:
            print(f'>>>> regex match on video stream data failed: ffmpeg -i {_path}')
            return MediaInfo(_path, None, 0, 0, 0, 0, 0, None)

        _dur_hrs, _dur_mins, _dur_secs = match1.group(1, 2, 3)
        _codec, _colorspace, _res_width, _res_height, fps = match2.group(1, 2, 3, 4, 5)
        filesize = os.path.getsize(_path) / (1024 * 1024)
        return MediaInfo(_path, _codec, int(_res_width), int(_res_height),
                         (int(_dur_hrs) * 3600) + (int(_dur_mins) * 60) + int(_dur_secs),
                         filesize, int(fps), _colorspace)
