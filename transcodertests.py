import unittest
from transcoder import transcode
import os

class TranscoderTests(unittest.TestCase):

    def setup(self):
        transcode.load_config('transcode.yml')

    def test_loadconfig(self):
        self.setup()
        self.assertIsNotNone(transcode.config, 'Config object not loaded')

    def test_loadqueue(self):
        self.setup()
        testpath = '/tmp/transcode_parsertest_loadqueue.tmp'
        with open(testpath, 'w') as t:
            t.write('one\ntwo\nthree')
        files = transcode.loadq(testpath)
        self.assertTrue(len(files) == 3, 'did not load file queue properly')
        os.remove(testpath)

    def test_mediainfo(self):
        self.setup()
        with open('tests/ffmpeg.out', 'r') as ff:
            info = transcode.parse_details('/dev/null', ff.read())
            self.assertIsNotNone(info)
            self.assertEqual(info.vcodec, 'h264')
            self.assertEqual(info.res_width, 1280)
            self.assertEqual(info.fps, 23)
            self.assertEqual(info.runtime, (2 * 60) + 9)
            self.assertEqual(info.path, '/dev/null')

    def test_default_profile(self):
        self.setup()
        with open('tests/ffmpeg.out', 'r') as ff:
            info = transcode.parse_details('/dev/null', ff.read())
            info.filesize_mb = 1000
            info.res_height = 720
            matched_profile, rule = transcode.match_profile(info)
            self.assertEqual(matched_profile, 'hevc_hd_preserved')
            self.assertEqual(rule, 'default')

    def test_skip_profile(self):
        self.setup()
        with open('tests/ffmpeg.out', 'r') as ff:
            info = transcode.parse_details('/dev/null', ff.read())
            info.filesize_mb = 1000
            matched_profile, rule = transcode.match_profile(info)
            self.assertEqual(matched_profile, 'SKIP')


if __name__ == '__main__':
    unittest.main()
