=====================
Cluster Configuration
=====================

Watching multiple machines doing your bidding is a beautiful thing.  Watching each of them doing concurrent bidding is even more beautiful.
With a well-thought-out configuration this is easy to do.

------------
Linux Setup
------------

We will refer to the machine you use pytranscode on as your *cluster manager* and other machines as *hosts*.

Setting up remote hosts is as follows, if not already setup for ssh access and ffmpeg:
Linux is natively supported as long as the following conditions are true:
* Each host machine in the cluster is running an *ssh* server.
* Each host has *ffmpeg* installed.
* If using hardware encoding, your machine (and *ffmpeg*) have been setup and tested to make sure it is working. Setup of hardware encoding is
beyond the scope of this document.
* The *cluster manager* machine must be able to *ssh* to each host without a password prompt (see `man ssh-copy-id`).

-----------
MacOS Setup
-----------

MacOS, being based on BSD, is also natively supported.  See Linux section. 
Check your MacOS version of ffmpeg for what hardware acceleration support is available, if any. 
At the time of this writing there was nothing available of appreciable quality, only VAAPI and the quality was dismal.

----------------
Windows 10 Setup
----------------
Setting up Windows 10 as a cluster host is a bear. Enter at your own risk.

There are 2 ways to enable SSH access for Windows. Each method is further complicated depending on which ffmpeg you use.  These instructions assume a certain level of proficiency with Windows and optionally WSL.

###########################
Microsoft OpenSSH
###########################
This method will only allow streaming cluster support due to Windows OpenSSH not being able to access network shares or drives consistently. Avoid if you can.

* Install OpenSSH server
* Set server to auto-start (delayed)
* Start server
* Copy RSA key from *cluster manager* 

Install openssh server via `Settings > Apps > manage optional features > Add a Feature > OpenSSH Server > Install`

You cannot use `ssh-copy-id` to authenticate to openssh on Windows. Instead, in the home folder of the user account create
a directory called **.ssh**.  Then from your *cluster manager* copy your $HOME/.ssh/id_rsa.pub to c:/Users/*username*/.ssh/authorized_keys on Windows.

In the search bar type **services* and click on **Services Desktop App**.  Scroll down to OpenSSH Server and
right-click to select Properties. Change the startup type to *Automatic* then OK. Now right-click
again and select *Start*. The service is now running and set to start automatically after each reboot.

Finally, if you have a supported nVidia card download the nVidia CUDA drivers and install if you plan on using CUDA encoding.
It's a large download. Choose Custom install and deselect all the documentation and other things you don't need if you want to
minimize space usage.

###########################
WSL (Ubuntu) OpenSSH:
###########################
This is the better method but requires more fiddling around at the shell. By installing Windows Subsystem for Linux you enable
a more standard bash experience and can use **mount** on network share drive mappings and enable *mounted* mode (faster).  
I will cover the highlights but the details are yours to research. 
Some helpful details `here <https://www.reddit.com/r/bashonubuntuonwindows/comments/5gh4c8/ssh_to_bash_on_wsl/>`_.

* From the Windows Store search for and install Ubuntu.
* On the search bar search for "Enable Features" and click on *Turn Windows features on and off*. Scroll down to Windows Subsystem for Linux and enable.
* Launch Ubuntu and create your new user as prompted.
* From *bash* you must uninstall and reinstall openssh-server (to fix a problem with the Microsoft-provided distribution):
    * `sudo apt remove --purge openssh-server`
    * `sudo rm -rf /etc/ssh`
    * `sudo apt install openssh-server`
* Try to *ssh* to your Windows machine now.
* From your *cluster manager* host, use `ssh-copy-id` to setup password-less *ssh* to your Windows host.
* Back on Windows, map a drive letter to your network media share (ex. *Z:*).
* This is where it gets more confusing:
    * (easiest) If installing the Windows `ffmpeg package <https://www.ffmpeg.org/>`_
       * Download and install now.
       * NOTE that your path mappings for pytranscoder will use *Z:* since the *ffmpeg* you are running is still a Windows program and expects commandline parameters to be Windows-like.
    * If installing the Ubuntu ffmpeg package
       * In *bash*: `sudo apt install ffmpeg`
       * Create a folder under /mnt representing your media folder mount point.
       * Now test mount your mapped drive (ie. `sudo mount -t drvfs 'z:' /mnt/media`)
       * If /mnt/media is mounted to your shared media server you are good to proceed.
       * Finally, make the mount permanent by adding it to /etc/fstab:
           `z: /mnt/media drvfs defaults 0 0`
       * NOTE that your path mappings for pytranscoder will use */mnt/media/*, not *Z:* as with the Windows-specific *ffmpeg*.



------------------
Cluster Definition
------------------

First, a word about queues.  The *queues:* definition in the Global section only applies when running pytranscoder on 
a single host.  These queues are not used when running in cluster mode. This is because you can define queues for each host doing work.
So whatever queues you have defined there, just ignore for the purposes of cluster setup.

Setting up your clusters is as it sounds - you must define some information about each host participating in the cluster, even
including the one your are running pytranscoder from, if applicable.


*Sample, 4-host configuration*:

.. code-block:: yaml

    config:
        ...
        ssh:                '/usr/bin/ssh'    # used only in cluster mode
        ...
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
        
            ##################################
            # My old MacPro booted into Ubuntu 
            ##################################
            macpro:                     # name of this host (does not need to be the same as network hostname)
                type:  mounted          # machine with source media and host share a filesystem (nfs, samba, etc)
                os:    macos            # choices are linux, macos, win10
                ip:    192.168.2.65
                user:  sshuser          # user account used to ssh to this host
                ffmpeg: '/usr/bin/ffmpeg'
                path-substitutions:     # optional, map source pathnames to equivalent on host
                    - "/volume1/media/ /mnt/media/"
                    - "/downloads/ /mnt/downloads/"
                profiles:               # profiles allowed on this host
                    - hevc
                    - h264
                status: 'enabled'       # set to disabled to temporarily stop using

            #################################
            # gaming machine (Windows OpenSSH)
            #################################
            gamer: 
                type:   streaming       # host not using shared filesystem
                os:     win10           # choices are linux, macos, win10
                ip:     192.168.2.64    # address of host
                user:   matt            # ssh login user
                working_dir: 'c:\temp'  # working folder on remote host, required for streaming type
                ffmpeg: 'c:/ffmpeg/bin/ffmpeg'
                profiles:               # profiles allowed on this host
                    - hevc_cuda
                    - hevc_qsv
                queues:
                    qsv: 1
                    cuda: 2
                status: 'enabled'         # set to disabled to temporarily stop using

            ####################################################
            # Spare family machine - Windows Subsystem for Linux
            ####################################################
            family:                     # machine configured to use WSL ssh server
                type:  mounted
                os:    win10
                ip:    192.168.2.66
                user:  chris
                ffmpeg: /mnt/c/ffmpeg/bin/ffmpeg.exe  # using Windows ffmpeg.exe build
                path-substitutions:         # how to map media paths on source to destination mount point
                    - "/volume1/media Z:"   # Z: mapped to network share (media)
                    - "/downloads/    Y:"   # Y: mapped to network share (downloads)
                profiles:               # profiles allowed on this host
                    - hevc_cuda
                    - hevc_cuda_10bit
                queues:
                    qsv: 1
                    cuda: 2
                status: enabled

This sample is based on a setup where a Linux machine is used as a media server, and all media is stored on that machine. The 
relevant root paths on that machine are */downloads* and */volume1/media*.  These folders are also shared via Samba (SMB) and NFS 
and accessible to all other machines on the network.

The first machine, **mediacenter**, is of type *local* which means it's the same machine we're running pytranscoder on. This is just
a simplified way of adding the machine without requiring ssh into itself. Notice that each machine has an *ffmpeg* path. These are required and 
will be the *ffmpeg* being run on that host. Status is either *enabled* or *disabled*. If disabled it will not participate in the cluster.

.. note::
    pytranscoder will check that each machine in the cluster is up and accessible when you start a job. If a host is down it will
    be ignored and processing will continue with the others.

Skipping down to **macpro**, the type is *mounted*. The *local* and *mounted* types are most preferred as they are faster. What this means 
is the host has mounted shared folders from the server and can access media directly. In the Windows world this is a mapped drive, in Linux
and MacOS it's an NFS mount.  In the case of Linux or MacOS, if your mountpoints are not named the same as on the server you must use 
the *path-substitutions* configuration.

For example, there is a video file on the server in */downloads/mymedia.mp4*.  The */downloads* folder is exported via NFS and mounted on 
**macpro** machine under */mnt/downloads*.  Once the *ffmpeg* job starts on **macpro** it will be passed */downloads/mymedia.mp4* as the input
filename.  Well, that path does not exist on **macpro**, but *mymedia.mp4* IS accessible as */mnt/downloads/mymedia.mp4*. So we setup 
the *path-substitutions* patterns to account for this. Now, before *ffmpeg* is run on **macpro** the input pathname will be changed from 
*/downloads/*... to */mnt/downloads/*...

Likewise, a file under */volume1/media/tv/series/season1/show.s01e01.mp4* is accessible on **macpro** as 
*/mnt/media/tv/series/season1/show.s01e01.mp4*.

Whew, hope that was clear enough.

Continuing on down the **macpro** configuration, and others, you'll see *profiles:*. This indicates a list of profiles suitable for this 
host. Note in this example that *h264* and *hevc* are given. These are basic profiles that perform CPU-based encoding without assistance 
since this host is incapable of any hardware encoding.  If I put *hevc_cuda* as a supported profile the job would fail since this host 
has no nVidia GPU. So this host will only be called on to encode video matching those profiles.

Skipping down to the **gamer** host we see a type of *streaming*. The streaming type is not encouraged but there in case you cannot or will not
map a server drive to the host. Maybe this is a security concern, or laziness.  Who knows.  But it's there if the situation arises.
Notice there are no *path-substitutions*.  This is because for *streaming* they are not used.
Hosts of the *streaming* type will be sent the media file via scp (secured copy) to the *working_dir* folder, *ffmpeg* will encode the file into the same
the same folder, and the result will be copied back to the server. Finally, the 2 artifacts in *working_dir* are removed.

Notice the differences between the **gamer** and **family** machines.  They are both Windows 10 but are configured very differently. This 
is discussed in detail in Windows Installation. But the driving difference is that **gamer** only has Microsoft's own OpenSSH server 
installed, along with Windows *ffmpeg*, but the **family** host uses WSL. Both type get the job done, but with caveats. For Windows OpenSSH,
the remote shell can access the c: drive normally (see **gamer** ffmpeg path). For WSL, the path is convoluted (see **family** ffmpeg path).

Of note on the **family** host are the *path-substitutions*. These map a remote media path to a mapped local drive letter. Unfortunately at the
time of this writing it is the only reasonable way since WSL cannot access network shares. As soon as this changes you should be able to use 
a network share path instead of drive letters. Finally, notice that the *profiles* for this host are CUDA-only. This means I only want the 
host doing hardware transcodes. Furthermore, this host has a better nVidia GPU and can handle 10-bit encodes to only send those jobs there.

