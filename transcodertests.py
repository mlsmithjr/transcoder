import shutil
import unittest
from pytranscoder import transcode
import os

from pytranscoder.cluster import manage_clusters
from pytranscoder.transcode import MediaInfo, match_profile


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
        rule = {
            'too small': {
                'profile': 'SKIP',
                'rules': {
                    'filesize_mb': '<500'
                }
            },
            'default': {
                'profile': 'hevc_cuda',
                'rules': {
                    'vcodec': '!hevc'
                }
            }
        }
        with open('tests/ffmpeg.out', 'r') as ff:
            info = transcode.parse_details('/dev/null', ff.read())
            info.filesize_mb = 1000
            info.res_height = 720
            matched_profile, rule = transcode.match_profile(info, rule)
            self.assertEqual(matched_profile, 'hevc_cuda')
            self.assertEqual(rule, 'default')

    def test_skip_profile(self):
        self.setup()
        rule = {
            'too small': {
                'profile': 'SKIP',
                'rules': {
                    'filesize_mb': '<1100'
                }
            }
        }
        with open('tests/ffmpeg.out', 'r') as ff:
            info = transcode.parse_details('/dev/null', ff.read())
            info.filesize_mb = 1000
            matched_profile, rule = transcode.match_profile(info, rule)
            self.assertEqual(matched_profile, 'SKIP')

    def test_rule_match(self):
        rule = {
            'small enough already': {
                'profile': 'SKIP',
                'rules': {
                    'filesize_mb': '<2500',
                    'res_height': '720-1081',
                    'runtime': '30-65'
                }
            }
        }
        info = MediaInfo(None, None, None, 1080, 45, 2300, None)
        profile, rulename = match_profile(info, rule)
        self.assertIsNotNone(profile, 'Expected a matched profile')
        self.assertIsNotNone(rulename, 'Expected a matched rule')


    def get_setup(self):
        setup = {
            'config': {
                'clusters': {
                    'cluster1': {
                        'm1': {
                            'type': 'mounted',
                            'ip': '127.0.0.1',
                            'user': 'mark',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'path-substitution': {
                                'src': '/volume2/',
                                'dest': '/media/'
                            },
                            'profile': 'copy',
                        },
                    },
                    'cluster2': {
                        'm2': {
                            'type': 'streaming',
                            'ip': '127.0.0.1',
                            'user': 'mark',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'working_dir': '/tmp/pytranscode-remote',
                            'profile': 'copy'
                        }
                    },
                },
            },
            "profiles": {
                "copy": {
                    "input_options": None,
                    "output_options": "-threads 4 -c:v copy -c:a copy -c:s copy -f matroska",
                    "extension": ".mkv",
                },
            }
        }
        return setup

    def test_cluster_mounted(self):
        if 'TEST_VIDEO' not in os.environ:
            print('cluster test not run - no video file given in TEST_VIDEO environment variable')
            return
        mediafile = os.environ['TEST_VIDEO']
        mediaext = mediafile[-4:]
        setup = self.get_setup()
        if not os.path.exists('/tmp/pytranscode-test'):
            os.mkdir('/tmp/pytranscode-test', 0o777)
        shutil.copyfile(mediafile, '/tmp/pytranscode-test/test1' + mediaext)

        testfiles = [
            ('/tmp/pytranscode-test/test1' + mediaext, 'cluster1')
        ]

        manage_clusters(testfiles, setup, False, testing=True)

    def test_cluster_streaming(self):
        if 'TEST_VIDEO' not in os.environ:
            print('cluster test not run - no video file given in TEST_VIDEO environment variable')
            return
        mediafile = os.environ['TEST_VIDEO']
        mediaext = mediafile[-4:]
        setup = self.get_setup()
        if not os.path.exists('/tmp/pytranscode-test'):
            os.mkdir('/tmp/pytranscode-test', 0o777)
        shutil.copyfile(mediafile, '/tmp/pytranscode-test/test2' + mediaext)
        if not os.path.exists('/tmp/pytranscode-remote'):
            os.mkdir('/tmp/pytranscode-remote', 0o777)

        testfiles = [
            ('/tmp/pytranscode-test/test2' + mediaext, 'cluster2')
        ]

        manage_clusters(testfiles, setup, False, testing=True)


if __name__ == '__main__':
    unittest.main()
