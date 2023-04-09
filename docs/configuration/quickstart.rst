===============
Quick Start
===============

For simple commandline help

.. code-block:: bash

    pytranscoder -h


To get started right away, start with this configuration:

.. code-block:: yaml


    config:
        ffmpeg:             '/usr/bin/ffmpeg'
        colorize:           yes

    templates:
        qsv:            # high quality h265
            cli:
                video-codec: "-c:v hevc_qsv -preset medium -qp 21 -b:v 7000K -f matroska -max_muxing_queue_size 1024"
                audio-codec: "-c:a copy"
                subtitles: "-c:s copy"
            audio-lang: eng
            subtitle-lang: eng
            threshold: 15
            threshold_check: 30
            extension: '.mkv'

        qsv_medium: # medium quality h265
            cli:
                video-codec: "-c:v hevc_qsv -preset medium -qp 21 -b:v 4000K -f matroska -max_muxing_queue_size 1024"
                audio-codec: "-c:a ac3 -b:a 768k"
                subtitles: "-c:s copy"
            audio-lang: eng
            subtitle-lang: eng
            threshold: 15
            threshold_check: 30
            extension: '.mkv'

        qsv_anime:  # anime, medium quality h265 and keep both eng and jpn language tracks
            cli:
                video-codec: "-c:v hevc_qsv -preset medium -qp 21 -b:v 3000K -f matroska"
                audio-codec: "-c:a ac3 -b:a 768k"
                subtitles: "-c:s copy"
            audio-lang: "eng jpn"
            subtitle-lang: eng
            threshold: 15
            threshold_check: 30
            extension: '.mkv'



Copy this file and save as **$HOME/.transcode.yml**, the default location pytranscoder will look for its configuration.
Pick a video file to test with. Let's refer to it as "myvideo.mp4", using the "qsv" template defined above.

.. code-block:: bash

    pytranscoder --dry-run -t qsv myvideo.mp4

You will see details of the ffmpeg command pytranscoder will use when you run for real.

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
