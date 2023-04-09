=============
Configuration
=============

Since pytranscoder can be run in a variety of ways it is easy to customize your workflow to your liking.  You an choose more detailed
control at the commandline or use the rules engine to help you be efficient. But at a minimum you need a configuration file as
described below. You can either specific the config file on the commandline with the **-y** flag or you can put it in the default
location, in a file called **.transcode.yml** in your home folder.

The configuration file is divided into 3 sections: global, profiles, and rules.

------
Global
------

These options apply globally to pytranscoder.

*Sample*:

.. code-block:: yaml

    config:
        default_queue_file:   '/path/to/default/list/of/files.txt'
        ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg
        ssh:                  '/usr/bin/ssh'        # your ssh client (for cluster support)
        queues:
            qsv:                1                   # sequential encodes
            cuda:               2                   # maximum of 2 encodes at a time
        colorize:             yes
        automap:              no                    # automatically generate ffmpeg -map options for all streams
        fls_path:             '/tmp'                # use local SSD to reduce thrashing of my NAS

+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Setting               | Purpose                                                                                                                                                                                                                                   |
+=======================+===========================================================================================================================================================================================================================================+
| default_queue_file    | A queue file is just a text file listing out all the media you want to encode. It is not required, but useful when automating a workflow. You can always indicate a queue file on the command line. This just sets the default, if any.   |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ffmpeg                | Full path to *ffmpeg* on this host                                                                                                                                                                                                        |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ssh                   | Full path to *ssh* on this host, used only in cluster mode.                                                                                                                                                                               |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| queues                | If using concurrency, define your queues here. The queue name is whatever you want. Each name specifies a maximum number of concurrent encoding jobs on the host machine. The default is sequential encoding (one at a time)              |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| colorize              | optional, defaults to "no". If "yes" terminal output will have some color added                                                                                                                                                           |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| automap               | optional, defaults to "yes". If "yes" then auto calculate and insert *ffmpeg* **-map** options to preserve all audio and subtitle tracks                                                                                                  |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| fls_path              | optional. If given, this path is used when transcoding to build the output file. This reduces drive thrashing if the source is on a network share. When finished, the output is only then moved to the source.                            |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+


-------------------
Profiles (optional)
-------------------

Profiles are used to provide the encoder with various options for encoding. One profile definition is required, but mostly likely
you will define multiples for different encoding scenarios.  The name of the profile can be provided on the command line
to select the appropriate one for your needs. Alternatively, you can define rules (see below) to auto-match media with profiles for a less manual encoding workflow.

*Sample*:

.. code-block:: yaml

    profiles:

        # some common, reusable settings to keep things tidy
        common:
            output_options:
                - "-f matroska"
            output_options_audio:
                - "-c:a copy"
            output_options_video:
                - "-crf 20"
            output_options_subtitle:
                - "-c:s copy"
            extension: '.mkv'

            threshold: 20
            threshold_check: 30
            automap: yes
            audio:
                include_languages:
                    - "eng"
                    - "jpn"
                default_language: eng

            subtitle:
                include_languages:
                    - "eng"
                default_language: eng

        #
        # Sample Intel QSV transcode setup (note to customize -hwaccel_device param for your environment)
        #
        hevc_qsv:
            include: common
            input_options:
                - "-hwaccel vaapi"
                - "-hwaccel_device /dev/dri/renderD129"
                - "-hwaccel_output_format vaapi"
            output_options_video:
                - "-vf scale_vaapi=format=p010"
                - "-c:v hevc_vaapi"

        #
        # Sample nVidia transcode setup
        #
        hevc_cuda:                  # profile name
            include: common
            input_options:          # ffmpeg input options
                - "-hwaccel cuvid"  # REQUIRED for CUDA
                - "-c:v h264_cuvid" # hardware decoding too
            output_options_video:
                - "-c:v hevc_nvenc" # REQUIRED for CUDA
                - "-profile:v main"
                - "-preset medium"
            queue: cuda		# manage this encode in the 'cuda' queue defined globally

            # optionally you can filter out audio/subtitle tracks you don't need.
            # these can also be moved to the "common" profile.

        x264:                        # simple h264
            include: common
            input_options:
            output_options_video:
                - "-c:v x264"

        h264_cuda_anime:            # h264 with animation tuning
            include: common
            input_options:
            output_options_video:
                - "-c:v h264_nvenc"
                - "-tune animation"
            audio:
                include_languages:
                    - "eng"
                    - "jpn"


Take a look over this sample.  Most of what you need is here.  Of special note is the **include** directive, which literally includes
one or more other profiles to create a new, combined one. Use this to isolate common flags to keep new profile definitions simpler.

+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Setting                 | Purpose                                                                                                                                                                       |
+=========================+===============================================================================================================================================================================+
| input_options           | Encoder options related to the input (see ffmpeg docs)                                                                                                                        |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| output_options          | General encoder options related to the output (see ffmpeg docs).                                                                                                              |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| output_options_video    | Video-specific encoder options. Works like output_options except this is mixin-enabled.                                                                                       |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| output_options_audio    | Audio-specific encoder options. Works like output_options except this is mixin-enabled.                                                                                       |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| output_options_subtitle | Subtitle-specific encoder options. Works like output_options except this is mixin-enabled.                                                                                    |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| extension               | Filename extension to use for the encoded file                                                                                                                                |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| queue                   | optional. Assign encodes for this profile to a specific queue (defined in *config* section)                                                                                   |
+-------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| threshold             | optional. If provided this number represents a minimum percentage compression savings for the encoded media.                                                                    |
|                       | If it does not meet this threshold the transcoded file is discarded and the source file remains as-is.                                                                          |
+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| threshold_check       | optional. If provided this is the percent done to start checking if the threshold is being met.                                                                                 |
|                       | Default is 100% (when media is finished). Use this to have threshold checks done earlier to stop a long-running transcode if not producing expected compression (threshold).    |
+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| include               | optional. Include options from one or more previously defined profiles. (see section on includes).                                                                              |
+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| audio                 | Audio track handling options. Include a list of **exclude_languages** to automatically remove tracks, or **include_languages** to only include them.                            |
|                       | Removed default selections will be replaced with the given **default_language**.                                                                                                |
+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| subtitle              | See _audio_ above.                                                                                                                                                              |
+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| automap               | optional, defaults to "yes". If "yes" then auto calculate and insert *ffmpeg* **-map** options to preserve all audio and subtitle tracks.                                       |
|                       | Overrides the Global setting, if any.                                                                                                                                           |
+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. note::
    When transcoding from h264 on an Intel I5/I7 6th+ gen chip, *ffmpeg* will use detected extensions to basically perform hardware decoding for you. So if you configured hardware encoding you'll see low CPU use. On AMD there is no chip assistance on decoding.  So even if hardware encoding, the decoding process will load down your CPU. To fix this simply enable hardware decoding as an **input option**.

----------------
Rules (optional)
----------------

Simple expressions to match video files with the appropriate profile. They are evaluated top-down so
make sure your default is the last one. You don't need to use the rules system. You can either
explicitly give the desired profile name on the commandline or just have a single rule for default.
But if you encode certain media differently then having the rules system make it a little easier
using various options depending on the media attributes.  No specific criteria is required - use the ones
applicable to your rule.

Rule evaluation is as follows: for each input media file, compare against each rule criteria. All criteria of a rule must match
in order for the given profile to be selected.  If any one fails, evaluation continues to the next
rule. If there are no matches, the *default* rule is selected.

*Samples*:

.. code-block:: yaml

    rules:
        'content too big':            # comment and unique identifier for this rule
            profile: hevc_hd_25fps    # profile to use if the criterial below match
            criteria:
                runtime:      '<180'    # less than 3 hours long
                filesize_mb:  '>5000'   # ..and media file larger than 5 gigabytes
                fps: '>25'              # ..and framerate > 25

        'already best codec':
            profile: 'SKIP'     # special keyword SKIP, means anything that matches this rule won't get transcoded
            criteria:
                'vcodec': 'hevc'	# if media video is encoded with hevc already

        'skip files that are not appropriate for hevc':
            profile: 'SKIP'
            criteria:
                filesize_mb: '<600'     # video file is less than 600mb
                runtime: '<40'          # ..and total runtime < 40 minutes

        'anime to h264':
            profile: h264_cuda_anime
            criteria:
                filesize_mb: '>2500'    # larger than 2.5g
                vcodec: '!hevc'         # not encoded with hevc
                path: '/media/anime/.*' # in a anime folder (regex)

        'half-hour videos':
            profile: 'x264'             # use profile called "x264"
            criteria:
                filesize_mb: '>500'     # 400mb file size or greater
                runtime: '<31'        	# 30 minutes or less runtime
                vcodec: '!hevc'	       	# NOT hevc encoded video

        'small enough already':         # skip if <2.5g size, between 720p and 1080p, and between 30 and 64 minutes long.
            profile: SKIP               # transcoding these will probably cause a noticeable quality loss so skip.
            criteria:
                filesize_mb: '<2500'    # less than 2.5 gigabytes
                res_height: '720-1081'  # 1080p, allowing for random oddball resolutions still in the HD range
                runtime:  '35-65'       # between 35 and 65 minutes long

        'default':                      # this will be the DEFAULT (no criteria implies a match)
            profile: hevc_cuda
            criteria:
                vcodec: '!hevc'


+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Setting       | Purpose                                                                                                                                                                       |
+===============+===============================================================================================================================================================================+
| profile       | The defined profile name (from above) to select if this rule criteria matches. If the profile name is *SKIP* then matched media will not be transcoded                        |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| runtime       | Total run time of media, in minutes. Determined by ffmpeg. Optionally can use < or > or a range                                                                               |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| source_size   | Size, in megabytes, of the media file. Optionally an use < or > or a range                                                                                                    |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| fps           | Frames per second. Determined by ffmpeg. Optionally can use < or > or a range                                                                                                 |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| vcodec        | Video codec used on the source media. Determined by ffmpeg. Can use ! to indicate *not* condition (negative match)                                                            |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| res_height    | Video vertical resolution. Determined by ffmpeg. Optionally can use < or > or a range                                                                                         |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| res_width     | Video horizontal resolution. Determined by ffmpeg. Optionally can use < or > or a range                                                                                       |
+---------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. note::
    For those settings that allow operators, put the operator first (< or >) followed by the number. For those that allow a range
    provide the lower and upper range with a hyphen (-) between.  No spaces are allowed in criteria.

