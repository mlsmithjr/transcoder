=====================
Running (Clustered)
=====================

If you're here you are brave.  It means you've configured multiple hosts and tested them for *ssh* access from your *cluster manager* machine.

If you haven't already guessed, pytranscoder runs encodes on other hosts using *ssh* to "log-in" to that machine and run *ffmpeg*. This is
fairly straightforward on Linux and MacOS but a bit of a pain under Windows, as you know if you've read the Windows Clustering setup.
Still, it does work well and I use it regularly across multiple Linux and Windows 10 hosts.

So really you can use any machine reachable with *ssh*, even outside your own network. Securing that connection with VPN or *ssh* certificates is 
a good idea though. Maybe setup a transcoding "co-op" with friends who have beefy rigs and fast internet using the *streaming* host type.

In my home network I have 2 Ubuntu boxes each with decent nVidia cards and a Windows 10 box also with a good nVidia card. 
I push 2 jobs each - that's 6 videos encoding at once using GPUs.  It's beautiful watching the scrolling 
progress indicators showing so much work being done on those 3 machines. I've seen a whole season of 12 50-minute HD videos transcoded in 14 minutes.

The best part is you just set and forget.  When you fire up a job it will use whatever machines in the defined cluster are awake and responsive.
Of course, you don't always want to dominate every machine in your household. You may set some to just do single encodes at a time (non-concurrent) 
as to not impact whoever else is using the machine. How you configure your cluster is in your hands.


#########
Examples
#########

Encode everything in your default queue file on cluster "home":
    `pytranscoder -c home`

    If you configured a *default_queue_file* in your Global config section, it will be opened and read for a list of files to process.
    Each file that is successfully encoded will be removed from that file.  Files are distributed across the cluster hosts based on profiles
    and queues.

Encode some files on a specific host in the cluster:
    `pytranscoder -c home --host workstation /downloads/*.mp4`

    All other cluster hosts will be ignored and encodes sent only to host *workstation*.

Encode files across 2 clusters:
    `pytranscoder -c home /downloads/series.s01*mp4 -c work /downloads/series.s02*mp4`

You can also use --dry-run with a cluster:
    `pytranscoder -c home --dry-run /media/*.mp4`

    This will show all work to be done and perform a reachability test on each host

.. note::
    There is a small gotcha in cluster mode. If you **Ctrl-C** to kill pytranscoder the *ffmpeg* jobs running on the other hosts will
    continue to run. A solution is being pursued.

