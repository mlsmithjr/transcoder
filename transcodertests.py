import re
import shutil
import unittest
import os
from typing import Dict

from pytranscoder.cluster import manage_clusters, RemoteHostProperties
from pytranscoder.config import ConfigFile
from pytranscoder.media import MediaInfo, status_re
from pytranscoder.transcode import LocalHost
from pytranscoder.utils import files_from_file, get_local_os_type


class TranscoderTests(unittest.TestCase):

    def test_ffmpeg_status_regex(self):
        sample = 'frame=  307 fps= 86 q=-0.0 size=    3481kB time=00:00:13.03 bitrate=2187.9kbits/s speed=3.67x   \n'
        match = status_re.match(sample)
        self.assertIsNotNone(match, 'no ffmpeg status match')
        self.assertTrue(len(match.groups()) == 5, 'Expected 5 matches')

    def test_loadconfig(self):
        config = ConfigFile('transcode.yml')
        self.assertIsNotNone(config.settings, 'Config object not loaded')
        self.assertEqual(len(config.queues), 2, 'Expected 2 queues')

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

    def test_loc_os(self):
        self.assertEqual(get_local_os_type(), 'linux', 'Expected linux as os type')

    def test_path_substitutions(self):
        config: Dict = self.get_setup()
        props = RemoteHostProperties('m1', config['config']['clusters']['cluster1']['m1'])
        intest, outtest = props.substitute_paths('/volume2/test.in', '/volume2/test.out')
        self.assertEqual(intest, '/media/test.in', 'Path substitution failed on input path')
        self.assertEqual(outtest, '/media/test.out', 'Path substitution failed on output path')

    def test_local_host_setup(self):
        config: Dict = self.get_setup()
        host = LocalHost(ConfigFile(config))
        self.assertEqual(len(host.queues), 3, 'Expected 3 queues configured')

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
                            'os': 'linux',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'path-substitutions': [
                                '/v2/ /m2/',
                                '/volume2/ /media/'
                            ],
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
                            'os': 'linux',
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
