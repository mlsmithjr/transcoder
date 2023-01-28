## pytranscoder
Python wrapper for ffmpeg for batch, concurrent, or clustered transcoding using defined profiles and optional rules engine
for automation.

[Read The Docs](https://pytranscoder.readthedocs.io/en/latest/)


#### News

**Coming soon**

Version 3 will include an alternate means of configuring your setup.  Let's face it, all that YAML is confusing.
The new version will use templating and be far simpler and very much smaller -- all my converted profiles fit on one screen now.
Existing profile support will remain indefinitely for users with more complicated setups, but templates will appeal more to most users.


#### What it is
This script is intended to help automate transcoding for people encoding lots of video.
It is more than a wrapper - it is a workflow and job manager.

There are 2 modes: **local** and **clustered**.  Local mode is the most common usage and is for running this script on the same machine where it is installed.  Cluster mode turns pytranscoder into a remote encoding manager.  In this mode it delegates and manages encode jobs running on multiple hosts.  This requires more advanced configuration and is documented separately in [Cluster.md](https://github.com/mlsmithjr/transcoder/blob/master/Cluster.md)

The remainder of this document focuses on using pytranscoder in local mode.

#### Features:
* Sequential or concurrent transcoding. 
* Concurrent mode allows you to make maximum use of your 
nVidia CUDA-enabled graphics card or Intel accelerated video (QSV)
* Preserves all streams but allows for filtering by audio and subtitle language.
* Configurable transcoding profiles
* Configurable rules and criteria to auto-match a video file to a transcoding profile
* Mixins are profile fragments you can provide at runtime to dynmically change your selected profiles.
* Transcode from a list of files (queue) or all on the command line
* Cluster mode allows use of other machines See [Cluster.md](https://github.com/mlsmithjr/transcoder/blob/master/Cluster.md) for details.
* On-the-fly compression monitoring and optional early job termination if not compressing as expected.
* Experimental support for HandBrakeCLI

#### Requirements

* Linux or MacOS, Windows 10. For Windows, WSL (Ubuntu) recommended.
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* nVidia graphics card with latest nVidia CUDA drivers (_optional_)
* Intel CPU with QSV enabled (_optional_)
* Python 3 (3.7 or higher)

#### Support
Please log issues or questions via the github home page for now.

Video Tutorials: [Part 1 - Linux Setup](https://www.youtube.com/watch?v=LHhC_w34Kd0&t=5s), [Part 2 - Usage](https://www.youtube.com/watch?v=Os6UACDAOKA)

#### Installation

There are a few possible ways to install a python app - one of these should work for you.

**Linux**
 The confusion is due to the fact that not all distributions or OS's install pip3 by default. Either way, pytranscoder is available in the **pypi** repo.
```bash
pip3 install --user pytranscoder-ffmpeg
# or...
python3 -m pip install --user pytranscoder-ffmpeg 
```

**Windows (WSL - Ubuntu)**
Windows Subsystem for Linux is the best option, but requires a couple of maintenance steps first if you don't have pip3:
```bash
sudo apt update
sudo apt upgrade
sudo install python3-pip

# now we can install
pip3 install --user pytranscoder-ffmpeg
```
At this point you have a choice - either install ffmpeg for Windows [ffmpeg.exe](https://www.ffmpeg.org) or install in bash as an Ubuntu package. Either will work but there are caveats, or  you could install both and not worry.

* ffmpeg.exe can be run in Windows command shell or from bash but requires special attention when configuring pytranscoder paths.
* ffmpeg apt package can only be run from bash but is a more natural Linux path mapping.

After installing you will find this document and others in $HOME/.local/shared/doc/pytranscoder (on Linux/MacOS)
and in $HOME/AppData/Python/*pythonversion*/shared/doc/pytranscoder** (on Windows). Also available [online](https://github.com/mlsmithjr/transcoder/blob/master/README.md)

#### Upgrading

Whatever method above for installing works for you, just use the --upgrade option to update, ie:
```pip3 install --upgrade pytranscoder-ffmpeg```


#### Operation - Profiles and Rules

>A profile is a named group of *ffmpeg* commandline options to encode a specific way. You can
define all the combinations you use regularly in *transcode.yml* for easy selection later.
At least 1 profile definition is required.

>A rule is a YAML syntax of predefined predicates to allow simple matching on source media details
and relate to a specific profile.  For example, if you transcode 720p differently than 1080p, and still different
than 4k you can set up rules to match those 3 resolutions to a specific transcode profile.
Easy - let the script do the work of selecting the right *ffmpeg* options.

But you aren't required to use rules.  You can specify the profile name on the commandline each
run using the -p option. Or you can define 1 rule that acts as a default (see examples). It's up to you. But using rules is a great way to automate a tedious manual workflow.

When changing or adding profiles and rules it is useful to test them out by running in *--dry-run* mode first, 
which will show you everything that would happen if running for real.

#### Configuration

There is a supplied sample *transcode.yml* config file, or you can download it [here](https://github.com/mlsmithjr/transcoder/blob/master/transcode.yml).  This can be customized all you like, however be
sure to preserve the YAML formatting. Either specify this file on the commandline with the *-y* option
or copy it to your home directory as *.transcode.yml* (default)

There are 3 sections in the file:

#### config - Global configuration information

Sample
```yaml
config:
  default_queue_file:   '/path/to/default/list/of/files/if/none/given'
  ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg for this config
  ssh:                '/usr/bin/ssh'    # used only in cluster mode (optional)
  queues:
    qsv:                1                   # sequential encodes
    cuda:               2                   # maximum of 2 encodes at a time
  colorize:             yes
```

| setting      | purpose |
| ----------- | ----------- |
| default_queue_file    | A queue file is just a text file listing out all the media you want to encode. It is not required, but useful when automating a workflow. You can always indicate a queue file on the command line. This just sets the default, if any.   |
| ffmpeg                | Full path to ffmpeg on this host |
| ssh                   | Full path to ssh on this host |
| queues                | If using concurrency, define your queues here. The queue name is whatever you want. Each name specifies a maximum number of concurrent encoding jobs. If none defined, a default sequential queue is used. |
| colorize     | optional, defaults to "no". If "yes" terminal output will have some color added |

#### profiles - Transcoding profiles (ffmpeg options)

Profiles are used to provide ffmpeg with various options for encoding. One profile definition is required, but mostly likely
you will define multiples for different encoding scenarios.  The name of the profile can be provided on the command line
to select the appropriate one for your needs. Alternatively, you can define rules (see below) to auto-match media with profiles for a less manual encoding workflow.

Sample:
```yaml
profiles:

  # some common, reusable settings to keep things tidy
  common:
    output_options_subtitles:
      - "-c:s copy"
       - "-f matroska"
    output_options_audio:
      - "-c:a copy"
    output_options_video:
      - "-crf 20"
    extension: '.mkv'
    threshold: 20
    threshold_check: 30

  #
  # Sample Intel QSV transcode setup (note to customize options for your environment)
  #
  hevc_qsv:
    include: common
    output_options_video:         # mixin-enabled section - overrides common
      - "-c:v hevc_qsv"
      - "-preset medium"
      - "-qp 21"
      - "-b:v 7M"
    
  #
  # Sample nVidia transcode setup
  #

  hevc_cuda:                  # profile name
      include: common
      input_options:          # ffmpeg input options
        - "-hwaccel cuvid"    # REQUIRED for CUDA
        - "-c:v h264_cuvid"   # hardware decoding too
      output_options_video:   # mixen-enabled - overrides common
        - "-c:v hevc_nvenc"   # REQUIRED for CUDA
        - "-profile:v main"
        - "-preset medium"
      output_options_audio:
        - "-c:a copy"
      
      queue: cuda		# manage this encode in the 'cuda' queue defined globally
      
      # optionally you can filter out audio/subtitle tracks you don't need
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
  #
  # This is a mixin, a profile fragment that can be provided on the command line
  # to alter a profile (ie. pytranscoder -p hevc_cuda -m mp3_hq file.mp4)

  mp3_hq:
    output_options_audio:
      - "-c:a mp3lame"
      - "-b:a 384k"

  x264:                            # profile name
      include: common
      input_options: 
      output_options:
        - "-c:v x264"
        
h264_cuda_anime:
    include: common
    input_options:
    output_options:
      - "-c:v h264_nvenc"
      - "-tune animation"
 
```

| setting               | purpose |
| -----------           | ----------- |
| input_options         | ffmpeg options related to the input (see ffmpeg docs)  |
| output_options        | ffmpeg options related to the output (see ffmpeg docs). Use for generic options, not mixin-enabled |
| output_options_video  | ffmpeg options specific to video (see ffmpeg docs). This section is mixin-enabled |
| output_options_audio  | ffmpeg options specific to audio (see ffmpeg docs). This section is mixin-enabled |
| extension             | Filename extension to use for the encoded file |
| queue                 | optional. Assign encodes for this profile to a specific queue (defined in *config* section)   |
| threshold             | optional. If provided this number represents a minimum percentage compression savings for the encoded media. If it does not meet this threshold the transcoded file is discarded, source file remains as-is, and the source job marked as complete. This is useful if a particular file doesn't compress much and you would rather just keep the original. |
| threshold_check       | optional. If provided this is the percent done to start checking if the threshold is being met. Default is 100% (when media is finished). Use this to have threshold checks done earlier to stop a long-running transcode if not producing expected compression (threshold).|
| include               | optional. Include options from one or more previously defined profiles. (see section on includes). |
| audio                 | Audio track handling options. Include a list of **exclude_languages** to automatically remove tracks. If any track being removed is a _default_, a new default will be set based on the **default_language**. |
| subtitle              | See _audio_ above. |

> CPU Note: When transcoding from h264 on an Intel I5/I7 6th+ gen chip, _ffmpeg_ will use detected extensions to basically perform hardware decoding for you. So if you configured hardware encoding you'll see low CPU use. On AMD there is no chip assistance on decoding.  So even if hardware encoding, the decoding process will load down your CPU. To fix this simply enable hardware decoding as an **input option**.

#### rules - simple profile matching rules

Simple expressions to match video files with the appropriate profile. They are evaluated top-down so
make sure your default is the last one. You don't need to use the rules system. You can either
explicitly give the desired profile name on the commandline or just have a single rule for default.
But if you encode certain media differently then having the rules system make it a little easier
using various options depending on the media attributes.  No specific criteria is required - use the ones
applicable to your rule.

Rule evaluation is as follows: for each input media file, compare against each rule criteria. All criteria of a rule must match
in order for the given profile to be selected.  If any one fails, evaluation continues to the next
rule. If there are no matches, the *default* rule is selected.

Samples:
```yaml
  'for content I consider too big':  # comment and unique identifier for this rule
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
      filesize_mb: '<600'       # video file is less than 600mb
      runtime: '<40'          	# ..and total runtime < 40 minutes

  'anime to h264 using tuning':
    profile: h264_cuda_anime
    criteria:
      filesize_mb: '>2500'   # larger than 2.5g
      vcodec: '!hevc'            # not encoded with hevc 
      path: '/media/anime/.*'  # in a anime folder (regex)
 
  'half-hour videos':
    profile: 'x264'             # use profile called "x264"
    criteria:
      filesize_mb: '>500'       # 400mb file size or greater
      runtime: '<31'        	# 30 minutes or less runtime
      vcodec: '!hevc'	       	# NOT hevc encoded video

  'small enough already':       # skip if <2.5g size, between 720p and 1080p, and between 30 and 64 minutes long.
      profile: SKIP             # transcoding these will probably cause a noticeable quality loss so skip.
      criteria:
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
provide the lower and upper range with a hyphen (-) between.  No spaces are allowed in criteria.

#### Sonarr-aware
You can invoke pytranscoder from a Sonarr custom script connection to handle recording of downloads and upgrades
to your queue file.  The filename passed from Sonarr will be appended to your default_queue_file (see global configuration above).
Media is not transcoded at this time, only recorded for future processing.  Simply having Sonarr call pytranscoder is all you need
to configure - pytranscoder will detect it was invoked from Sonarr and act accordingly.  No parameters are required.

#### Process Flow
High-level steps the script takes to process your media.

- Determine list of input files to transcode
    - If a profile is given (-p) make that the starting default
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

In the global profile section of *transcode.yml* you define your queues. Use whatever names you like, and provide a maximum number of concurrent jobs for that queue.  Use 1 for synchronous or a higher value to run multiples (but not more than your hardware can support - use trial and error to figure out, but 2 is a good number to stick with).

You can optionally designate a specific queue for each of your profiles.  If none defined, the *default* queue is used, which is sequential.  What queue assigned allows is finer management of concurrent transcoding jobs.  Queues are not necessary if you only plan to transcode sequentially.

>If you want maximum use of your machine consider this scenario:
>
>You have an 8th generation Intel i5 6-core machine with nVidia graphics card that can handle 2 concurrent encodes. You define 2 queues:
```yaml
     queues:
        one: 1
        two: 2
```
> You have 2 profiles: "qsv" (configured to use Intel QSV) and "cuda" (configured for nVidia CUDA).  You associate the "qsv" profile with queue **one**, and "cuda" with queue **two**.  You start a job like:
```bash
pytranscoder -p qsv /media/tv/new/*.mp4 -p cuda /media/movies/new/*.mp4
```
> This example will run 3 concurrent jobs - 1 running on the CPU using QSV and 2 running on the nVidia card!
> This is how a multi queue configuration can be used. But I hope you have good system fans.

You must also supply the appropriate options for your transcode profiles to use the supported hardware, otherwise you'll
completely bog down your system (see the transcode.yml "hevc" and "qsv" samples). If you transcode with a profile not
setup for hardware support, or the rules matcher selects a profile without hardware support, that file will
transcode using CPU time. Therefore, when using concurrent hardware transcoding using rules it is best that all your rules map to only profiles with hardware support.

You can always force non-concurrent CPU-based transcodes from the command line, selecting sequential-only (-s) and bypassing profile rules.


#### Testing your Setup

You should always do a dry-run test before committing to a configuration change. This will show you
how your media will be handled but won't actually do any work or change anything. It will help you
see that your defined rules are matching as expected and that hosts can be connected to via ssh.

```bash
    pytranscoder --dry-run /volume1/media/any_video_file
```

#### Running

Note that if using a list file (queue) as input, when the process is done that file will contain only those
video files that failed to encode, or it will be removed if all files were processed. So if you need to keep
this file make a copy first.

**The default behavior is to remove the original video file after encoding** and replace it with the new version.
If you want to keep the source *be sure to use the -k* parameter.  The work file will be placed in the same
folder as the source with the same name and a .tmp extension while being encoded.


| option                | purpose |
| -----------           | ----------- |
| --from-file <file>    | Load list of files to process from <file>  |
| -p <profile>          | Specify <profile> to use. Can be used multiple times on command line and applies to all subsequent files (see examples)  |
| -y <config>           | Specify non-default transcode.yml file.  |
| -s                    | Force sequential mode (no concurrency event for concurrent queues) |
| -k                    | Keep original media files, leave encoded .tmp file in same folder. |
| --dry-run             | Show what will happen without actually doing any work |
| -v                    | Verbose output. Show more processing details, useful for debugging |
| -c <name>             | Cluster mode. See Cluster.md for details |
| -m name{,name...}     | Add named mixin(s) to the given profile (-p)

##### Examples:

To get help and version number:
```bash
   pytranscoder -h
```

To transcode 2 files using a specific profile:
```bash
    pytranscoder -p my_fave_x264 /tmp/video1.mp4 /tmp/video2.mp4
    
```

To use a profile but alter the audio track using a mixin:
```bash
    pytranscoder -p hevc_cuda -m mp3_hq videofile.mp4
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

Complex example to show off flexibiliity. Using custom config file *test.yml*, keep original media, transcode
all mp4 files in /media1 using rules,, transcode all files in /media2 using hevc_cuda profile, and 
transcode all files listed in listoffiles.txt using qsv profile:
```bash
    pytranscoder -y /home/me/test.yml -k /media1/*.mp4 -p hevc_cuda /media2/* -p qsv --from-file /tmp/listofiles.txt
```

If configured for concurrency but want to auto transcode a bunch of files sequentially only:
```bash
    pytranscoder -s *.mp4
```

To run in cluster mode (see Cluster documentation):
```bash
    pytranscoder -c *.mp4
```

#### Using includes
This feature requires a deeper familiarity with the YAML format. Essentially, you can define a partial profile or a full one and later "include" it into another profile. This facilitates reuse of definitions and simpler profiles.

```yaml
#
# Merge-style example
#
profiles:
    # values universal to all my high-quality transcodes
    hq:
      output_options:  # options using hyphens and separate lines are "lists"
        - "-crf 18"
        - "-preset slow"
        - "-c:a copy"
        - "-c:s copy"
        - "-f matroska"
      threshold: 20
      extension: ".mkv"
  
    hevc_cuda:
      include: hq     # pull in everything defined above in "hq"
      output_options: # combine these options with those from "hq"
        - "-c:v hevc_nvenc"
        - "-profile:v main"
      threshold: 18    # replace "hq" threshold value with 18
```

The above example is equivalent to:
```yaml
  hevc_cuda:
    output_options: -crf 18 -preset slow -c:a copy -c:s copy -f matroska -c:v hevc_nvenc -profile:v main
    threshold : 18
    extension: ".mkv"
```
The advantage is that now we have a base (parent) profile we can include into many others to avoid repetative profile definitions.  And, if we decide to change our base threshold, for example, we only need to change it in the base (parent).
  
Note that the profiles "hq" and "hevc_cuda" were combined, and the value for threshold was overridden to 18.
Lets refer to the first (base) profile as the parent, and the second as the child. So a child profile can include one or more parent profiles.  All values in the child are retained. However, if input_options or output_options are lists instead of strings, the parent and child values will be combined.
Here is the same example slightly reformatted:
  
```yaml
#
# Replace-style example
#
  profiles:
    hq:
      output_options: -crf 18 -preset slow -c:a copy -c:s copy -f matroska
      threshold: 20
      extension: ".mkv"
  
    hevc_cuda:
      include: hq
      output_options: -c:v hevc_nvenc -profile:v main
      threshold: 18
```
This will produce a bad profile. Now I need to mention a feature of YAML only used in the **include** examples - lists.  YAML-formatted data can be very complex but pytranscoder requirements are meager and simple.  But to support the include feature in both _replace_ and _merge_ modes I needed another way to express input and output options.
Note the difference in the Merge and Replace examples is that Merge uses hyphens and a separate line for the output_options sections.  In Replace, all the options are on a single line.  The former is an expression of a "list of arguments".  The latter is just a "string of arguments" When a parent and child both have input_options or output_options that are lists, the two are combined.  If either is not a list (just a string), then the child wins and the parent version is ignored.
With this new information we can now see why the Replace example produces a bad profile.  It will look like this:
```yaml
    hevc_cuda:
      output_options: -c:v hevc_nvenc -profile:v main
      threshold: 18
      extension: ".mkv"
```
Since _output_options_ is a simple string rather than list, pytranscoder doesn't know how to merge them so it doesn't try.  The child values always wins.  So this profile will produce undesirable results because the parent options weren't merged.  Convert both back to lists and it will work again.

