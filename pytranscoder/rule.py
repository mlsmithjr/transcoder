import re
from typing import Dict

from pytranscoder import verbose
from pytranscoder.media import MediaInfo

valid_predicates = ['vcodec', 'res_height', 'res_width', 'runtime', 'filesize_mb', 'fps', 'path']
numeric_predicates = ['res_height', 'res_width', 'runtime', 'filesize_mb', 'fps']


class Rule:
    name: str
    profile: str
    criteria: Dict

    def __init__(self, name: str, rule: Dict):
        self.name = name
        self.profile = rule['profile']
        if 'criteria' in rule:
            self.criteria = rule['criteria']
        else:
            self.criteria = None

    def is_skip(self):
        return self.profile.upper() == 'SKIP'

    def match(self, media_info: MediaInfo) -> (str, str):
        if verbose:
            print(f' > evaluating "{self.name}"')

        if self.criteria is None:
            # no criteria section, match by default
            if verbose:
                print(f'  >> rule {self.name} selected by default (no criteria)')
            return self.profile, self.name

        for pred, value in self.criteria.items():
            inverted = False
            if pred not in valid_predicates:
                print(f'Invalid predicate {pred} in rule {self.name}')
                exit(1)
            if isinstance(value, str) and len(value) > 1 and value[0] == '!':
                inverted = True
                value = value[1:]
            if pred == 'vcodec' and not inverted and media_info.vcodec != value:
                if verbose:
                    print(f'  >> predicate vcodec ("{value}") did not match {media_info.vcodec}')
                break
            if pred == 'vcodec' and inverted and media_info.vcodec == value:
                if verbose:
                    print(f'  >> predicate vcodec ("{value}") matched {media_info.vcodec}')
                break
            if pred == 'path':
                try:
                    match = re.search(value, media_info.path)
                    if match is None:
                        if verbose:
                            print(f'  >> predicate path ("{value}") did not match {media_info.path}')
                        break
                except Exception as ex:
                    print(f'invalid regex {media_info.path} in rule {self.name}')
                    if verbose:
                        print(str(ex))
                    exit(0)

            if pred in numeric_predicates:
                comp = media_info.eval_numeric(self.name, pred, value)
                if not comp and not inverted:
                    # mismatch
                    break
                if comp and inverted:
                    # mismatch
                    break
        else:
            # didn't bail out on any predicates, have a match
            return self.profile, self.name
