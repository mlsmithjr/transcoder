# transcoder

Python wrapper for ffmpeg for batch and concurrent transcoding

This script is intended to help automate transcoding for people running a media server.

### Features:
* Sequential or concurrent transcoding. Concurrent mode allows you to make maximum use of your 
nVida CUDA-enabled graphics card or Intel accelerated video.
* Configurable transcoding profiles
* Configurable rules to auto-match a video file to a transcoding profile
* Transcode from a list of files or all on the command line
* Optionally trigger Plex library update via API

### Requirements

* Linux
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* latest nVidia CUDA drivers (_optional_)
* Python 3 (3.6 or higher)
* Python PlexAPI package (optional).  Install with `pip3 install plexapi`

### Configuration

There is a supplied sample *transcode.yml* config file.  This can be customized all you like, however be
sure to preserve the YAML formatting.

There are 3 sections:

##### config
> Global configuration information

Sample
``` 
  default_queue_file:   '/path/to/default/list/of/files/if/none/given'
  ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg for this config
  concurrent_jobs:      2              # set to 1 to disable concurrency
  plex_server:          null           # can be 'server:port'
```

##### profiles
> Transcoding profiles (ffmpeg options)

Sample:
``` 
  hevc_hd_preserved:          # profile name
      input_options: |        # ffmpeg input options
        -hide_banner
        -nostats
        -loglevel quiet
        -hwaccel cuvid        # REQUIRED for CUDA
      output_options: |       # ffmpeg output options
        -c:v hevc_nvenc       # REQUIRED for CUDA
        -profile:v main
        -preset medium
        -crf 20
        -c:a copy
        -c:s copy
        -f matroska
      extension: '.mkv'
```
##### rules
> Simple expression to match video files with the appropriate profile. They are evaluated top-down so
make sure your default is the last one. You don't need to use the rules system. You can either
explicitly give the desired profile name on the commandline or just have a single rule for default.
But if you transcode certain media differently then having the rules system make it easy to transcode
using various options depending on the media.
ß
Samples:
``` 
  'for content I consider too big for their runtime':
      profile: hevc_hd_25fps    # profile to use if the criterial below match
      rules:
        runtime:      '<180'    # less than 3 hours
        source_size:  '>5000'   # ..and larger than 5 gigabytes

  'default':                    # this will be the DEFAULT (no rules implies a match)
      profile: hevc_hd_preserved
```
Since there are people who will run this script in synchronous mode, the *concurrent_jobs* value should be set to 1.
There really is no good reason to increase this number if you are not using hardware transcoding as the CPU will be
fully engaged already.


### Profiles and Rules

A profile is a named group of *ffmpeg* commandline options to transcode a specific way. You can
define all the combinations you use regularly in *transcode.yml* for easy selection later.
At least 1 profile definition is required.

A rule is a YAML syntax of predefined predicates to allow simple matching on source media details
and match to a specific profile.  For example, if you transcode 720p differently than 1080p, and still different
than 4k you can set up rules to match those 3 resolutions to a specific transcode profile.
Easy - let the script do the work of selecting the right *ffmpeg* options.

But you aren't required to use rules.  You can specify the profile on the commandline each
run using the -p option. Or you can define 1 rules that acts as a default (see example above).


### Notes on Concurrency

Concurrency here means running multiple transcoding jobs at the same time by taking advantage of hardware support.
Normally a transcode will almost max out a CPU until it is finished. But with hardware-assisted transcoding
very little of the CPU is used and most work is offloaded to the hardware. This allows the CPU to handle
multiple files and still have processing power left over for regular system activities.

To change the concurrent jobs default you must edit *transcode.yml*, look for *concurrent_jobs*, and 
change its value from 2 to whatever your system can handle, or 1 to disable. You must also supply the
appropriate options for your transcode profiles to use the supported hardware, otherwise you'll
completely bog down your system (see the transcode.yml "hevc" samples). If you transcode with a profile not
setup for hardware support, or the rules matcher selects a profile without the setup, that file will
transcode using CPU time. Therefore, when using concurrent hardware transcoding using rules it is best that all your rules map
to only profiles with hardware support.  You can always run non-concurrent CPU-based transcodes from
the command line, selecting sequential-only and bypassing profile rules.


### How I use this tool
My *concurrent_jobs* is set to 2.  I run on Ubuntu with a nVidia GTX 960 card with 4gb, which allows my 2 concurrent transcodes using very little CPU.
If you have a more powerful card with more memory you can try increasing the value.

I use Sonarr and Radarr to curate my library.  When items are downloaded I have a post script that records those items in a shared "queue" file, which is just a list of files - full pathnames.
Routinely I run the script to walk through my accumulated list to transcode everything. But, there are things I do not want transcoded so I use the rules as a way to skip those videos.
Also, I transcode some things differently. There are rules for those too.  And finally, I 
sometimes just want to transcode some files very specifically in a way that isn't compatible
with hardware transcoding, so I'll run the tool using -p and -s options.  Using the rules system is helpful if you are automating
your transcoding in a _cron_ job or just want to fire it off and walk away.

### Running

Note that if using a list file as input, when the process is done that file will contain only those
video files that failed to transcode, or it will be removed if all files were processed. So if you need to keep
this file make a copy first.

The default behavior is to remove the original video file after transcoding and replace it with the new version.
If you want to keep the source *be sure to use the -k* parameter.  The transcoded file will be placed in the same
folder as the source with the same name and a .tmp extension.

To get help:
```
   # python3 transcode.py -h
```

To transcode 2 files using a specific profile:
```
    # python3 transcode.py -p x264 /tmp/video1.mp4 /tmp/video2.mp4
    
```

To transcode everything in a master file, defaulting to rules to match profiles:
```
    # python3 transcode.py --from-file /tmp/queue.txt
    
```

To transcode everything in a master file, using a forced profile for all:
```
    # python3 transcode.py -p hevc_hd_preserve --from-file /tmp/queue.txt
    
```

If configured for concurrency but want o transcode a bunch of files sequentially only:
```
    # python3 transcode.py -s *.mp4
```