## pytranscoder

Python wrapper for ffmpeg for batch, concurrent, or clustered transcoding

This script is intended to help automate transcoding for people running a media server.

This documentation is specific to the clustering functionality of the tool.  It is separate from the main
docs, README.md, because it is a more advanced feature.

#### System Setup
We will refer to the machine you use pytranscode on as your *cluster manager* and other machines as *hosts*.
>###### Linux
Linux is natively supported as long as the following conditions are true:
* Each host machine in the cluster is running an ssh server.
* The *cluster manager* machine must be able to ssh to each host without a password prompt (see `man ssh-copy-id`).
###### MacOS
MacOS, being based on BSD, is also natively supported.  See Linux section. Check your MacOS version of ffmpeg for what hardware support is available, if any.
###### Windows 10
* Install OpenSSH server
* Set server to auto-start
* Start server
* Copy RSA key from *cluster manager* 

> Install openssh server via `Settings > Apps > manage optional features > OpenSSH Server > Install`

>You cannot use ssh-copy-id to authenticate to openssh on Windows. Instead, in the home folder of the user account create
a directory called **.ssh**.  Then from your *cluster manager* copy your **$HOME/.ssh/id_rsa.pub** to **c:/Users/*username*/.ssh/authorized_keys** on Windows.

>In the search bar type **services* and click on **Services Desktop App**.  Scroll down to OpenSSH Server and
right-click to select Properties. Change the startup type to *Automatic* then OK. Now right-click
again and select *Start*. The service is now running and set to start automatically after each reboot.

>Finally, if you have a supported nVidia card download the nVidia CUDA drivers and install if you plan on using CUDA encoding.
It's a large download. Choose Custom install and deselect all the documentation and other things you don't need if you want to
minimize space usage.

When pytranscoder starts it will verify that it can ssh to each host using the provided configuration before continuing.


#### Configuration

There is a new section in the transcode.yml file, under the global *config* section, called *clusters*. A cluster is a
group of one or more host machines you will use for encoding.  You may define multiple clusters if you have a large
network of machines at your disposal. **Note**: all hosts in the cluster do not need to be available at runtime - they
will simply be ignored and other hosts in the cluster used.


Sample
```yaml
config:
  default_queue_file:   '/path/to/default/list/of/files/if/none/given'
  ffmpeg:               '/usr/bin/ffmpeg'       # path to ffmpeg for this config
  queues:
    qsv:                1                   # sequential encodes
    cuda:               2                   # maximum of 2 encodes at a time
  plex_server:          192.168.2.61:32400  # optional, use 'address:port'

  # 
  # cluster definitions
  #
  clusters:
    household:                  # name for this cluster
      macpro:                   # name of this host (does not need to be the same as network hostname)
        type: mounted           # machine with source media and host share a filesystem (nfs, samba, etc)
        ip: 192.168.2.65
        user: sshuser           # user account used to ssh to this host
        ffmpeg: '/usr/bin/ffmpeg'
        path-substitution:      # optional, map source pathnames to equivalent on host
          src: /volume1/media/
          dest: /media/
        profile: hevc           # profile for all encoding on this host, required
        status: enabled         # set to disabled to temporarily stop using
      win10:
        type: streaming         # host not using shared filesystem
        ip: 192.168.2.64        # address of host
        user: matt              # ssh login user
        working_dir: 'c:/temp'  # working folder on remote host, required for streaming type
        ffmpeg: '/usr/bin/ffmpeg'
        profile: hevc_cuda      # profile for all encoding on this host, required
        status: enabled         # set to disabled to temporarily stop using

```

| setting      | purpose |
| -----------   | ----------- |
| type          | Host type, either *mounted* or *streaming*. A mounted type indicates the input media files are accessible via a shared filesystem mounted on the host. A streaming type indicates no sharing, and each media file being encoded is copied to that host, encoded, then copied back. |
| ip            | Address or host name of the host  |
| user          | User to log into this host as via ssh. The user must be pre-authenticated to the host so that a password is not required. See https://www.ssh.com/ssh/copy-id. |
| ffmpeg        | Path on the host to ffmpeg |
| working_dir   | Required for streaming type hosts. Indicates the temporary directory to use for encoding. |
| profile       | The profile to use for all encodes on this host. Required |
| path-substitution | Optional. Applicable only to mounted type hosts. Uses when the server media files and host mount paths are different. Any part of the media pathname matching *src* will be replaced with *dest*. |
| status        | enabled or disabled. Disabled hosts will be skipped. Default is enabled.|

==== Sample Walkthrough

You have a media server called **mediaserver**. It has an NFS-exported path to the root of your media storage. This folder is 
on a RAID mounted at /volume1/media. You want to enable all the machines in your household to be used for encoding. You want to
transcode all media to HEVC because it's just better, but it's very time-consuming so you decide to use other machine that
are under-utilized for such tasks. Because your uptight over security you create a special user account on all hosts just for
encoding and setup password-less ssh login to each host using *ssh-copy-id*.
You plan to kick off clustered encoding from **mediaserver**, using 2 other machines to do the work.

You have another machine, your main workstation, which is called **workstation**. This machine mounts the **mediaserver** export as /mnt/media
for easy sharing. It has no CUDA-enabled graphics card but does have an 8th generation Intel i5 supporting QSV.

Your last machine is a shared machine your kids sometimes use, called **shared**. It has a great nVidia graphics card, but does not mount
the media filesystem exported from **mediaserver**.

Here is the configuration for the scenario above:

```yaml
  clusters:
    household:                  # name for this cluster
      workstation:
        type: mounted
        ip: 192.168.2.63
        user: encodeuser
        ffmpeg: '/usr/bin/ffmpeg'
        path-substitution:      # optional, map source pathnames to equivalent on host
          src: /volume1/media/
          dest: /mnt/media/
        profile: qsv
      shared:
        type: streaming
        ip: 192.168.2.64
        user: encodeuser
        working_dir: '/tmp'
        ffmpeg: '/usr/bin/ffmpeg'
        profile: hevc_cuda

```

Not really much of a cluster, but just for illustration purposes.
Now, assuming you have a bunch of media files on **mediaserver** you want to transcode:

```bash
    ls /volume1/media
    
    file1.mp4  file2.mp4  file3.mp4
```

```
    pytrancoder -c household /volume1/media/*
```

This will pick up each file in /volume1/media and queue them for encoding.  Two threads are started - one for *workstation* and
the other for **shared**.  Each thread examines the queue, pulling the next video to be transcoded until all files are
processed.

For **workstation**, a file is pulled from the queue, /volume1/media/file1.mp4 for instance. Since there is a *path-substitution*
configured, change the path to /mnt/media/file1.mp4.  Finally, ssh to **workstation** as encodeuser and run ffmpeg to encode /mnt/media/file1.mp4 using qsv.
The temporary encoded file will be placed in the same folder as the source. Since the filesystem is NFS-mounted, it will already
be available on *mediaserver* when the process completes.

For **shared**, a file is pulled from the queue, /volume1/media/file2.mp4 for instance, and copied to /tmp on that host. 
Then ssh to **shared** as encodeuser and run ffmpeg to encode /tmp/file2.mp4 using hevc_cuda. When finished, copy the encoded
file from **shared** back to **mediaserver** and remove temporary files from **shared** /tmp.

The last file, /volume1/media/file3.mp4, will be handled by the first host to finish the previous encodes. Once all have
been encoded the process will exit.

No encoding was performed on **mediaserver** - it was only used as the manager for the hosts in the cluster.

Also keep in mind that you can use any machine you have ssh access to. It doesn't need to be on your network. You can get your
friends with massive gaming rigs to participate in your cluster. Any defined host that isn't up and available when pytranscoder
is run will be ignored and transcoding will continue on other available hosts.

#### Testing your Setup

You should always do a dry-run test before committing to a configuration change. This will show you
how your media will be handled but won't actually do any work or change anything. It will help you
see that your defined rules are matching as expected and that hosts can be connected to via ssh.

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

