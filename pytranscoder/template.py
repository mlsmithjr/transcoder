
from __future__ import annotations
from typing import Dict, List, Optional, Any

from pytranscoder.profile import Directives


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


class Template(Directives):
    def __init__(self, name: str, template: Optional[Dict] = None):
        self.template: Dict[str, Any] = template
        self.name = name

        if not template:
            self.template: Dict[str, Any] = dict()

        if "cli" not in template:
            print(f'Template error ({name}: missing "cli" section')
            exit(1)

        self.cli = template["cli"]

    def input_options(self) -> List[str]:
        opt = self.cli.get("input-options", None)
        return opt or []

    def output_options(self, mixins: Optional = None) -> List[str]:
        opts = []
        vopt = self.cli.get("video-codec", None) or ""
        opts.append(*vopt.split(" "))
        aopt = self.cli.get("audio-codec", None) or ""
        opts.append(*aopt.split(" "))
        sopt = self.cli.get("subtitles", None) or ""
        opts.append(*sopt.split(" "))

        return opts


    def get(self, key: str):
        return self.template.get(key, None)

    def extension(self) -> str:
        return self.template['extension']

    def name(self) -> str:
        return self.name

    def queue_name(self) -> str:
        return self.template.get('queue', None)

    def threshold(self) -> int:
        return self.template.get('threshold', 0)

    def threshold_check(self) -> int:
        return self.template.get('threshold_check', 100)

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
