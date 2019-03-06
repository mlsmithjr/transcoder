## pytranscoder

Python wrapper for ffmpeg for batch, concurrent, or clustered transcoding

This script is intended to help automate transcoding for people running a media server or encoding lots of video.

#### Features:
* Sequential or concurrent transcoding. 
* Concurrent mode allows you to make maximum use of your 
nVida CUDA-enabled graphics card or Intel accelerated video (QSV)
* Encode concurrently using CUDA and QSV at the same time.
* Configurable transcoding profiles
* Configurable rules to auto-match a video file to a transcoding profile
* Transcode from a list of files (queue) or all on the command line
* Cluster mode allows use of other machines See [Cluster.md](https://github.com/mlsmithjr/transcoder/blob/master/Cluster.md) for details.
* Optionally trigger Plex library update via API
* Handles Sonarr download events and logs file path to default queue for later batch processing

#### Requirements

* Linux or MacOS, Windows 10. For Windows, WSL recommended.
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* nVidia graphics card with latest nVidia CUDA drivers (_optional_)
* Intel CPU with QSV enabled (_optional_)
* Python 3 (3.6 or higher)
* Python PlexAPI package (optional).  Install with `pip3 install --user plexapi`

#### Support
Please log issues or questions via the github home page for now.


#### Installation

There are a few possible ways to install a python app - one of these should work for you.
```
pip3 install --user pytranscoder-ffmpeg
# or...
python3 -m pip install --user pytranscoder-ffmpeg 
# or...
python -m pip install --user pytranscoder-ffmpeg   # the Windows 10 way

```

After installing you will find this document and others in **$HOME/.local/shared/doc/pytranscoder** (on Linux/MacOS)
and in **$HOME/AppData/Python/*pythonversion*/shared/doc/pytranscoder** (on Windows).

#### Operation - Profiles and Rules

A profile is a named group of *ffmpeg* commandline options to encode a specific way. You can
define all the combinations you use regularly in *transcode.yml* for easy selection later.
At least 1 profile definition is required.

A rule is a YAML syntax of predefined predicates to allow simple matching on source media details
and match to a specific profile.  For example, if you transcode 720p differently than 1080p, and still different
than 4k you can set up rules to match those 3 resolutions to a specific transcode profile.
Easy - let the script do the work of selecting the right *ffmpeg* options.

But you aren't required to use rules.  You can specify the profile on the commandline each
run using the -p option. Or you can define 1 rule that acts as a default (see examples).

When changing or adding profiles and rules it is useful to test them out by running in *--dry-run* mode first, 
which will show you everything that would happen if running for real.



#### Configuration

There is a supplied sample *transcode.yml* config file.  This can be customized all you like, however be
sure to preserve the YAML formatting. Either specify this file on the commandline with the *-y* option
or copy it to your home directory as *.transcode.yml* (default)
IF you installed via pip you will find the sample in either $HOME/.local/share/doc/pytranscoder/ (if installed with --user) 
or /usr/share/doc/pytranscoder (if installed globally)

There are 3 sections:

#### config - Global configuration information

Sample
```yaml
config:
  default_queue_file:   '/path/to/default/list/of/files/if/none/given'
  ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg for this config
  ssh:                '/usr/bin/ssh'    # used only in cluster mode
  queues:
    qsv:                1                   # sequential encodes
    cuda:               2                   # maximum of 2 encodes at a time
  plex_server:          192.168.2.61:32400  # optional, use 'address:port'
```

| setting      | purpose |
| ----------- | ----------- |
| default_queue_file    | A queue file is just a text file listing out all the media you want to encode. It is not required, but useful when automating a workflow. You can always indicate a queue file on the command line.     |
| ffmpeg                | Full path to ffmpeg on this host |
| ssh                   | Full path to ssh on this host |
| queues                | If using concurrency, define your queues here. The queue name is whatever you want. Each name specifies a maximum number of concurrent encoding jobs. If none defined, a default sequential queue is used. |
| plex_server           | optional, if you want your Plex server notified after media is encoded. Use address:port format. |

#### profiles - Transcoding profiles (ffmpeg options)

Profiles are used to provide ffmpeg with various options for encoding. One profile definition is required, but mostly likely
you will define multiples for different encoding scenarios.  The name of the profile can be provided on the command line
to select the appropriate one for your needs. Alternatively, you can define rules (see below) to auto-match media with profiles
for a less manual encoding workflow.

Sample:
```yaml
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

| setting          | purpose |
| -----------      | ----------- |
| input_options    | ffmpeg options related to the input (see ffmpeg docs)  |
| output_options   | ffmpeg options related to the output (see ffmpeg docs)  |
| extension        | Filename extension to use for the encoded file |
| threshold        | optional. If provided this number represents a minimum percentage compression for the encoded media. If it does not meet this threshold the transcoded file is discarded and the source job marked as complete. This is useful if a particular file doesn't compress much and you would rather just keep the original. |


#### rules - simple profile matching rules

Simple expressions to match video files with the appropriate profile. They are evaluated top-down so
make sure your default is the last one. You don't need to use the rules system. You can either
explicitly give the desired profile name on the commandline or just have a single rule for default.
But if you encode certain media differently then having the rules system make it a little easier
using various options depending on the media attributes.  No specific criteria is required - use the ones
applicable to your rule.
The name of each rule is just a brief string describing the rule and is displayed in output to confirm which profile
was selected for encoding.

Rule evaluation is as follows: for each input media file, compare against each rule criteria. They must all match
in order for the given profile to be selected for encoding.  If any one fails, evaluation continues to the next
rule. If there are no matches, the *default* rule is selected.

Samples:
```yaml
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

  'small enough already':       # skip if <2.5g size and higher than 720p and between 30 and 64 minutes long.
      profile: SKIP             # transcoding these will probably cause a noticeable quality loss so skip.
      rules:
        filesize_mb: '<2500'    # less than 2.5 gigabytes
        res_height: '720-1081'  # 1080p, allowing for random oddball resolutions still in the HD range
        runtime:  '35-65'       # between 35 and 65 minutes long

  'default':                       # this will be the DEFAULT (no criteria implies a match)
      profile: hevc_hd_preserved   # use profile named "hevc_hd_preserved"
```

| setting      | purpose |
| ----------- | ----------- |
| profile       | The defined profile name (from above) to select if this rule criteria matches. If the profile name is *SKIP* then matched media will not be transcoded  |
| runtime       | Total run time of media, in minutes. Determined by ffmpeg. Optionally can use < or > or a range |
| source_size   | Size, in megabytes, of the media file. Optionally an use < or > or a range |
| fps           | Frames per second. Determined by ffmpeg. Optionally can use < or > or a range |
| vcodec        | Video codec used on the source media. Determined by ffmpeg. Can use ! to indicate *not* condition (negative match) |
| res_height    | Video vertical resolution. Determined by ffmpeg. Optionally can use < or > or a range |
| res_width     | Video horizontal resolution. Determined by ffmpeg. Optionally can use < or > or a range |

So, for example, using the sample rule *'for content I consider too big'*, if the video is less than 180 minutes long and the file
size is larger than 5 gigabytes and frames-per-second is greater than 25 then use the hevc_hd_25fps profile to encode.

For those settings that allow operators, put the operator first (< or >) followed by the number. For those that allow a range
provide the lower and upper range with a hyphen (-) between.  No spaces are allowed in any setting values.

#### Sonarr-aware
You can invoke pytranscoder from a Sonarr custom script connection to handle recording of downloads and upgrades
to your queue file.  The filename passed from Sonarr will be appended to your default_queue_file (see global configuration above).
Media is not transcoded at this time, only recorded for future processing.  Simply having Sonarr call pytranscoder is all you need
to configure - pytranscoder will detect it was invoked from Sonarr and act accordingly.  No parameters are required.

#### Process Flow
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

#### Running without Concurrency
If you cannot transcode concurrently, or just don't want to you can still get value from this script. 
Just avoid defining any queues, or define them with a value of 1 (see global config section).

#### Notes on Concurrency

Concurrency here means running multiple encoding jobs at the same time by taking advantage of hardware support.
Normally an encode run will almost max out a CPU until it is finished. But with hardware-assisted encoding
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


#### Typical Use-Case
I run on Ubuntu with a nVidia GTX 970 card with 4gb, which allows me 2 concurrent transcodes using very little CPU. So I
have defined a queue called "cuda", set to 2, that I assign to all my profiles in which I specify nVidia hardware encoding.
This means that all media matched to those profiles will be queued to encode 2 at a time using nVidia CUDA.
If you have a more powerful card with more memory you can try increasing the value. An 8gb nVidia card you will likely support 
4 concurrent sessions. Monitor carefully to find the performance sweet spot for your needs.

I also have an 8th generation Intel i5 6-core which allows me to use Intel QSV encoding, which is the Intel encoder/decoder on
the CPU itself. It support h264 and h265. Intel-based encoding is slower than CUDA but produces a slightly smaller file, and
arguably slightly better quality.  So I defined a queue called "qsv", set to 1, that I assign to all my profiles in which
I specify QSV encoding.

If I wanted to max out my hardware I could encode using both queues at the same time, resulting in a total of 3 concurrent
jobs running - 2 using the CUDA engine and 1 using QSV.  And I would still have plenty of CPU cycle remaining for system
activities.

I use Sonarr to curate my library.  When items are downloaded I have a post script that records those items in a shared "queue" file, which is just a list of media files - full pathnames.
Routinely I run the *pytranscoder* to walk through my accumulated list to transcode everything. But, there are things I do not want transcoded so I use the rules as a way to skip those videos.
Also, I transcode some things differently. There are rules for those too.  And finally, I 
sometimes just want to transcode some files very specifically in a way that isn't compatible
with hardware transcoding, so I'll run the tool using -p and -s options.  Using the rules system is helpful if you have multiple profile needs and are automating
your transcoding in a _cron_ job or just want to fire it off and walk away. 

#### Testing your Setup

You should always do a dry-run test before committing to a configuration change. This will show you
how your media will be handled but won't actually do any work or change anything. It will help you
see that your defined rules are matching as expected and that hosts can be connected to via ssh.

```bash
    pytranscoder --dry-run -c mycluster /volume1/media/any_video_file
```

#### Running

Note that if using a list file (queue) as input, when the process is done that file will contain only those
video files that failed to encode, or it will be removed if all files were processed. So if you need to keep
this file make a copy first.

The default behavior is to remove the original video file after encoding and replace it with the new version.
If you want to keep the source *be sure to use the -k* parameter.  The work file will be placed in the same
folder as the source with the same name and a .tmp extension while being encoded.


| option                | purpose |
| -----------           | ----------- |
| --from-file <file>    | Load list of files to process from <file>  |
| -p <profile>          | Specify <profile> to use. Can be used multiple times on command line and applies to all subsequent files (see examples)  |
| -y <config>           | Specify non-default transcode.yml file.  |
| -s                    | Force sequential mode. |
| -k                    | Keep original media files, leave encoded .tmp file in same folder. |
| --dry-run             | Show what will happen without actually doing any work |
| -v                    | Verbose output |
| -c <name>             | Cluster mode. See Cluster.md for details |



##### Examples:

To get help and version number:
```bash
   pytranscoder -h
```

To transcode 2 files using a specific profile:
```bash
    pytranscoder -p my_fave_x264 /tmp/video1.mp4 /tmp/video2.mp4
    
```

To auto transcode a file using the rules system but keep the original:
```bash
    pytranscoder -k testvid.mp4
```

To transcode 2 files using different profiles:
```bash
    pytranscoder -p my_fave_x264 /tmp/video1.mp4 -p cuda_hevc  /tmp/video2.mp4
    
```

To auto transcode everything in a specific queue file, defaulting to rules to match profiles:
```bash
    pytranscoder --from-file /tmp/queue.txt
    
```
To do a test run without transcoding, to see which profiles will match and the *ffmpeg* commandline:
```bash
    pytranscoder --dry-run atestvideo.mp4

```

To use a specific transcode.yml file and auto transcode using rules:
```bash
    pytranscoder -y /home/me/etc/transcode.yml *.mp4
```

To transcode everything in a queue file, using a forced profile for all:
```bash
    pytranscoder -p cuda_hevc --from-file /tmp/queue.txt
    
```

Complex example to show off flexibiliity. Using custom config file test.yml, keep original media, transcode
all mp4 files in /media1 using rules,, transcode all files in /media2 using hevc_cuda profile, and 
transcode all files listed in listoffiles.txt using qsv profile:
```bash
    pytranscoder -y /home/me/test.yml -k /media1/*.mp4 -p hevc_cuda /media2/* -p qsv --from-file /tmp/listofiles.txt
```

If configured for concurrency but want to auto transcode a bunch of files sequentially only:
```bash
    pytranscoder -s *.mp4
```

To run in cluster mode (see Cluster.md documentation):
```bash
    pytranscoder -c *.mp4
```
