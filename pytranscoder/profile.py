from typing import Dict, List, Optional


class Profile:
    name: str
    profile: Dict

    def __init__(self, name: str, profile: Dict):
        self.profile = profile
        self.name = name

    @staticmethod
    def level_options(opts: List) -> List:
        z = []
        for o in opts:
            for t in o.split():
                z.append(t)
        return z

    @property
    def input_options(self) -> [str]:
        if 'input_options' in self.profile and self.profile['input_options'] is not None:
            if isinstance(self.profile['input_options'], List):
                return Profile.level_options(self.profile['input_options'])
            return self.profile['input_options'].split()
        return []

    @property
    def output_options(self) -> [str]:
        if isinstance(self.profile['output_options'], List):
            return Profile.level_options(self.profile['output_options'])
        return self.profile['output_options'].split()

    @property
    def extension(self) -> str:
        return self.profile['extension']

    @property
    def queue_name(self) -> str:
        return self.profile.get('queue', None)

    @property
    def threshold(self) -> int:
        return self.profile.get('threshold', 0)

    @property
    def threshold_check(self) -> int:
        return self.profile.get('threshold_check', 100)

    @property
    def include_profiles(self) -> List[str]:
        alist = self.profile.get('include', None)
        if alist is None:
            return []
        return alist.split()

    @property
    def automap(self) -> bool:
        return self.profile.get('automap', True)

    @staticmethod
    def option_merge(parent: List, child: List) -> List:
        pdict = {}
        # prep the parent list for easy search/replace
        for p in parent:
            tmp = p.split()
            if len(tmp) == 2:
                pdict[tmp[0]] = tmp[1]
            else:
                pdict[p] = None

        # check child options against parent, replacing as needed
        for child_opt in child:
            tmp = child_opt.split()
            if len(tmp) == 2:
                if tmp[1]:
                    pdict[tmp[0]] = tmp[1]
            else:
                pdict[tmp] = None

        newopts = []
        for k, v in pdict.items():
            if v:
                newopts.append(k + ' ' + v)
            else:
                newopts.append(k)
        return newopts

    def include(self, parent):
        # overlay this profile settings on top of parent profile to make a new one
        p = dict(parent.profile)
        for k, v in self.profile.items():
            if k in p:
                if isinstance(p[k], List):
                    if isinstance(v, List):
                        # merge existing key values
                        #p[k] = p[k] + v
                        p[k] = self.option_merge(p[k], v)
                    else:
                        # replace
                        p[k] = v
                else:
                    # keep child value
                    p[k] = v
            else:
                p[k] = v

        self.profile = p

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
