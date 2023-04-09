
from __future__ import annotations
from typing import Dict, List, Optional, Any


class Directives:
    def name(self) -> str:
        pass

    def extension(self) -> str:
        pass

    def input_options_list(self) -> List[str]:
        pass

    def output_options_list(self, config, mixins=None) -> List[str]:
        pass

    def threshold_check(self) -> int:
        pass

    def queue_name(self) -> str:
        pass

    def threshold(self) -> int:
        pass

    def stream_map(self, video_stream: str, audio: List, subtitle: List) -> List[str]:
        pass


class Options:
    def __init__(self, opts: List = None):
        self.options = list()
        if opts:
            if isinstance(opts, str):
                self.options.append(opts)
            else:
                self.merge(opts)

    def merge(self, parent):
        pdict = {}
        child: List = self.options
        if isinstance(parent, List):
            parent: List = parent
        else:
            parent: List = parent.options
        # prep the parent list for easy search/replace
        for p in parent:
            tmp = p.split()
            if len(tmp) == 2:
                pdict[tmp[0]] = tmp[1]
            else:
                pdict[tmp[0]] = None

        # check child options against parent, replacing as needed
        for child_opt in child:
            tmp = child_opt.split()
            if len(tmp) == 2:
                if tmp[1]:
                    pdict[tmp[0]] = tmp[1]
            else:
                pdict[tmp[0]] = None

        new_opts = []
        for k, v in pdict.items():
            if v:
                new_opts.append(k + ' ' + v)
            else:
                new_opts.append(k)
        self.options = new_opts

    def remove(self, opt: str):
        for o in self.options:
            if o.split()[0] == opt:
                self.options.remove(o)
                break

    def as_list(self):
        return list(self.options)

    def as_shell_params(self) -> List:
        z = []
        for o in self.options:
            for t in o.split():
                z.append(t)
        return z


class Profile(Directives):
    def __init__(self, name: str, profile: Optional[Dict] = None):
        self.profile: Dict[str, Any] = profile
        self._name = name

        if not profile:
            self.profile: Dict[str, Any] = dict()

        if "input_options" in self.profile:
            self.profile["input_options"] = Options(profile["input_options"])
        else:
            self.profile["input_options"] = Options()

        if "output_options" in self.profile:
            self.profile["output_options"] = Options(profile["output_options"])
        else:
            self.profile["output_options"] = Options()

        for section in ['audio', 'video', 'subtitle']:
            section_name = f'output_options_{section}'
            if section_name in self.profile:
                self.profile[section_name] = Options(profile[section_name])

    def get(self, key: str):
        return self.profile.get(key, None)

    def name(self) -> str:
        return self._name

    def input_options_list(self) -> List[str]:
        return self.profile["input_options"].as_shell_params()

    #ooutput = self._manager.config.output_from_profile(_profile, job.mixins)

    @property
    def output_options(self) -> Options:
        return self.profile["output_options"]

    @property
    def output_options_audio(self) -> Options:
        return self.profile.get("output_options_audio", None)

    @property
    def output_options_video(self) -> Options:
        return self.profile.get("output_options_video", None)

    @property
    def output_options_subtitle(self) -> Options:
        return self.profile.get("output_options_subtitle", None)

    def extension(self) -> str:
        return self.profile['extension']

    def queue_name(self) -> str:
        return self.profile.get('queue', None)

    def threshold(self) -> int:
        return self.profile.get('threshold', 0)

    def threshold_check(self) -> int:
        return self.profile.get('threshold_check', 100)

    @property
    def include_profiles(self) -> List[str]:
        alist: str = self.profile.get('include', None)
        if alist is None:
            return []
        return alist.split()

    def include(self, parent):      # accepts dict or Profile object
        # overlay this profile settings on top of parent profile to make a new one
        if isinstance(parent, dict):
            p = dict(parent)
        else:
            p = dict(parent.profile)
        for k, v in p.items():
            if k in self.profile:
                if isinstance(v, Options):
                    if isinstance(self.profile[k], Options):
                        # merge existing key values
                        self.profile[k].merge(v)
                    else:
                        # replace
                        self.profile[k] = v
                else:
                    # keep child value
                    continue
            else:
                self.profile[k] = v

        return self

    def included_audio(self) -> list:
        audio_section = self.profile.get('audio')
        if audio_section is None:
            return []
        return audio_section.get('include_languages', [])

    def excluded_audio(self) -> list:
        audio_section = self.profile.get('audio')
        if audio_section is None:
            return []
        return audio_section.get('exclude_languages', [])

    def included_subtitles(self) -> list:
        subtitle_section = self.profile.get('subtitle')
        if subtitle_section is None:
            return []
        return subtitle_section.get('include_languages', [])

    def excluded_subtitles(self) -> list:
        subtitle_section = self.profile.get('subtitle')
        if subtitle_section is None:
            return []
        return subtitle_section.get('exclude_languages', [])

    def default_audio(self) -> Optional[str]:
        audio_section = self.profile.get('audio')
        if audio_section is None:
            return None
        return audio_section.get('default_language', [])

    def default_subtitle(self) -> Optional[str]:
        subtitle_section = self.profile.get('subtitle')
        if subtitle_section is None:
            return None
        return subtitle_section.get('default_language', [])

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

    def stream_map(self, video_stream: str, audio: List, subtitle: List) -> list:
        excl_audio = self.excluded_audio()
        excl_subtitle = self.excluded_subtitles()
        incl_audio = self.included_audio()
        incl_subtitle = self.included_subtitles()

        defl_audio = self.default_audio()
        defl_subtitle = self.default_subtitle()

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
        seq_list.append(f'0:{video_stream}')
        audio_streams = self._map_streams("a", audio, excl_audio, incl_audio, defl_audio)
        subtitle_streams = self._map_streams("s", subtitle, excl_subtitle, incl_subtitle, defl_subtitle)
        return seq_list + audio_streams + subtitle_streams

    @staticmethod
    def find_mixin_section(mixins: List[Profile], mixin_type: str):
        for mixin in mixins:
            section_name = f'output_options_{mixin_type}'
            if section_name in mixin.profile:
                section = mixin.profile[section_name]
                # mixins only allow one override, so take the first we find
                return section.as_shell_params()
        return []

    def output_options_list(self, config, mixins=None) -> List[str]:
        # start with output_options (not mixable)
        output_opt = self.output_options.as_shell_params()
        mixin_profiles = config.find_mixins(mixins)
        for section in ['audio', 'video', 'subtitle']:
            section_name = f'output_options_{section}'
            if section_name in self.profile:
                # we have a mixin-enabled section - see if there are mixins to apply
                options = self.find_mixin_section(mixin_profiles, section)
                if len(options) > 0:
                    output_opt.extend(options)
                else:
                    # no mixin override, just use the section in the profile
                    output_opt.extend(self.profile[section_name].as_shell_params())
        return output_opt
