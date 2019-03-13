import os
import re
import subprocess

from pytranscoder import verbose


video_re = re.compile(r'^.*Duration: (\d+):(\d+):.* Stream #0:0.*: Video: (\w+).*, (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
                      re.DOTALL)


class MediaInfo:
    filesize_mb: int
    path: str
    res_height: int
    res_width: int
    runtime: int
    fps: int
    vcodec: str

    __verbose: bool = False

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

    @staticmethod
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


def fetch_details(_path: str, ffmpeg: str) -> MediaInfo:
    """Use ffmpeg to get media information

    :param _path:   Absolute path to media file
    :param ffmpeg: Absolut path for ffmpeg
    :return:        Instance of MediaInfo
    """
    with subprocess.Popen([ffmpeg, '-i', _path], stderr=subprocess.PIPE) as proc:
        output = proc.stderr.read().decode(encoding='utf8')
        return MediaInfo.parse_details(_path, output)
