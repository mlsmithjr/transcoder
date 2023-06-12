
from __future__ import annotations
from typing import Dict, List, Optional, Any

from pytranscoder.profile import Directives


class Template(Directives):
    def __init__(self, name: str, template: Optional[Dict] = None):
        self.template: Dict[str, Any] = template
        self._name = name

        if not template:
            self.template: Dict[str, Any] = dict()

        if "cli" not in template:
            print(f'Template error ({name}: missing "cli" section')
            exit(1)

        self.cli = template["cli"]

    def input_options_list(self) -> List[str]:
        opt = self.cli.get("input-options", None)
        return opt or []

    def output_options_list(self, config, mixins: Optional[List] = None) -> List[str]:
        opts = []
        vopt = self.cli.get("video-codec", None) or ""
        opts.extend(vopt.split(" "))
        aopt = self.cli.get("audio-codec", None) or ""
        opts.extend(aopt.split(" "))
        sopt = self.cli.get("subtitles", None) or ""
        opts.extend(sopt.split(" "))

        return opts

    def get(self, key: str):
        return self.template.get(key, None)

    def extension(self) -> str:
        ext = self.template.get('extension', None)
        if not ext:
            print(f"Required value for 'extension' missing in template {self.name}")
            exit(1)
        return ext

    def name(self) -> str:
        return self._name

    def queue_name(self) -> str:
        return self.template.get('queue', None)

    def threshold(self) -> int:
        return self.template.get('threshold', 0)

    def threshold_check(self) -> int:
        return self.template.get('threshold_check', 100)

    def _map_streams(self, stream_type: str, streams: List) -> list:
        seq_list = list()
        mapped = list()
        default_reassign = False
        includes = None
        if stream_type == "a":
            includes = self.template.get("audio-lang", None)
        elif stream_type == "s":
            includes = self.template.get("subtitle-lang", None)
        if includes:
            includes = includes.split(" ")
        else:
            includes = []

        for s in streams:
            stream_lang = s.get('lang', 'none')

            if len(includes) > 0 and stream_lang not in includes:
                if s.get('default', None) is not None:
                    default_reassign = True
                continue

            # if we got here, map the stream
            mapped.append(s)
            seq = s['stream']
            seq_list.append('-map')
            seq_list.append(f'0:{seq}')

        if default_reassign:
            defl = None
            if len(includes) > 1:
                # find the default, if any
                for i in includes:
                    if i[0] == "*":
                        defl = i[1:]
                        break
                else:
                    print('Warning: A default stream will be removed but no default language specified to replace it')
            else:
                defl = includes[0][1:] if includes[0][0] == '*' else includes[0]
                for i, s in enumerate(mapped):
                    if s.get('lang', None) == defl:
                        seq_list.append(f'-disposition:{stream_type}:{i}')
                        seq_list.append('default')
        return seq_list

    def stream_map(self, video_stream: str, audio: List, subtitle: List) -> List[str]:

        if len(self.template.get("audio-lang", "")) == 0 and len(self.template.get("subtitle-lang", "")) == 0:
            # default to map everything
            return ['-map', '0']

        seq_list = list()
        seq_list.append('-map')
        seq_list.append(f'0:{video_stream}')
        audio_streams = self._map_streams("a", audio)
        subtitle_streams = self._map_streams("s", subtitle)
        return seq_list + audio_streams + subtitle_streams
