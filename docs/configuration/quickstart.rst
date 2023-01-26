===============
Quick Start
===============

For simple commandline help

.. code-block:: bash

    pytranscoder -h


To get started right away, start with this configuration:

.. code-block:: yaml

    config:
        default_queue_file: '/tmp/queue.txt'
        ffmpeg:             '/usr/bin/ffmpeg'
        colorize:           yes

    profiles:
        x264:               # h264 encoding (CPU only)
            input_options:
            output_options:
                - "-crf 20"
                - "-c:a copy"
                - "-c:s copy"
                - "-f matroska"
                - "-c:v x264"
            threshold: 20
            threshold_check: 60
            extension: '.mkv'

        # may be out of date by now
        hevc_cuda:                  # nVidia CUDA HEVC encoding
            input_options:
                - "-hwaccel cuvid"        # REQUIRED for CUDA
                - "-c:v h264_cuvid"       # hardware decoding too
            output_options:
                - "-crf 20"
                - "-c:a copy"
                - "-c:s copy"
                - "-f matroska"
                - "-c:v hevc_nvenc"
                - "-profile:v main"
                - "-preset medium"
            extension: '.mkv'
            threshold: 20
            threshold_check: 60

    rules:

        'half-hour videos':
            profile: 'x264'             # use profile called "x264"
            criteria:
                filesize_mb: '>500'     # 400mb file size or greater
                runtime: '<31'          # 30 minutes or less runtime
                vcodec: '!hevc'         # NOT hevc encoded video

        'small enough already':       # skip if <2.5g size, between 720p and 1080p, and between 30 and 64 minutes long.
            profile: SKIP             # transcoding these will probably cause a noticeable quality loss so skip.
            criteria:
                filesize_mb: '<2500'    # less than 2.5 gigabytes
                res_height: '720-1081'  # 1080p, allowing for random oddball resolutions still in the HD range
                runtime:  '35-65'       # between 35 and 65 minutes long

        'default':
            profile: hevc_cuda
            criteria:
                vcodec: '!hevc'


Copy this file and save as **$HOME/.transcode.yml**, the default location pytranscoder will look for its configuration.
Pick a video file to test with. Let's refer to it as "myvideo.mp4".

.. code-block:: bash

    pytranscoder --dry-run myvideo.mp4

You will see something like this:

.. code-block:: bash

    ----------------------------------------
    Filename : myvideo.mp4
    Profile  : hevc_cuda
    ffmpeg   : -y -hwaccel cuvid -c:v h264_cuvid -i myvideo.mp4 -crf 20 -c:a copy -c:s copy -f matroska -c:v hevc_nvenc -profile:v main -preset medium myvideo.mkv.tmp

This shows you the video to be encoded, the profile selected (from .transcoder.yml), and the ffmpeg command line to be used.

Use the **--dry-run** flag whenever you change your configuration to test that things work the way you intend. To run for real, omit --dry-run.  You'll see something like this:

.. code-block:: bash

    myvideo.mkv: speed: 8.51x, comp: 81%, done:   8%
    myvideo.mkv: speed: 8.45x, comp: 81%, done:  16%
    myvideo.mkv: speed: 8.46x, comp: 82%, done:  25%
    myvideo.mkv: speed: 8.47x, comp: 81%, done:  33%
    myvideo.mkv: speed: 8.47x, comp: 82%, done:  42%
    myvideo.mkv: speed: 8.45x, comp: 81%, done:  50%
    myvideo.mkv: speed: 8.46x, comp: 82%, done:  59%
    myvideo.mkv: speed: 8.45x, comp: 82%, done:  68%
    myvideo.mkv: speed: 8.48x, comp: 82%, done:  76%
    myvideo.mkv: speed:  8.5x, comp: 82%, done:  85%
    myvideo.mkv: speed: 8.49x, comp: 82%, done:  94%
    Finished myvideo.mkv

**Speed** is how fast your machine is encoding video, **comp** is the compression percentage, and **done** how much has been processed.
Your original myvideo.mkv will be replaced with a new version.

.. tip::
    Should you wish to do test encodes without destroying the original, use the **-k** (keep) flag. The encode job will leave behind *myvideo.mkv.tmp*, for example.

Now you are ready to tweak your configuration with profiles and rules to suit your needs.
