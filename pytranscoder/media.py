import csv
import os
import re
from typing import Dict, Optional

from pytranscoder import verbose

#video_re = re.compile(r'^.*Duration: (\d+):(\d+):.* Stream .*: Video: (\w+).*, (\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
#                      re.DOTALL)
video_dur = re.compile(r".*Duration: (\d+):(\d+):(\d+)", re.DOTALL)
video_info = re.compile(r'.*Stream #0:(\d+)(?:\(\w+\))?: Video: (\w+).*, (yuv\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps', re.DOTALL)
audio_info = re.compile(r'.*Stream #0:(?P<stream>\d+)(\((?P<lang>\w+)\))?: Audio: (?P<format>\w+)')
subtitle_info = re.compile(r'.*Stream #0:(?P<stream>\d+)(\((?P<lang>\w+)\))?: Subtitle:')


class MediaInfo:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, info: Optional[Dict]):
        self.valid = info is not None
        if not self.valid:
            return
        self.path = info['path']
        self.vcodec = info['vcodec']
        self.stream = info['stream']
        self.res_height = info['res_height']
        self.res_width = info['res_width']
        self.runtime = info['runtime']
        self.filesize_mb = info['filesize_mb']
        self.fps = info['fps']
        self.colorspace = info['colorspace']
        self.audio = info['audio']
        self.subtitle = info['subtitle']

    def is_multistream(self) -> bool:
        return len(self.audio) > 1 or len(self.subtitle) > 1

    def ffmpeg_streams(self) -> list:
        seq_list = list()
        seq_list.append('-map')
        seq_list.append(f'0.{self.stream}')
        for s in self.audio:
            seq = s['stream']
            seq_list.append('-map')
            seq_list.append(f'0.{seq}')
        for s in self.subtitle:
            seq = s['stream']
            seq_list.append('-map')
            seq_list.append(f'0.{seq}')
        return seq_list

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
        match1 = video_dur.match(output)
        if match1 is None or len(match1.groups()) < 3:
            print(f'>>>> regex match on video stream data failed: ffmpeg -i {_path}')
            return MediaInfo(None)

        match2 = video_info.match(output)
        if match2 is None or len(match2.groups()) < 5:
            print(f'>>>> regex match on video stream data failed: ffmpeg -i {_path}')
            return MediaInfo(None)

        audio_tracks = list()
        for audio_match in audio_info.finditer(output):
            ainfo = audio_match.groupdict()
            if ainfo['lang'] is None:
                ainfo['lang'] = 'und'
            audio_tracks.append(ainfo)

        subtitle_tracks = list()
        for subt_match in subtitle_info.finditer(output):
            sinfo = subt_match.groupdict()
            if sinfo['lang'] is None:
                sinfo['lang'] = 'und'
            subtitle_tracks.append(sinfo)

        _dur_hrs, _dur_mins, _dur_secs = match1.group(1, 2, 3)
        _id, _codec, _colorspace, _res_width, _res_height, fps = match2.group(1, 2, 3, 4, 5, 6)
        filesize = os.path.getsize(_path) / (1024 * 1024)

        minfo = {
            'path': _path,
            'vcodec': _codec,
            'stream': _id,
            'res_width': int(_res_width),
            'res_height': int(_res_height),
            'runtime': (int(_dur_hrs) * 3600) + (int(_dur_mins) * 60) + int(_dur_secs),
            'filesize_mb': filesize,
            'fps': int(fps),
            'colorspace': _colorspace,
            'audio': audio_tracks,
            'subtitle': subtitle_tracks
        }
        return MediaInfo(minfo)
