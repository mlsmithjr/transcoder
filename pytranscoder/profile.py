from typing import Dict, List, Optional, Set, Any


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


class ProfileSKIP(Exception):
    pass


class Profile:
    def __init__(self, name: str, profile: Optional[Dict] = None):
        self.profile: Dict[str, Any] = profile
        self.name = name

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

    def get(self, key: str):
        return self.profile.get(key, None)

    @property
    def input_options(self) -> Options:
        return self.profile["input_options"]

    @property
    def output_options(self) -> Options:
        return self.profile["output_options"]

    @property
    def extension(self) -> str:
        return self.profile['extension']

    @extension.setter
    def extension(self, ext: str):
        self.profile["extension"] = ext

    @property
    def queue_name(self) -> str:
        return self.profile.get('queue', None)

    @queue_name.setter
    def queue_name(self, name: str):
        self.profile["queue"] = name

    @property
    def threshold(self) -> int:
        return self.profile.get('threshold', 0)

    @threshold.setter
    def threshold(self, val):
        self.profile["threshold"] = val

    @property
    def threshold_check(self) -> int:
        return self.profile.get('threshold_check', 100)

    @threshold_check.setter
    def threshold_check(self, val):
        self.profile["threshold_check"] = val

    @property
    def automap(self) -> bool:
        return self.profile.get('automap', True)

    @automap.setter
    def automap(self, val: bool):
        self.profile["automap"] = val

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
