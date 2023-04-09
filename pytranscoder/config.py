
import os
from typing import Dict, Any, Optional, List

import yaml

from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile, Directives
from pytranscoder.rule import Rule
from pytranscoder.template import Template


class ConfigFile:
    settings:   Dict
    queues:     Dict
    directives: Dict[str, Directives]
    rules:      Dict[str, Rule]

    def __init__(self, configuration: Any):
        """load configuration file (defaults to $HOME/.transcode.yml)"""

        self.directives = dict()
        self.rules = dict()
        if configuration is not None:
            if isinstance(configuration, Dict):
                yml = configuration
            else:
                if not os.path.exists(configuration):
                    print(f'Configuration file "{configuration}" not found')
                    exit(1)
                with open(configuration, 'r') as f:
                    yml = yaml.load(f, Loader=yaml.Loader)
            self.settings = yml['config']
            #
            # load profiles
            #
            if 'profiles' in yml:
                for name, profile in yml['profiles'].items():
                    p = Profile(name, profile)
                    self.directives[name] = p
                    parent_names = p.include_profiles
                    for parent_name in parent_names:
                        if parent_name not in self.directives:
                            print(f'Profile error ({name}: included "{parent_name}" not defined')
                            exit(1)
                        p.include(self.directives[parent_name])
            #
            # load templates
            #
            if "templates" in yml:
                for name, template in yml['templates'].items():
                    self.directives[name] = Template(name, template)

            if 'rules' in yml:
                for name, rule in yml['rules'].items():
                    self.rules[name] = Rule(name, rule)

            if 'queues' in self.settings:
                self.queues = self.settings['queues']
            else:
                self.queues = dict()

    def fls_path(self) -> str:
        return self.settings.get('fls_path', None)

    def colorize(self) -> bool:
        return self.settings.get('colorize', 'no').lower() == 'yes'

    def has_queue(self, name) -> bool:
        return name in self.queues

    def has_directive(self, directive_name) -> bool:
        return directive_name in self.directives

    def get_directive(self, name) -> Directives:
        return self.directives.get(name, None)

    def find_mixins(self, mixins: List[str]) -> List[Profile]:
        profiles: List[Profile] = []
        if mixins is None:
            return profiles
        for mixin in mixins:
            p = self.get_directive(mixin)
            if p:
                profiles.append(p)
        return profiles

    def match_rule(self, media_info: MediaInfo, restrict_profiles=None) -> Optional[Rule]:
        for rule in self.rules.values():
            if restrict_profiles is not None and rule.profile not in restrict_profiles:
                continue
            if rule.match(media_info):
                if rule.is_skip():
                    return rule
                if not self.has_directive(rule.profile):
                    print(f'profile "{rule.profile}" referenced from rule "{rule.name}" not found')
                    exit(1)
                return rule
        return None

    @property
    def ffmpeg_path(self):
        return self.settings['ffmpeg']

    @property
    def ssh_path(self):
        return self.settings.get('ssh', '/usr/bin/ssh')

    @property
    def default_queue_file(self):
        return self.settings.get('default_queue_file', None)

    def add_rule(self, name, rule: Rule):
        self.rules[name] = rule

    @property
    def automap(self) -> bool:
        return self.settings.get('automap', True)
