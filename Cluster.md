## pytranscoder - cluster mode

Python wrapper for ffmpeg for batch, concurrent, or clustered transcoding

This script is intended to help automate encoding for people who do a lot of it.

This documentation is specific to the clustering functionality of the tool.  It is separate from the main
docs, README.md, because it is a more advanced feature.

### System Setup
We will refer to the machine you use pytranscode on as your *cluster manager* and other machines as *hosts*.

Setting up remote hosts is as follows, if not already setup for ssh access and ffmpeg:
#### Linux
Linux is natively supported as long as the following conditions are true:
* Each host machine in the cluster is running an ssh server.
* Each host has ffmpeg installed.
* If using hardware encoding, your machine (and ffmpeg) have been setup and tested to make sure it is working. Setup of hardware encoding is beyond the scope of this doc.
* The *cluster manager* machine must be able to ssh to each host without a password prompt (see `man ssh-copy-id`).
#### MacOS
MacOS, being based on BSD, is also natively supported.  See Linux section. Check your MacOS version of ffmpeg for what hardware acceleration support is available, if any. At the time of this writing there was nothing available of appreciable quality, only VAAPI and the quality was dismal.
#### Windows 10
**Windows is only supported as a cluster manager if installed and run under WSL**

There are 2 ways to enable SSH access for Windows. Each method is further complicated depending on which ffmpeg you use.  These instructions assume a certain level of proficiency with Windows and optionally WSL.

**Windows SSH**:
> This method will only allow streaming cluster support due to Windows OpenSSH not being able to access network shares.

> * Enable OpenSSH server
* Enable your OpenSSH server via the Windows Services control panel.
* Start server

> In the home folder of the user account create a directory called **.ssh**.  Then from your *cluster manager* copy your **$HOME/.ssh/id_rsa.pub** to **c:/Users/*username*/.ssh/authorized_keys** on Windows.
>
>Finally, if you have a supported nVidia card download the nVidia CUDA drivers and install if you plan on using CUDA encoding.
It's a large download. Choose Custom install and deselect all the documentation and other things you don't need if you want to
minimize space usage.

When pytranscoder starts it will verify that it can ssh to each host using the provided configuration before continuing.


#### Configuration

If you skipped right to this documentation you need to read the [README](https://github.com/mlsmithjr/transcoder/blob/master/README.md) first.

Each of your hosts can be designated as *mounted*, *streaming*, or *agent*. 
A *mounted* host is one that has network access to the same media you are transcoding via a NFS or Samba/CIFS mount. This is the ideal configuration since files need not be copied to and from a host - they are already shared.
A *streaming* host is one that does not have network access to the media. This most likely will be due to not having the ability to setup a network share on that host. Each file to be encoded is copied to that host using **scp** (ssh), encoded, then the output copied back to your *cluster manager*. This is very inefficient, but works.
A *agent* host has pytranscoder installed and performs the encoding operations for the *cluster manager* (no ssh enablement required).

There is a section in the transcode.yml file, under the global *config* section, called *clusters*. A cluster is a
group of one or more host machines you will use for encoding.  You may define multiple clusters if you have a large
network of machines at your disposal. **Note**: all hosts in the cluster do not need to be available at runtime - they
will simply be ignored and other hosts in the cluster used.

Add an **ssh** item to your global configuration (location of your *cluster manager* ssh client), then define the cluster:

Sample
```yaml
config:
  
  ssh:                '/usr/bin/ssh'    # used only in cluster mode
  
  ###################### 
  # cluster definitions
  ###################### 
  clusters:
    household:                  # name for this cluster

      ################################# 
      # cluster manager, which will 
      # also participate in the cluster
      ################################# 
      mediacenter:
        type: local		# Indicates this is where pytranscoder is running and can be used in the cluster as well.
        ffmpeg:         '/usr/bin/ffmpeg'
        status:          'enabled'
  
      ################################# 
      # My old MacPro booted into Ubuntu 
      ################################# 
      macpro:                   # name of this host (does not need to be the same as network hostname)
        type:  mounted           # machine with source media and host share a filesystem (nfs, samba, etc)
        os:    macos               # choices are linux, macos, win10
        ip:    192.168.2.65
        user:  sshuser           # user account used to ssh to this host
        ffmpeg:      '/usr/bin/ffmpeg'
        path-substitutions:     # optional, map source pathnames to equivalent on host
          - /volume1/media/ /media/
        profiles:               # profiles allowed on this host
          - hevc
          - h264
        status: 'enabled'         # set to disabled to temporarily stop using

      ################################# 
      # My son's gaming machine
      ################################# 
      gamer:                    # machine configured with Windows OpenSSH server
        type:   streaming         # host not using shared filesystem
        os:     win10               # choices are linux, macos, win10
        ip:     192.168.2.64        # address of host
        user:   matt              # ssh login user
        working_dir: 'c:\temp'  # working folder on remote host, required for streaming type
        ffmpeg:      'c:/ffmpeg/bin/ffmpeg'
        profiles:               # profiles allowed on this host
          - hevc_cuda
          - hevc_qsv
        queues:
          qsv: 1
          cuda: 2
        status: 'enabled'         # set to disabled to temporarily stop using

      ################################# 
      # Spare family machine
      ################################# 
      family:
        type:  agent
        os:    win10
        ip:    192.168.2.66
        user:  chris
        ffmpeg: c:/ffmpeg/bin/ffmpeg.exe  # using Windows ffmpeg.exe build
        profiles:               # profiles allowed on this host
          - hevc_cuda
          - hevc_cuda_10bit
        queues:
          qsv: 1
          cuda: 1
        status: enabled
```

| setting      | purpose |
| -----------   | ----------- |
| type          | Host type, either *mounted*, *streaming*, or *agent*. There can be one host in all clusters with type *local*. A *mounted* type indicates the input media files are accessible via a shared filesystem mounted on the host. A *streaming* type indicates no sharing, and each media file being encoded is copied to that host, encoded, then copied back.  A *local* type is used to also include the *cluster manager* machine (system running pytranscoder) in the cluster so it won't sit idle, and is  optional. There are fewer required configuration attributes for this type. |
| os      | One of linux,macos, or win10. **[1]** |
| ip            | Address or host name of the host.  **[1]**  |
| user          | User to log into this host as via ssh. The user must be pre-authenticated to the host so that a password is not required. See https://www.ssh.com/ssh/copy-id.  **[1]** |
| ffmpeg        | Path on the host to ffmpeg. |
| working_dir   | Indicates the temporary directory to use for encoding.  **[2]** |
| profiles       | The allowed profiles to use for all encodes on this host. If not provided, assumes all. A video input matching a profile that is not assigned to a particular host will be run on a host that will, if any. This is how, for example, you restrict CPU-based encodings to hosts with no hardware acceleration - or vice versa. In other words, you control how each host is used by which profiles it supports. |
| path-substitutions | Optional. Applicable only to *mounted* type hosts. Use when the server media files and host mount paths are different. |
| queues   | Optional. You can define per-host queues to enable concurrent jobs on each host.  If not given, encoding jobs will run 1 at a time.  See README.md for further discussion of queues. |
| status        | *enabled* or *disabled*. Disabled hosts will be skipped. Default is *enabled*.|

**[1]** Required for *mounted* and *streaming* types.
**[2]** Required for *streaming* type.


#### Sample Walkthrough

You have a media server called **mediaserver**. It has an NFS-exported path to the root of your media storage. This folder is 
on a RAID mounted at /volume1/media. You want to enable all the machines in your household to be used for encoding. You want to
transcode all media to HEVC because it's just better, but it's very time-consuming so you decide to use other machines that
are under-utilized for such tasks. You create a special user account on all hosts just for encoding and setup password-less ssh login to each host using *ssh-copy-id*.
You plan to kick off clustered encoding from **mediaserver**, using 2 other machines to do the work.

You have another machine, your main workstation, which is called **workstation**. This machine mounts the **mediaserver** export as /mnt/media for easy sharing. It has no CUDA-enabled graphics card but does have an 8th generation Intel i5 supporting QSV.

Your last machine is a shared machine your kids sometimes use, called **shared**. It has a great nVidia graphics card, but does not mount the media filesystem exported from **mediaserver**.

Here is the configuration for the scenario above:

```yaml
  clusters:
    household:                  # name for this cluster
      workstation:
        type: mounted
        ip: 192.168.2.63
        user: encodeuser
        ffmpeg: '/usr/bin/ffmpeg'
        path-substitutions:      # optional, map source pathnames to equivalent on host
          - /volume1/media/ /mnt/media/
        profiles:
          - qsv
  
      shared:
        type: streaming
        ip: 192.168.2.64
        user: encodeuser
        working_dir: '/tmp'
        ffmpeg: '/usr/bin/ffmpeg'
        profiles:
          - hevc_cuda

```

Not really much of a cluster, but just for illustration purposes.
Now, assuming you have a bunch of media files on **mediaserver** you want to transcode:

```bash
    ls /volume1/media
    
    file1.mp4  file2.mp4  file3.mp4
```
Let's do a dry run to see what will happen:

```bash
pytranscoder --dry-run -c household /volume1/media/*.mp4

----------------------------------------
Filename : file1.mp4
Host: workstation (mounted)
Profile  : qsv
ffmpeg   : -y -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi -i /volume1/media/file1.mp4 -vf scale_vaapi=format=p010 -c:v hevc_vaapi -crf 18 -c:a copy -c:s copy -f matroska -max_muxing_queue_size 1024 /volume1/media/file1.mkv.tmp

----------------------------------------
Filename : file2.mp4
Host: shared (streaming)
Profile  : hevc_cuda
ffmpeg   : -y -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi -i /volume1/media/file2.mp4 -vf scale_vaapi=format=p010 -c:v hevc_vaapi -crf 18 -c:a copy -c:s copy -f matroska -max_muxing_queue_size 1024 /volume1/media/file2.mkv.tmp

...
```
Running a --dry-run will check that the cluster machines are up, that **ssh** login works, and then perform the profile matchines, if applicable. Execution will then stop without doing any work.

To run for real:

```bash
    pytranscoder -c household /volume1/media/*
```

This will pick up each file in /volume1/media and queue them for encoding.  Two threads are started - one for **workstation** and
the other for **shared**.  Each thread examines the queue, pulling the next video to be transcoded until all files are
processed.

For **workstation**, a file is pulled from the queue, /volume1/media/file1.mp4 for instance. Since there is a *path-substitution*
configured, change the path to /mnt/media/file1.mp4.  Finally, ssh to **workstation** as _encodeuser_ and run ffmpeg to encode /mnt/media/file1.mp4 using QSV.
The temporary encoded file will be placed in the same folder as the source. 

For **shared**, a file is pulled from the queue, /volume1/media/file2.mp4 for instance, and copied to /tmp on that host. 
Then ssh to **shared** as _encodeuser_and run ffmpeg to encode /tmp/file2.mp4 using hevc_cuda. When finished, copy the encoded
file from **shared** back to **mediaserver** and remove temporary files from **shared** /tmp.

The last file, /volume1/media/file3.mp4, will be handled by the first host to finish the previous encodes. Once all have
been encoded the process will exit.

No encoding was performed on **mediaserver** - it was only used as the manager for the hosts in the cluster. You can easily add it to the cluster though and have 3 machines working.

Any defined host that isn't up and available when pytranscoder
is run will be ignored and transcoding will continue on other available hosts.

#### Testing your Setup

You should always do a dry-run test before committing to a configuration change. It will help you see that your defined rules are matching as expected and that hosts can be connected to via ssh.

```bash
    pytranscoder --dry-run -c mycluster /volume1/media/any_video_file
```

#### Running

Usage:
```bash
    pytranscoder -c <cluster1> files ... -c <cluster2> files ...
```

You can start 1 or multiple clusters, comprised of 1 or more hosts each.  You can assign different files to different
clusters, if your needs are that complex.

However, most people will simple run as:

```bash
    pytranscoder -c mycluster /volume1/media/*.mp4
```

To troubleshoot problems, use verbose mode
```bash
    pytranscoder -v -c mycluster /volume1/media/*.mp4

```

To force encode(s) to a specific host named 'wopr'
```bash
    pytranscoder -c mycluster -h wopr /volume1/media/*.mp4
```
To force all jobs to use a specific profile:
```bash
    pytranscoder -c mycluster -p best_profile /volume1/media/*.mp4
```

Or you can do combinations:
```bash
    pytranscoder -v -c mycluster -p best_profile -h wopr /volume1/media/*.mp4
```
