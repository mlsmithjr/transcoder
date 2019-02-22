# transcoder

Python wrapper for ffmpeg for batch and concurrent transcoding

This script is intended to help automate transcoding for people running a media server.

### Features:
* Sequential or concurrent transcoding. 
* Concurrent mode allows you to make maximum use of your 
nVida CUDA-enabled graphics card or Intel accelerated video (QSV)
* Configurable transcoding profiles
* Configurable rules to auto-match a video file to a transcoding profile
* Transcode from a list of files (queue) or all on the command line
* Optionally trigger Plex library update via API
* Handles Sonarr download events and logs file path to default queue for later batch processing

### Requirements

* Linux
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* nVidia graphics card with latest nVidia CUDA drivers (_optional_)
* Intel CPU with QSV enabled (_optional_)
* Python 3 (3.6 or higher)
* Python PlexAPI package (optional).  Install with `pip3 install plexapi`

### Installation

```
pip3 install pytranscoder-ffmpeg
```

### Configuration

There is a supplied sample *transcode.yml* config file.  This can be customized all you like, however be
sure to preserve the YAML formatting. Either specify this file on the commandline with the *-y* option
or copy it to your home directory as *.transcode.yml* (default)

There are 3 sections:

## config - Global configuration information

Sample
``` 
config:
  default_queue_file:   '/path/to/default/list/of/files/if/none/given'
  ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg for this config
  concurrent_jobs:      2              # set to 1 to disable concurrency
  plex_server:          null           # can be 'address:port'
```

## profiles - Transcoding profiles (ffmpeg options)

Sample:
```yml
profiles:
  #
  # Sample Intel QSV transcode setup (note to customize -hwaccel_device param for your environment)
  #
  hevc_qsv:
    input_options: -hwaccel vaapi -hwaccel_device /dev/dri/renderD129 -hwaccel_output_format vaapi
    output_options: -vf scale_vaapi=format=p010 -c:v hevc_vaapi -crf 20 -c:a copy -c:s copy -f matroska
    extension: '.mkv'
    threshold: 20

  #
  # Sample nVidia transcode setup
  #

  hevc_hd_preserved:          # profile name
      input_options: |        # ffmpeg input options
        -hide_banner
        -hwaccel cuvid        # REQUIRED for CUDA
      output_options: |       # ffmpeg output options
        -c:v hevc_nvenc       # REQUIRED for CUDA
        -profile:v main
        -preset medium
        -crf 20
        -c:a copy             # copy audio without transcoding
        -c:s copy             # copy subtitles
        -f matroska
      extension: '.mkv'
      threshold: 20            # minimum file size reduction %, otherwise keep original

  # alternate style of option formatting
  x264:                            # profile name
      input_options: ' -hide_banner'
      output_options: '-crf 20 -c:a copy -c:s copy -f matroska'
      extension: '.mkv'


```
## rules - simple profile matching rules

Simple expression to match video files with the appropriate profile. They are evaluated top-down so
make sure your default is the last one. You don't need to use the rules system. You can either
explicitly give the desired profile name on the commandline or just have a single rule for default.
But if you transcode certain media differently then having the rules system make it a little easier
using various options depending on the media.

Samples:
```yml
  'for content I consider too big':  # comment and unique identifier for this rule
      profile: hevc_hd_25fps    # profile to use if the criterial below match
      rules:
        runtime:      '<180'    # less than 3 hours long
        source_size:  '>5000'   # ..and media file larger than 5 gigabytes
        fps: '>25'              # ..and framerate > 25

  'already best codec':
    profile: 'SKIP'     # special keyword SKIP, means anything that matches this rule won't get transcoded
    rules:
      'vcodec': 'hevc'	# if media video is encoded with hevc already

  'skip files that are not appropriate for hevc':
    profile: 'SKIP'
    rules:
      source_size: '<600'       # video file is less than 600mb
      runtime: '<40'          	# ..and total runtime < 40 minutes

  'half-hour videos':
    profile: 'x264'             # use profile called "x264"
    rules:
      source_size: '>500'       # 400mb file size or greater
      runtime: '<31'        	# 30 minutes or less runtime
      vcodec: '!hevc'	       	# NOT hevc encoded video

  'default':                       # this will be the DEFAULT (no criteria implies a match)
      profile: hevc_hd_preserved   # use profile named "hevc_hd_preserved"
```

Since there are people who will run this script in synchronous mode, the *concurrent_jobs* value should be set to 1.
There really is no good reason to increase this number if you are not using hardware transcoding as the CPU will be fully engaged already.


### Sonarr-aware
You can invoke pytranscoder from a Sonarr custom script connection to handle recording of downloads and upgrades
to your queue file.  The filename passed from Sonarr will be appended to your default_queue_file (see global configuration above).
Media is not transcoded at this time, only recorded for future processing.  Simply having Sonarr call pytranscoder is all you need
to configure - pytranscoder will detect it was invoked from Sonarr and act accordingly.  No parameters are required.

### Profiles and Rules

A _profile_ is a named group of *ffmpeg* commandline options to transcode a specific way. You can
define all the combinations you use regularly in *transcode.yml* for easy selection later.
At least 1 profile definition is required.

A rule is a YAML syntax of predefined predicates to allow simple matching on source media details
and match to a specific profile.  For example, if you transcode 720p differently than 1080p, and still different
than 4k you can set up rules to match those 3 resolutions to a specific transcode profile.
Easy - let the script do the work of selecting the right *ffmpeg* options.

But you aren't required to use rules.  You can specify the profile on the commandline each
run using the -p option. Or you can define 1 rule that acts as a default (see example above).

When changing or adding profiles and rules it is useful to test them out by running in *--dry-run* mode first, which will show you everything that would happen if running for real.

### Process Flow
- Determine list of input files to transcode
    - If a profile is given (-p) make that the starting default to use for all subsequent media.
    - If a list file is given, read list of media files from that file.
    - If media files are given on the command line, add those to the list, observing any -p profile overrides along the way.
- Check concurrency value and allocate additional threads, if applicable.
    - If running concurrent, interactive transcoding stats and screen logging for *ffmpeg* will be disabled.
 - If running in --dry-run mode:
    - For each media file print "what-if" transcoding details
    - Exit script execution
- For each media file do the transcoding:
   - If file has no given profile assignment, use the rules system to find a match. If no match, skip
   - When file has finished transcoding:
       - If the selected profile has a threshold value, compare original and transcoded file size.
          - If threshold met:
             - If -k not given, remove original and replace with newly transcoded .tmp file.
             - If -k given, keep the original and leave the transcoded .tmp version in place for inspection.
          - If threshold not met, inform user and remove .tmp file leaving original intact.
       - If -k not given, remove original and replace with newly transcoded .tmp file.
       - If a list file (queue) was used, the completed media file will be removed from that list.
- Exit script execution

### Running without Concurrency
If you cannot transcode concurrently, or just don't want to you can still get value from this script.  Just edit the transcode.yml file as described above and change concurrent_jobs to 1.  You still get the use of profiles
and rules to help with your transcoding needs.

### Notes on Concurrency

Concurrency here means running multiple transcoding jobs at the same time by taking advantage of hardware support.
Normally a transcode will almost max out a CPU until it is finished. But with hardware-assisted transcoding
very little of the CPU is used and most work is offloaded to the hardware. This allows the CPU to handle
multiple files and still have processing power left over for regular system activities.

To change the concurrent jobs default you must edit *transcode.yml*, look for *concurrent_jobs*, and 
change its value from 2 to whatever your system can handle, or 1 to disable. You must also supply the
appropriate options for your transcode profiles to use the supported hardware, otherwise you'll
completely bog down your system (see the transcode.yml "hevc" and "qsv" samples). If you transcode with a profile not
setup for hardware support, or the rules matcher selects a profile without hardware support, that file will
transcode using CPU time. Therefore, when using concurrent hardware transcoding using rules it is best that all your rules map
to only profiles with hardware support.  You can always run non-concurrent CPU-based transcodes from
the command line, selecting sequential-only (-s) and bypassing profile rules.


### Typical Use-Case
My *concurrent_jobs* is set to 2.  I run on Ubuntu with a nVidia GTX 960 card with 4gb, which allows me 2 concurrent transcodes using very little CPU.
If you have a more powerful card with more memory you can try increasing the value. An 8gb nVidia card you will likely support 
4 concurrent sessions. Monitor carefully to find the performance sweet spot for your needs.

I use Sonarr to curate my library.  When items are downloaded I have a post script that records those items in a shared "queue" file, which is just a list of media files - full pathnames.
Routinely I run the *pytranscoder* to walk through my accumulated list to transcode everything. But, there are things I do not want transcoded so I use the rules as a way to skip those videos.
Also, I transcode some things differently. There are rules for those too.  And finally, I 
sometimes just want to transcode some files very specifically in a way that isn't compatible
with hardware transcoding, so I'll run the tool using -p and -s options.  Using the rules system is helpful if you have multiple profile needs and are automating
your transcoding in a _cron_ job or just want to fire it off and walk away. 

### Running

Note that if using a list file (queue) as input, when the process is done that file will contain only those
video files that failed to transcode, or it will be removed if all files were processed. So if you need to keep
this file make a copy first.

The default behavior is to remove the original video file after transcoding and replace it with the new version.
If you want to keep the source *be sure to use the -k* parameter.  The transcoded file will be placed in the same
folder as the source with the same name and a .tmp extension.

To get help:
```bash
   pytranscoder -h
```

To transcode 2 files using a specific profile:
```bash
    pytranscoder -p my_fave_x264 /tmp/video1.mp4 /tmp/video2.mp4
    
```

To auto transcode a file but keep the original:
```bash
    pytranscoder -k testvid.mp4
```

To transcode 2 files using different profiles:
```bash
    pytranscoder -p my_fave_x264 /tmp/video1.mp4 -p cuda_hevc  /tmp/video2.mp4
    
```

To auto transcode everything in a queue file, defaulting to rules to match profiles:
```bash
    pytranscoder --from-file /tmp/queue.txt
    
```
To do a test run without transcoding, to see which profiles will match and the *ffmpeg* commandline:
```bash
    pytranscoder --dry-run atestvideo.mp4

```

To transcode everything in a queue file, using a forced profile for all:
```bash
    pytranscoder -p cuda_hevc --from-file /tmp/queue.txt
    
```

If configured for concurrency but want to auto transcode a bunch of files sequentially only:
```bash
    pytranscoder -s *.mp4
```
