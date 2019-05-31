## pytranscoder

Workflow and job manager for ffmpeg transcoding.

There are 2 modes: **local** and **clustered**.  Local mode is the most common usage and is for running this script on the same machine where it is installed.  Cluster mode turns pytranscoder into a remote encoding manager.  In this mode it delegates and manages encode jobs running on multiple hosts.  This requires more advanced configuration and is documented separately in [Cluster.md](https://github.com/mlsmithjr/transcoder/blob/master/Cluster.md)


#### Features:
* Sequential or concurrent transcoding. 
* Concurrent mode allows you to make maximum use of your 
nVidia CUDA-enabled graphics card or Intel accelerated video (QSV)
* Preserves all streams but allows for filtering by audio and subtitle language.
* Configurable transcoding profiles
* Configurable rules and criteria to auto-match a video file to a transcoding profile
* Transcode from a list of files (queue) or all on the command line
* Cluster mode allows use of other machines See [Cluster.md](https://github.com/mlsmithjr/transcoder/blob/master/Cluster.md) for details.
* On-the-fly compression monitoring and optional early job termination if not compressing as expected.
* Optionally trigger Plex library update via API
* Handles Sonarr download events and logs file path to default queue for later batch processing

#### Requirements

* Linux or MacOS, Windows 10. For Windows, WSL (Ubuntu) recommended.
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* nVidia graphics card with latest nVidia CUDA drivers (_optional_)
* Intel CPU with QSV enabled (_optional_)
* Python 3 (3.6 or higher)
* Python PlexAPI package (optional).  Install with `pip3 install --user plexapi`

#### Support
Please log issues or questions via the github home page for now.

Video Tutorials: [Part 1 - Linux Setup](https://www.youtube.com/watch?v=LHhC_w34Kd0&t=5s), [Part 2 - Usage](https://www.youtube.com/watch?v=Os6UACDAOKA)

#### Documentation

[Read The Docs](https://pytranscoder.readthedocs.io/en/latest/)

