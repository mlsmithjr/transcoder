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

* latest *ffmpeg* (3.4.3-2 or higher)
* latest nVidia CUDA drivers (_optional_)
* Python 3 (3.6 or higher)
* Python PlexAPI package (optional).  Install with `pip3 install plexapi`

### Configuration
Since there are people who will run this script in synchronous mode, the *CONCURRENT_JOBS* value should be set to 1.
There really is no good reason to increase this number if you are not using hardware transcoding as the CPU will be
fully engaged already.

> To change the concurrent jobs default you must edit *transcode.py*, look for CONCURRENT_JOBS, and 
> change its value from 2 to whatever your system can handle, or 1 to disable. You must also supply the
> appropriate options for your transcode profiles to use the supported hardware, otherwise you'll
> completely bog down your system (see the transcode.yml "hevc" samples). If you transcode with a profile not
> setup for hardware support, or the rules matcher selects a profile without the setup, that file will
> transcode using CPU time. Therefore, when using concurrent hardware transcoding using rules it is best that all your rules map
> to only profiles with hardware support.  You can always run non-concurrent CPU-based transcodes from
> the command line, selecting sequential-only and bypassing profile rules.

Included with the source is a starting config file called *transcode.yml*.
This is a YAML-formatted file and contains definitions for some transcoding profiles and matching rules.
Use these sample to get started until I can write up detailed documentation.  You can specify the location of
the config file on the command line or just put it into *~/.transcode.yml*, which is the default location.

The basics are this: There are profiles and rules defined.  The profiles define all the different ways you want to transcode (different settings).
When you run the script you can force a specific transcode profile.
But, if you want to use the simple rule system you can define rules to select the appropriate transcoding profile for each video.
The bottom half of the config file defines those rules. As you can see it uses a YAML syntax to define simple filtering criteria.

### How I use this tool
My CONCURRENT_JOBS is set to 2.  I run on Ubuntu with a nVidia GTX 960 card with 4gb, which allows my 2 concurrent transcodes using very little CPU.
If you have a more powerful card with more memory you can try increasing the value.

I use Sonarr and Radarr to curate my library.  When items are downloaded I have a post script that records those items in a shared "queue" file, which is just a list of files - full pathnames.
Routinely I run the script to walk through my accumulated list of transcode everything. But, there are things I do not want transcoded so I use the rules as a way to skip those videos.
Also, I transcode some things differently. There are rules for those too.  And finally, I 
sometimes just want to transcode some files very specifically, so I'll run the tool using only 
command line options (forcing a profile and bypassing the rules).  Using the rules system is helpful if you are automating
your transcoding in a _cron_ job.

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