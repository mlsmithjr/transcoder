import sys
import os
from typing import Dict, Any, Optional

import yaml

from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile
from pytranscoder.rule import Rule


class ConfigFile:
    settings:   Dict
    queues:     Dict
    profiles:   Dict[str, Profile]
    rules:      Dict[str, Rule]

    def __init__(self, configuration: Any):
        """load configuration file (defaults to $HOME/.transcode.yml)"""

        self.profiles = dict()
        self.rules = dict()
        yml = None
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
            for name, profile in yml['profiles'].items():
                self.profiles[name] = Profile(name, profile)
                parent_names = self.profiles[name].include_profiles
                for parent_name in parent_names:
                    if parent_name not in self.profiles:
                        print(f'Profile error ({name}: included "{parent_name}" not defined')
                        exit(1)
                    self.profiles[name].include(self.profiles[parent_name])

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

    def has_profile(self, profile_name) -> bool:
        return profile_name in self.profiles

    def get_profile(self, profile_name) -> Profile:
        return self.profiles.get(profile_name, None)

    def match_rule(self, media_info: MediaInfo, restrict_profiles=None) -> Optional[Rule]:
        for rule in self.rules.values():
            if restrict_profiles is not None and rule.profile not in restrict_profiles:
                continue
            if rule.match(media_info):
                if rule.is_skip():
                    return rule
                if not self.has_profile(rule.profile):
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
    def plex_server(self):
        return self.settings.get('plex_server', None)

    @property
    def default_queue_file(self):
        return self.settings.get('default_queue_file', None)

    def add_rule(self, name, rule: Rule):
        self.rules[name] = rule

    @property
    def automap(self) -> bool:
        return self.settings.get('automap', True)
