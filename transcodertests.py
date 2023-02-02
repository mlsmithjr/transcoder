
import unittest
import os
from typing import Dict
from unittest import mock

from pytranscoder.cluster import RemoteHostProperties, Cluster, StreamingManagedHost
from pytranscoder.config import ConfigFile
from pytranscoder.ffmpeg import status_re, FFmpeg
from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile
from pytranscoder.transcode import LocalHost
from pytranscoder.utils import files_from_file, get_local_os_type, calculate_progress, dump_stats, is_exceeded_threshold


class TranscoderTests(unittest.TestCase):

    @staticmethod
    def make_media(path, vcodec, res_width, res_height, runtime, source_size, fps, colorspace,
                   audio, subtitle) -> MediaInfo:
        info = {
            'path': path,
            'vcodec': vcodec,
            'stream': 0,
            'res_width': res_width,
            'res_height': res_height,
            'runtime': runtime,
            'filesize_mb': source_size,
            'fps': fps,
            'colorspace': colorspace,
            'audio': audio,
            'subtitle': subtitle
        }
        return MediaInfo(info)

    def test_stream_map_all(self):
        with open('tests/ffmpeg3.out', 'r') as ff:
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            setup = ConfigFile(self.get_setup())
            p = setup.get_directive('qsv')
            streams = info.stream_map(p)
            self.assertEqual(len(streams), 2, 'expected -map 0')

    def test_stream_exclude(self):
        with open('tests/ffmpeg3.out', 'r') as ff:
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            setup = ConfigFile(self.get_setup())
            p = setup.get_directive('excl_test_1')
            streams = info.stream_map(p)
            self.assertEqual(len(streams), 12, 'expected 6 streams (12 elements)')

    def test_stream_reassign_default(self):
        with open('tests/ffmpeg4.out', 'r') as ff:
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            setup = ConfigFile(self.get_setup())
            p = setup.get_directive('excl_test_2')
            streams = info.stream_map(p)
            self.assertEqual(len(streams), 8, 'expected 4 streams (8 elements)')

#    def test_hook(self):
#        transcode.manage_hook("rule_hook_ex.py")
#        info = TranscoderTests.make_media("/some/path/to/anime/content", "x264", 1080, 720, 45, 3000, 25, None, [], [])
#        profile = try_hook(info, is_testing=True)
#        transcode.manage_hook(None)
#        self.assertEqual(profile.name, "anime", "Expected to match anime")
#        expected = sorted(["-f matroska", "-c:a copy", "-c:s copy", "-c:v hevc_nvenc", "-profile:v main",
#                           "-preset medium", "-crf 20"])
#        actual = sorted(profile.output_options.as_list())
#        self.assertEqual(actual, expected, "Output options mismatch")

    def test_profile_merge(self):
        p1 = Profile("p1", {"one": 1, "two": 2, "input_options": ["three", "four", "five"]})
        p2 = Profile("p2", {"one": 11, "six": 6, "input_options": ["seven", "four"]})
        p2.include(p1)
        self.assertEqual(p2.get("one"), 11, 'expected 11 for "one"')
        self.assertEqual(p2.get("two"), 2, 'expected 2 for "two"')
        self.assertEqual(p2.get("six"), 6, 'expected 6 for "six"')
        op2 = sorted(p2.input_options_list.as_list())
        expected = sorted(["three", "four", "five", "seven"])
        self.assertEqual(op2, expected, "Unexpected input_options merger")

    def test_progress(self):
        info = TranscoderTests.make_media(None, None, None, 1080, 90 * 60, 2300, 25, None, [], [])
        stats = {'size': 1225360000, 'time': 50 * 60}
        done, comp = calculate_progress(info, stats)
        self.assertEqual(done, 55, 'Expected 55% done')
        self.assertEqual(comp, 6, 'Expected 6% compression')

    def test_ffmpeg_status_regex(self):
        sample = 'frame=  307 fps= 86 q=-0.0 size=    3481kB time=00:00:13.03 bitrate=2187.9kbits/s speed=3.67x   \n'
        match = status_re.match(sample)
        self.assertIsNotNone(match, 'no ffmpeg status match')
        self.assertTrue(len(match.groups()) == 5, 'Expected 5 matches')

    def test_loadconfig(self):
        config = ConfigFile('config-samples/transcode.yml')
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
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            self.assertIsNotNone(info)
            self.assertEqual(info.vcodec, 'h264')
            self.assertEqual(info.res_width, 1280)
            self.assertEqual(info.fps, 23)
            self.assertEqual(info.runtime, (2 * 3600) + (9 * 60) + 38)
            self.assertEqual(info.path, '/dev/null')
            self.assertEqual(info.colorspace, 'yuv420p')

    def test_mediainfo2(self):
        with open('tests/ffmpeg2.out', 'r') as ff:
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            self.assertIsNotNone(info)
            self.assertEqual(info.vcodec, 'h264')
            self.assertEqual(info.res_width, 1920)
            self.assertEqual(info.fps, 24)
            self.assertEqual(info.runtime, (52 * 60) + 49)
            self.assertEqual(info.path, '/dev/null')
            self.assertEqual(info.colorspace, 'yuv420p')

    def test_mediainfo3(self):
        with open('tests/ffmpeg3.out', 'r') as ff:
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            self.assertIsNotNone(info)
            self.assertEqual(info.vcodec, 'hevc')
            self.assertEqual(info.res_width, 3840)
            self.assertEqual(info.fps, 23)
            self.assertEqual(info.runtime, (2 * 3600) + (5 * 60) + 53)
            self.assertEqual(info.path, '/dev/null')
            self.assertEqual(info.colorspace, 'yuv420p10le')

    def test_include_overides(self):
        setup = ConfigFile(self.get_setup())
        p: Profile = setup.get_directive('hevc_cuda_8bit')
        self.assertEqual(p.threshold, 0, 'Threshold should be 0')
        self.assertEqual(p.threshold_check, 100, 'Threshold check should be 100')
        self.assertIn("-cq:v 21", p.output_options_list.as_list(), 'Expected -cq:v 21')
        self.assertIn('-pix_fmt yuv420p', p.output_options_list.as_list(), 'expected pix_fmt')

    def test_default_profile(self):
        info = TranscoderTests.make_media(None, None, None, 720, 45, 3000, 25, None, [], [])
        config = ConfigFile(self.get_setup())
        rule = config.match_rule(info)
        self.assertIsNotNone(rule, 'expected to match a rule')
        self.assertEqual(rule.profile, 'hevc_cuda')
        self.assertEqual(rule.name, 'default')

    def test_skip_profile(self):
        with open('tests/ffmpeg.out', 'r') as ff:
            info = MediaInfo.parse_ffmpeg_details('/dev/null', ff.read())
            info.filesize_mb = 499
            config = ConfigFile(self.get_setup())
            rule = config.match_rule(info)
            self.assertIsNotNone(rule, 'Expected rule match')
            self.assertTrue(rule.is_skip(), 'Expected a SKIP rule')

    def test_rule_match(self):
        info = TranscoderTests.make_media(None, None, None, 1080, 45, 2300, None, None, [], [])
        config = ConfigFile(self.get_setup())
        rule = config.match_rule(info)
        self.assertIsNotNone(rule, 'Expected a matched profile')

    def test_loc_os(self):
        self.assertNotEqual(get_local_os_type(), 'unknown', 'Expected other than "unknown" as os type')

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

    def test_threshold_calculation(self):
        src = 1_234_567_890
        dest = 1_000_000_000
        threshold = 20
        result = is_exceeded_threshold(threshold, src, dest)
        self.assertFalse(result, "Expected threshold to be false")

    @staticmethod
    def get_setup():
        setup = {
            'config': {
                'ffmpeg': '/usr/bin/ffmpeg',
                'hbcli': '/usr/bin/HandBrakeCLI',
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
                            'profiles': ['hevc_cuda'],
                            'queues': {'q2': 2},
                            'status': 'enabled',
                        },
                        'workstation': {
                            'os': 'linux',
                            'type': 'local',
                            'ip': '192.168.2.63',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'status': 'enabled',
                        },
                        'm2': {
                            'type': 'streaming',
                            'ip': '127.0.0.1',
                            'os': 'linux',
                            'user': 'mark',
                            'ffmpeg': '/usr/bin/ffmpeg',
                            'working_dir': '/tmp/pytranscode-remote',
                            'profiles': ['qsv'],
                            'queues': {'q3': 1},
                            'status': 'enabled',
                        },
                    },
                },
            },
            "profiles": {
                "hq": {
                    "output_options": ["-c:v", "copy", "-c:a", "copy", "-c:s", "copy", "-f", "matroska"],
                    "threshold": 1,
                    "extension": ".mkv",
                },
                "hevc_cuda": {
                    "include": "hq",
                    "input_options": None,
                    "output_options": ["-threads 4"],
                    "extension": ".mkv",
                    "queue": "q2",
                    "audio": {
                        "include_languages": ["eng"],
                        "default_language": "eng",
                    },
                    "subtitle": {
                        "include_languages": ["eng"],
                        "default_language": "eng",
                    }
                },
                "hevc_cuda_8bit": {
                    "include": "hq",
                    "output_options": [
                        "-cq:v 21",
                        "-b:v 2000K",
                        "-maxrate:v 4M",
                        "-pix_fmt yuv420p"
                    ],
                    "threshold": 0,
                    "threshold_check": 100
                },
                "excl_test_1": {
                    "include": "hq",
                    "input_options": None,
                    "output_options": ["-threads 4"],
                    "extension": ".mkv",
                    "queue": "q2",
                    "audio": {
                        "exclude_languages": ["spa"],
                        "default_language": "eng",
                    },
                    "subtitle": {
                        "exclude_languages": ["spa"],
                        "default_language": "eng",
                    }
                },
                "excl_test_2": {
                    "include": "hq",
                    "input_options": None,
                    "output_options": ["-threads 4"],
                    "extension": ".mkv",
                    "queue": "q2",
                    "audio": {
                        "exclude_languages": ["eng"],
                        "default_language": "chi",
                    },
                    "subtitle": {
                        "exclude_languages": ["eng"],
                        "default_language": "chi",
                    }
                },
                "qsv": {
                    "input_options": None,
                    "output_options": ["-c:v copy -c:a copy"],
                    "extension": ".mkv",
                    "queue": "q3",
                },
                "vintage_tv": {
                    "input_options": None,
                    "output_options": ["-c:v copy -c:a copy"],
                    "extension": ".mp4",
                },
                "hbcli_qsv": {
                    "input_options": None,
                    "output_options": ["-f av_mkv -q 20.0 -B 256 -e qsv_h265"],
                    "extension": ".mkv",
                    "queue": "qsv"
                }
            },
            "rules": {
                'vintage tv': {
                    'profile': 'vintage_tv',
                    'criteria': {
                        'filesize_mb': '<500',
                        'res_height': '<500',
                        'runtime': '<60',
                    },
                },
                'too small': {
                    'profile': 'SKIP',
                    'criteria': {
                        'filesize_mb': '<500'
                    }
                },
                'small enough already': {
                    'profile': 'SKIP',
                    'criteria': {
                        'filesize_mb': '<2500',
                        'res_height': '720-1081',
                        'runtime': '30-65'
                    }
                },
                'feature-length treat better': {
                    'profile': 'qsv',
                    'criteria': {
                        'runtime': '>90'
                    },
                },
                'default': {
                    'profile': 'hevc_cuda',
                    'criteria': {
                        'vcodec': '!hevc'
                    }
                }
            }
        }
        return setup

    @mock.patch.object(FFmpeg, 'run_remote')
    @mock.patch('pytranscoder.cluster.filter_threshold')
    @mock.patch('pytranscoder.cluster.os.rename')
    @mock.patch('pytranscoder.cluster.os.remove')
    @mock.patch.object(FFmpeg, 'fetch_details')
    def test_cluster_match_default_rule(self, mock_ffmpeg_details, mock_os_rename, mock_os_remove,
                                        mock_filter_threshold, mock_run_remote):

        setup = ConfigFile(self.get_setup())

        #
        # setup all mocks
        #
        mock_run_remote.return_value = 0
        mock_filter_threshold.return_value = True
        mock_os_rename.return_value = None
        mock_os_remove.return_value = None
        info = TranscoderTests.make_media('/dev/null', 'x264', 1920, 1080, 45 * 60, 3200, 24, None, [], [])
        mock_ffmpeg_details.return_value = info

        #
        # configure the cluster, add the job, and run
        #
        cluster = self.setup_cluster1(setup)
        qname, job = cluster.enqueue('/dev/null.mp4', None)
        self.assertEqual(qname, 'q2', 'Job placed in wrong queue')
        self.assertEqual(job.profile_name, 'hevc_cuda', 'Rule matched to wrong profile')

        cluster.testrun()
        for host in cluster.hosts:
            if host.hostname == 'm1' and len(host._complete) > 0:
                filename, elapsed = host.completed.pop()
                self.assertEqual('/dev/null.mp4', filename, 'Completed filename missing from assigned host')
                break

    @staticmethod
    def setup_cluster1(config) -> Cluster:
        cluster_config = config.settings['clusters']
        cluster = Cluster('cluster1', cluster_config['cluster1'], config, config.ssh_path)
        return cluster

    @mock.patch.object(FFmpeg, 'run_remote')
    @mock.patch('pytranscoder.cluster.filter_threshold')
    @mock.patch('pytranscoder.cluster.os.rename')
    @mock.patch('pytranscoder.cluster.os.remove')
    @mock.patch.object(FFmpeg, 'fetch_details')
    def test_cluster_match_skip(self, mock_ffmpeg_details, mock_os_rename, mock_os_remove,
                                mock_filter_threshold, mock_run_remote):

        setup = ConfigFile(self.get_setup())

        #
        # setup all mocks
        #
        mock_run_remote.return_value = 0
        mock_filter_threshold.return_value = True
        mock_os_rename.return_value = None
        mock_os_remove.return_value = None
        info = TranscoderTests.make_media('/dev/null', 'x264', 1920, 1080, 60 * 60, 1800, 24, None, [], [])
        mock_ffmpeg_details.return_value = info

        #
        # configure the cluster, add the job, and run
        #
        cluster = self.setup_cluster1(setup)
        qname, job = cluster.enqueue('/dev/null.mp4', None)
        self.assertEqual(qname, None, 'Expected to skip')

    @mock.patch.object(FFmpeg, 'run_remote')
    @mock.patch('pytranscoder.cluster.filter_threshold')
    @mock.patch('pytranscoder.cluster.os.rename')
    @mock.patch('pytranscoder.cluster.os.remove')
    @mock.patch.object(MediaInfo, 'parse_ffmpeg_details')
    @mock.patch('pytranscoder.cluster.run')
    @mock.patch('pytranscoder.cluster.shutil.move')
    @mock.patch.object(FFmpeg, 'fetch_details')
    @mock.patch.object(StreamingManagedHost, 'run_process')
    def test_cluster_streaming_host(self, mock_run_proc, mock_ffmpeg_fetch, mock_move, mock_run, mock_info_parser,
                                    mock_os_rename, mock_os_remove,
                                    mock_filter_threshold, mock_run_remote):

        setup = ConfigFile(self.get_setup())

        #
        # setup all mocks
        #
        mock_run.return_value = 0, 'ok'
        mock_run_remote.return_value = 0
        mock_move.return_value = 0
        mock_filter_threshold.return_value = True
        mock_os_rename.return_value = None
        mock_os_remove.return_value = None
        info = TranscoderTests.make_media('/dev/null', 'x264', 1920, 1080, 110 * 60, 3000, 24, None, [], [])
        mock_info_parser.return_value = info
        mock_ffmpeg_fetch.return_value = info
        #
        # configure the cluster, add the job, and run
        #
        cluster = self.setup_cluster1(setup)
        qname, job = cluster.enqueue('/dev/null.mp4', None)
        self.assertEqual(qname, 'q3', 'Job placed in wrong queue')
        self.assertEqual(job.profile_name, 'qsv', 'Rule matched to wrong profile')

        cluster.testrun()
        for host in cluster.hosts:
            if host.hostname == 'm2' and len(host._complete) > 0:
                filename, elapsed = host.completed.pop()
                self.assertEqual('/dev/null.mp4', filename,
                                  'Completed filename missing from assigned host')
                break

    @mock.patch.object(FFmpeg, 'run')
    @mock.patch('pytranscoder.cluster.filter_threshold')
    @mock.patch('pytranscoder.cluster.os.rename')
    @mock.patch('pytranscoder.cluster.os.remove')
    @mock.patch.object(MediaInfo, 'parse_ffmpeg_details')
    @mock.patch.object(FFmpeg, 'fetch_details')
    def test_cluster_match_default_queue(self, mock_ffmpeg_details, mock_info_parser, mock_os_rename, mock_os_remove,
                                         mock_filter_threshold, mock_run_remote):

        setup = ConfigFile(self.get_setup())

        #
        # setup all mocks
        #
        mock_run_remote.return_value = 0
        mock_filter_threshold.return_value = True
        mock_os_rename.return_value = None
        mock_os_remove.return_value = None
        info = TranscoderTests.make_media('/dev/null', 'x264', 500, 480, 30 * 60, 420, 24, None, [], [])
        mock_info_parser.return_value = info
        mock_ffmpeg_details.return_value = info

        #
        # configure the cluster, add the job, and run
        #
        cluster = self.setup_cluster1(setup)
        qname, job = cluster.enqueue('/dev/null.mp4', None)
        self.assertEqual(qname, '_default', 'Job placed in wrong queue')
        self.assertEqual(job.profile_name, 'vintage_tv', 'Rule matched to wrong profile')

        cluster.testrun()
        for host in cluster.hosts:
            if host.hostname == 'workstation' and len(host._complete) > 0:
                dump_stats(host._complete)
                filename, elapsed = host.completed.pop()
                self.assertEqual('/dev/null.mp4', filename, 'Completed filename missing from assigned host')
                break


if __name__ == '__main__':
    unittest.main()
