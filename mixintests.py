import unittest

from pytranscoder.config import ConfigFile


class MixinTests(unittest.TestCase):
    def test_loaded(self):
        config = self.get_setup()
        profiles = config.find_mixins(['mixin1'])
        self.assertEqual(len(profiles), 1, "expected 1 profile")

    def test_mixin_enabled(self):
        config = self.get_setup()
        profile = config.get_directive('profile1')
        options = profile.output_options_audio
        self.assertIsNotNone(options, "expected output_options_audio in profile1 via include")
        self.assertEqual(['-c:a', 'copy'], options.as_shell_params(), "Invalid inherited audio options")

    def test_audio_mixin(self):
        config = self.get_setup()
        profile = config.get_directive('profile1')
        options = config.output_from_profile(profile, ['mixin1'])
        expect = ['-c:v', 'copy', '-f', 'matroska', '-threads', '4', '-c:a', 'mp3lame', '-b:a', '384k', '-c:s', 'copy']
        self.assertEqual(expect, options, "Output options mismatch (audio)")

    def test_video_mixin(self):
        config = self.get_setup()
        profile = config.get_directive('profile2')
        options = config.output_from_profile(profile, ['mixin2'])
        expect = ['-c:s', 'copy', '-f', 'matroska', '-threads', '4', '-c:a', 'copy',
                  '-aaa', 'bbb', '-ccc', 'ddd', '-eee', 'fff']
        self.assertEqual(expect, options, "Output options mismatch (video)")

    def test_subtitle_mixin(self):
        config = self.get_setup()
        profile = config.get_directive('profile1')
        options = config.output_from_profile(profile, ['mixin3'])
        expect = ['-c:v', 'copy', '-f', 'matroska', '-threads', '4', '-c:a', 'copy', "-vf", "subtitles=subtitle.srt"]
        self.assertEqual(expect, options, "Output options mismatch (subtitle)")

    def test_multi_mixin(self):
        config = self.get_setup()
        profile = config.get_directive('profile2')
        options = config.output_from_profile(profile, ['mixin2', 'mixin1'])
        expect = ['-c:s', 'copy', '-f', 'matroska', '-threads', '4', '-c:a', 'mp3lame', '-b:a', '384k',
                  '-aaa', 'bbb', '-ccc', 'ddd', '-eee', 'fff']
        self.assertEqual(expect, options, "Output options mismatch (video)")

    def test_multi_mixin_all(self):
        config = self.get_setup()
        profile = config.get_directive('profile3')
        options = config.output_from_profile(profile, ['mixin2', 'mixin1', 'mixin3'])
        expect = ['-f', 'matroska', '-threads', '4', '-c:a', 'mp3lame', '-b:a', '384k',
                  '-aaa', 'bbb', '-ccc', 'ddd', '-eee', 'fff', "-vf", "subtitles=subtitle.srt"]
        self.assertEqual(expect, options, "Output options mismatch (video)")

    def test_mixins_do_not_combine(self):
        config = self.get_setup()
        profile = config.get_directive('profile2')
        self.assertEqual(["-c:v", "hevc_x264"], profile.output_options_video.as_shell_params(), "mixin inheritance failed")

    @staticmethod
    def get_setup():
        return ConfigFile('tests/mixinstest.yml')


if __name__ == '__main__':
    unittest.main()
