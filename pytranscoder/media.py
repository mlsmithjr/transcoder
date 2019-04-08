import csv
import os
import re
from pathlib import Path

from pytranscoder import verbose
from pytranscoder.profile import Profile

video_re = re.compile(r'^.*Duration: (\d+):(\d+):.* Stream .*: Video: (\w+).*, (\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
                      re.DOTALL)


class MediaInfo:

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

    @staticmethod
    def parse_details(_path, output):
        match = video_re.match(output)
        if match is None or len(match.groups()) < 6:
            print(f'>>>> regex match on video stream data failed: ffmpeg -i {_path}')
            return MediaInfo(_path, None, 0, 0, 0, 0, 0, None)
        else:
            _dur_hrs, _dur_mins, _codec, _colorspace, _res_width, _res_height, fps = match.group(1, 2, 3, 4, 5, 6, 7)
            filesize = os.path.getsize(_path) / (1024 * 1024)
            return MediaInfo(_path, _codec, int(_res_width), int(_res_height), (int(_dur_hrs) * 60) + int(_dur_mins),
                             filesize, int(fps), _colorspace)

    def log_stats(self, profile: Profile):
        try:
            name = Path.home() / '.pytranscoder-ml.csv'
            with open(str(name), 'a+') as statsfile:
                csv_file = csv.writer(statsfile, quoting=csv.QUOTE_NONNUMERIC)
                new_filesize = os.path.getsize(self.path) / (1024 * 1024)
                row = [self.path, self.vcodec, self.res_height, self.runtime, self.filesize_mb,
                       new_filesize, self.fps, self.colorspace, profile.name]
                csv_file.writerow(row)
        except Exception:
            print('Unable to write to ~/.pytranscoder-ml.csv')
