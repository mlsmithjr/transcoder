
import os
import re
from datetime import timedelta
from typing import Dict, Optional, List

from pytranscoder import verbose

#video_re = re.compile(r'^.*Duration: (\d+):(\d+):.* Stream .*: Video: (\w+).*, (\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps,.*$',
#                      re.DOTALL)
from pytranscoder.profile import Profile

video_dur = re.compile(r".*Duration: (\d+):(\d+):(\d+)", re.DOTALL)
video_info = re.compile(r'.*Stream #0:(\d+)(?:\(\w+\))?: Video: (\w+).*, (yuv\w+)[(,].* (\d+)x(\d+).* (\d+)(\.\d.)? fps', re.DOTALL)
audio_info = re.compile(r'^\s+Stream #0:(?P<stream>\d+)(\((?P<lang>\w+)\))?: Audio: (?P<format>\w+).*?(?P<default>\(default\))?$', re.MULTILINE)
subtitle_info = re.compile(r'^\s+Stream #0:(?P<stream>\d+)(\((?P<lang>\w+)\))?: Subtitle:', re.MULTILINE)


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

    def __str__(self):
        runtime = "{:0>8}".format(str(timedelta(seconds=self.runtime)))
        audios = [a['stream'] + ':' + a['lang'] + ':' + a['format'] + ':' + a['default'] for a in self.audio]
        audio = '(' + ','.join(audios) + ')'
        subs = [s['stream'] + ':' + s['lang'] + ':' + s['default'] for s in self.subtitle]
        sub = '(' + ','.join(subs) + ')'
        buf = f"MediaInfo: {self.path}, {self.filesize_mb}mb, {self.fps} fps, cs={self.colorspace}, {self.res_width}x{self.res_height}, {runtime}, c:v={self.vcodec}, audio={audio}, sub={sub}"
        return buf

    def is_multistream(self) -> bool:
        return len(self.audio) > 1 or len(self.subtitle) > 1

    def _map_streams(self, stream_type: str, streams: List, excludes: list, includes: list, defl: str) -> list:
        if excludes is None:
            excludes = []
        if not includes:
            includes = None
        seq_list = list()
        mapped = list()
        default_reassign = False
        for s in streams:
            stream_lang = s.get('lang', 'none')
            #
            # includes take precedence over excludes
            #
            if includes is not None and stream_lang not in includes:
                if s.get('default', None) is not None:
                    default_reassign = True
                continue

            if stream_lang in excludes:
                if s.get('default', None) is not None:
                    default_reassign = True
                continue

            # if we got here, map the stream
            mapped.append(s)
            seq = s['stream']
            seq_list.append('-map')
            seq_list.append(f'0:{seq}')

        if default_reassign:
            if defl is None:
                print('Warning: A default stream will be removed but no default language specified to replace it')
            else:
                for i, s in enumerate(mapped):
                    if s.get('lang', None) == defl:
                        seq_list.append(f'-disposition:{stream_type}:{i}')
                        seq_list.append('default')
        return seq_list

    def ffmpeg_streams(self, profile: Profile) -> list:
        excl_audio = profile.excluded_audio()
        excl_subtitle = profile.excluded_subtitles()
        incl_audio = profile.included_audio()
        incl_subtitle = profile.included_subtitles()

        defl_audio = profile.default_audio()
        defl_subtitle = profile.default_subtitle()

        if excl_audio is None:
            excl_audio = []
        if excl_subtitle is None:
            excl_subtitle = []
        #
        # if no inclusions or exclusions just map everything
        #
        if len(incl_audio) == 0 and len(excl_audio) == 0 and len(incl_subtitle) == 0 and len(excl_subtitle) == 0:
            return ['-map', '0']

        seq_list = list()
        seq_list.append('-map')
        seq_list.append(f'0:{self.stream}')
        audio_streams = self._map_streams("a", self.audio, excl_audio, incl_audio, defl_audio)
        subtitle_streams = self._map_streams("s", self.subtitle, excl_subtitle, incl_subtitle, defl_subtitle)
        return seq_list + audio_streams + subtitle_streams

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
                # convert to seconds
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

    @staticmethod
    def parse_details_json(_path, info):
        minone = MediaInfo(None)
        minfo = { 'audio': [], 'subtitle': []}
        if 'streams' not in info:
            return minone
        for stream in info['streams']:
            if stream['codec_type'] == 'video':
                minfo['path'] = _path
                minfo['vcodec'] = stream['codec_name']
                minfo['stream'] = str(stream['index'])
                minfo['res_width'] = stream['width']
                minfo['res_height'] = stream['height']
                minfo['filesize_mb'] = os.path.getsize(_path) / (1024 * 1024)
                fr_parts = stream['r_frame_rate'].split('/')
                fr = int(int(fr_parts[0]) / int(fr_parts[1]))
                minfo['fps'] = str(fr)
                minfo['colorspace'] = stream['pix_fmt']
                if 'duration' in stream:
                    minfo['runtime'] = int(stream['duration'])
                else:
                    if 'tags' in stream:
                        for name, value in stream['tags'].items():
                            if name[0:8] == 'DURATION':
                                hh, mm, ss = value.split(':')
                                duration = (int(float(hh)) * 3600) + (int(float(mm)) * 60) + int(float(ss))
                                minfo['runtime'] = duration
                                break

            elif stream['codec_type'] == 'audio':
                audio = dict()
                audio['stream'] = str(stream['index'])
                audio['format'] = stream['codec_name']
                audio['default'] = 0
                if 'disposition' in stream:
                    if 'default' in stream['disposition']:
                        audio['default'] = stream['disposition']['default']
                if 'tags' in stream:
                    if 'language' in stream['tags']:
                        audio['lang'] = stream['tags']['language']
                    else:
                        # derive the language
                        for name, value in stream['tags'].items():
                            if name[0:9] == 'DURATION-':
                                lang = name[9:]
                                audio['lang'] = lang
                                break
                minfo['audio'].append(audio)
            elif stream['codec_type'] == 'subrip':
                sub = dict()
                sub['stream'] = str(stream['index'])
                sub['format'] = stream['codec_name']
                sub['default'] = 0
                if 'disposition' in stream:
                    if 'default' in stream['disposition']:
                        sub['default'] = stream['disposition']['default']
                if 'tags' in stream:
                    if 'language' in stream['tags']:
                        sub['lang'] = stream['tags']['language']
                    else:
                        # derive the language
                        for name, value in stream['tags'].items():
                            if name[0:9] == 'DURATION-':
                                lang = name[9:]
                                sub['lang'] = lang
                                break
                minfo['subtitle'].append(sub)
        return MediaInfo(minfo)
