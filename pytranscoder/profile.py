from typing import Dict


class Profile:
    name: str
    profile: Dict

    def __init__(self, name: str, profile: Dict):
        self.profile = profile
        self.name = name

    @property
    def input_options(self) -> [str]:
        if 'input_options' in self.profile and self.profile['input_options'] is not None:
            return self.profile['input_options'].split()
        return []

    @property
    def output_options(self) -> [str]:
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
