=============
Configuration
=============

The configuration file is divided into 3 sections: global, profiles, and rules.

======
Global
======

These options apply globally to pytranscoder.

*Sample*:

.. code-block:: yaml

    config:
        default_queue_file:   '/path/to/default/list/of/files.txt'
        ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg for this config
        ssh:                  '/usr/bin/ssh'
        queues:
            qsv:                1                   # sequential encodes
            cuda:               2                   # maximum of 2 encodes at a time
        plex_server:          192.168.2.61:32400  # optional, use 'address:port'
        colorize:             yes

+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Setting               | Purpose                                                                                                                                                                                                                                   |
+=======================+===========================================================================================================================================================================================================================================+
| default_queue_file    | A queue file is just a text file listing out all the media you want to encode. It is not required, but useful when automating a workflow. You can always indicate a queue file on the command line. This just sets the default, if any.   |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ffmpeg                | Full path to ffmpeg on this host                                                                                                                                                                                                          |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ssh                   | Full path to ssh on this host, used only in cluster mode.                                                                                                                                                                                 |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| queues                | If using concurrency, define your queues here. The queue name is whatever you want. Each name specifies a maximum number of concurrent encoding jobs. If none defined, a default sequential queue is used.                                |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| plex_server           | optional, if you want your Plex server notified after media is encoded. Use address:port format.                                                                                                                                          |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| colorize              | optional, defaults to "no". If "yes" terminal output will have some color added                                                                                                                                                           |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+


========
Profiles
========

Profiles are used to provide ffmpeg with various options for encoding. One profile definition is required, but mostly likely
you will define multiples for different encoding scenarios.  The name of the profile can be provided on the command line
to select the appropriate one for your needs. Alternatively, you can define rules (see below) to auto-match media with profiles for a less manual encoding workflow.

*Sample*:

.. code-block:: yaml

    profiles:

        # some common, reusable settings to keep things tidy
        common:
            output_options:
                - "-crf 20"
                - "-c:a copy"
                - "-c:s copy"
                - "-f matroska"
            extension: '.mkv'
            threshold: 20
            threshold_check: 60

        #
        # Sample Intel QSV transcode setup (note to customize -hwaccel_device param for your environment)
        #
        hevc_qsv:
            include: common
            input_options: -hwaccel vaapi -hwaccel_device /dev/dri/renderD129 -hwaccel_output_format vaapi
            output_options: 				# in addition to those included from 'common'
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
            output_options:         # in addition to included from 'common'
                - "-c:v hevc_nvenc" # REQUIRED for CUDA
                - "-profile:v main"
                - "-preset medium"
            queue: cuda		# manage this encode in the 'cuda' queue defined globally
            
            # optionally you can filter out audio/subtitle tracks you don't need.
            # these can also be moved to the "common" profile.
            audio:
                exclude_languages:
                    - "chi"
                    - "spa"
                    - "fre"
                    - "ger"
                default_language: eng
        
            subtitle:
                exclude_languages:
                    - "chi"
                    - "spa"
                    - "fre"
                    - "por"
                    - "ger"
                    - "jpn"
                default_language: eng

        x264:                        # simple h264
            include: common
            input_options: 
            output_options:
                - "-c:v x264"
                
        h264_cuda_anime:            # h264 with animation tuning
            include: common
            input_options:
            output_options:
                - "-c:v h264_nvenc"
                - "-tune animation"

Take a look over this sample.  Most of what you need is here.  Of special note is the **include** directive, which literally includes
one or more other profiles to create a new, combined one. Use this to isolate common flags to keep new profile definitions simpler.

+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Setting               | Purpose                                                                                                                                                                       |
+=======================+===============================================================================================================================================================================+
| input_options         | ffmpeg options related to the input (see ffmpeg docs)                                                                                                                         |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| output_options        | ffmpeg options related to the output (see ffmpeg docs)                                                                                                                        |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| extension             | Filename extension to use for the encoded file                                                                                                                                |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| queue                 | optional. Assign encodes for this profile to a specific queue (defined in *config* section)                                                                                   |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| threshold             | optional. If provided this number represents a minimum percentage compression savings for the encoded media.                                                                  | 
|                       | If it does not meet this threshold the transcoded file is discarded and the source file remains as-is.                                                                        |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| threshold_check       | optional. If provided this is the percent done to start checking if the threshold is being met.                                                                               |
|                       | Default is 100% (when media is finished). Use this to have threshold checks done earlier to stop a long-running transcode if not producing expected compression (threshold).  |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| include               | optional. Include options from one or more previously defined profiles. (see section on includes).                                                                            |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| audio                 | Audio track handling options. Include a list of **exclude_languages** to automatically remove tracks. If any track being removed is a _default_,                              |
|                       | a new default will be set based on the **default_language**.                                                                                                                  |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| subtitle              | See _audio_ above.                                                                                                                                                            |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. note::
    When transcoding from h264 on an Intel I5/I7 6th+ gen chip, *ffmpeg* will use detected extensions to basically perform hardware decoding for you. So if you configured hardware encoding you'll see low CPU use. On AMD there is no chip assistance on decoding.  So even if hardware encoding, the decoding process will load down your CPU. To fix this simply enable hardware decoding as an **input option**.

