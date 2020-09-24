============
Using Mixins
============

Mixins are new as of version 2.2 and are a more flexible way of reusing profiles. You don't have to refit your transcode.yaml to use mixins - profiles are still backward-compatible.
Simply put, a mixin is a profile fragment used, at runtime, to "mix-in" to an existing profiles.

There are 2 requirements to use them:

1. Your profiles must be mixin-enabled, meaning you need to split your current output_options into output_options, output_options_video, output_options_audio, and output_options_subtitle (or whichever ones you intend to use for mixins).
2. The output_options section should be limited to general, non-encoding options. But you may continue to put, for example, subtitle options there.  You just can't use a subtitle mixin later if you do.
3. Define mixin profiles.
4. Specify mixins from the command line as needed (using -m).

So what's the difference between "includes" and "mixins".  The short answer is, "much".
An include pulls in options from other profiles and combines them.  A mixin is exclusive - they are never combined. This means you can use includes and mixins at the same time.
When you specify a mixin to use at runtime, whichever section is in that mixin will override the same section in the profile.  This allows for each swapping out of specific output options as needed without defining new profiles.

As an example, assume you have a 4G download of a 50 minute TV show. You think 4G is just too big so you use ffprobe to look at the details.  Somebody encoded the audio in DTS at a very high bitrate and it's using 1/3 of the space just for audio.  Well that's just silly, so you want to re-encode just the audio.  Using just profiles, you would have to create a specific one just for this scenario.  But if you have mixins defined you can do something like this:

  pytranscoder -p copy -m aac_hq my_large_video.mp4

See example profiles below for how this would be setup. Note that the output_audio section of the mixin will *replace* the same section of the "copy" profile using the command line above.
So now we have a generic copy file we can use for anything, such as changing video containers.  Or we can use mixins to make selective changes to audio, video, or subtitle.
Multiple mixins may be specified, separated with a comma (no spaces allowed).


.. code-block:: yaml

    profiles:

        # generic, "copy" profiles
        copy:
          output_options:
            - "-f matroska"

          output_options_video:
            - "-c:v copy" 

          output_options_audio:
            - "-c:a copy" 

          output_options_subtitle:
            - "-c:s copy" 

          threshold: 20
          extension: ".mkv"


        # this is a mixin
        aac_hq:
          output_options_audio:
            - "-c:a libfdk_aac"
            - "-b:a 384k"


Another, more practical example. I do mostly cuda/hevc encoding but depending on content may want to vary the quality without resorting to a new profile:

.. code-block:: yaml

  typical:
      output_options_video:	# defaults to high quality
        - "-cq:v 21"            # crf option passed to CUDA engine
        - "-rc vbr_hq"          # variable bit-rate, high quality
        - "-rc-lookahead 20"
        - "-bufsize 5M"
        - "-b:v 7M"
        - "-profile:v main"
        - "-maxrate:v 7M"
        - "-c:v hevc_nvenc"
        - "-preset slow"
        - "-pix_fmt yuv420p"
      output_options_audio:
        - "-c:a copy"       # copy all audio as-is
      output_options_subtitle:
        - "-c:s copy"       # copy all subtitles as-is
      output_options:
        - "-f matroska"     # mkv format
        - "-max_muxing_queue_size 1024"
    extension: '.mkv'
    threshold: 18           # minimum of 18% compression required
    threshold_check: 20     # start checking threshold at 20% complete

  # mixin to allow me to override the higher quality of the profile above, at runtime
  medium:
      output_options_video:
      - "-cq:v 23"
      - "-bufsize 3M"
      - "-b:v 5M"
      - "-profile:v main"
      - "-maxrate:v 5M"
      - "-preset medium"

  aac_hq:
    output_options_audio:
      - "-c:a libfdk_aac"
      - "-b:a 384k"


So now I have the option to just use:
pytranscoder -p code a_file.mp4

or if I want a smaller file size:

pytranscoder -p cuda -m medium,aac_hq a_file.mp4

