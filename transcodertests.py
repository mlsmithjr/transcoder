import shutil
import unittest
import os

from pytranscoder.cluster import manage_clusters
from pytranscoder.config import ConfigFile
from pytranscoder.media import MediaInfo
from pytranscoder.utils import files_from_file


class TranscoderTests(unittest.TestCase):

    def test_loadconfig(self):
        config = ConfigFile('transcode.yml')
        self.assertIsNotNone(config.settings, 'Config object not loaded')

    def test_loadqueue(self):
        testpath = '/tmp/transcode_parsertest_loadqueue.tmp'
        with open(testpath, 'w') as t:
            t.write('one\ntwo\nthree')
        files = files_from_file(testpath)
        self.assertTrue(len(files) == 3, 'did not load file queue properly')
        os.remove(testpath)

    def test_mediainfo(self):
        with open('tests/ffmpeg.out', 'r') as ff:
            info = MediaInfo.parse_details('/dev/null', ff.read())
            self.assertIsNotNone(info)
            self.assertEqual(info.vcodec, 'h264')
            self.assertEqual(info.res_width, 1280)
            self.assertEqual(info.fps, 23)
            self.assertEqual(info.runtime, (2 * 60) + 9)
            self.assertEqual(info.path, '/dev/null')

    def test_default_profile(self):
        with open('tests/ffmpeg.out', 'r') as ff:
            info = MediaInfo.parse_details('/dev/null', ff.read())
            info.filesize_mb = 1000
            info.res_height = 720
            config = ConfigFile(self.get_setup())
            rule = config.match_rule(info)
            self.assertIsNotNone(rule, 'expected to match a rule')
            self.assertEqual(rule.profile, 'copy')
            self.assertEqual(rule.name, 'default')

    def test_skip_profile(self):
        with open('tests/ffmpeg.out', 'r') as ff:
            info = MediaInfo.parse_details('/dev/null', ff.read())
            info.filesize_mb = 499
            config = ConfigFile(self.get_setup())
            rule = config.match_rule(info)
            self.assertIsNotNone(rule, 'Expected rule match')
            self.assertTrue(rule.is_skip(), 'Expected a SKIP rule')

    def test_rule_match(self):
        info = MediaInfo(None, None, None, 1080, 45, 2300, None)
        config = ConfigFile(self.get_setup())
        rule = config.match_rule(info)
        self.assertIsNotNone(rule, 'Expected a matched profile')

    @staticmethod
    def get_setup():
        setup = {
            'config': {
                'ffmpeg': '/usr/bin/ffmpeg',
                'queues': {
                    'q1': 1,
                    'q2': 2
                },
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
                            'profiles': ['copy'],
                            'status': 'enabled',
                        },
                        'workstation': {
                            'os': 'linux',
                            'type': 'local',
                            'ip': '192.168.2.63',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'status': 'enabled',
                        }
                    },
                    'cluster2': {
                        'm2': {
                            'type': 'streaming',
                            'ip': '127.0.0.1',
                            'user': 'mark',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'working_dir': '/tmp/pytranscode-remote',
                            'profiles': ['copy'],
                            'status': 'enabled',
                        },
                    },
                },
            },
            "profiles": {
                "hevc_cuda": {
                    "input_options": None,
                    "output_options": "-threads 4 -c:v copy -c:a copy -c:s copy -f matroska",
                    "threshold": 1,
                    "extension": ".mkv",
                },
                "copy": {
                    "input_options": None,
                    "output_options": "-threads 4 -c:v copy -c:a copy -c:s copy -f matroska",
                    "threshold": 1,
                    "extension": ".mkv",
                },
            },
            "rules": {
                'too small': {
                    'profile': 'SKIP',
                    'rules': {
                        'filesize_mb': '<500'
                    }
                },
                'small enough already': {
                    'profile': 'SKIP',
                    'rules': {
                        'filesize_mb': '<2500',
                        'res_height': '720-1081',
                        'runtime': '30-65'
                    }
                },
                'default': {
                    'profile': 'copy',
                    'rules': {
                        'vcodec': '!hevc'
                    }
                }
            }
        }
        return setup

    def test_cluster_mounted(self):
        if 'TEST_VIDEO' not in os.environ:
            print('cluster test not run - no video file given in TEST_VIDEO environment variable')
            return
        mediafile = os.environ['TEST_VIDEO']
        mediaext = mediafile[-4:]
        setup = ConfigFile(self.get_setup())
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
        setup = ConfigFile(self.get_setup())
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
