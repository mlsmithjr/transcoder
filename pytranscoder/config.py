import sys
from typing import Dict, Any

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
        if configuration is not None:
            yml = None
            if isinstance(configuration, Dict):
                yml = configuration
            else:
                with open(configuration, 'r') as f:
                    yml = yaml.load(f)
            self.settings = yml['config']
            if 'queues' not in self.settings:
                print('"queues" definition missing from transcode.yml configuration file')
                sys.exit(1)

            for name, profile in yml['profiles'].items():
                self.profiles[name] = Profile(name, profile)

            for name, rule in yml['rules'].items():
                self.rules[name] = Rule(name, rule)

            if 'queues' in self.settings:
                self.queues = self.settings['queues']
            else:
                self.queues = list()

    def has_queue(self, name) -> bool:
        return name in self.queues

    def has_profile(self, profile_name) -> bool:
        return profile_name in self.profiles

    def get_profile(self, profile_name) -> Profile:
        return self.profiles.get(profile_name, None)

    def match_rule(self, media_info: MediaInfo, restrict_profiles=None) -> Rule:
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

