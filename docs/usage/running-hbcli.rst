======================
Running (HandBrakeCLI)
======================

Although this tool is designed for **ffmpeg**, it has limited support for HandBrakeCLI as well.

*Sample .transcode.yml exerpt:*

.. code-block:: yaml

    ffmpeg: '/usr/bin/ffmpeg'
    hbcli: '/usr/bin/HandBrakeCLI'

    profiles:

          handbrake_qsv_hevc:
            processor: hbcli
            output_options:
              - "-f av_mkv"
              - "-q 20.0"
              - "-B 256"
              - "-e qsv_h265"
            extension: '.mkv'
            queue: 'qsv'

This is an example profile to do a simple encode. Structurally this profile is the same
as for **ffmpeg** except with the addition of the "processor" directive.
This is used to indicate that the profile is to use the configured **HandBrakeCLI**.
If "processor" is omitted then the profile is assumbed to be for **ffmpeg**.

For clusters, you configure the *hbcli* directive the same as *ffmpeg*.

