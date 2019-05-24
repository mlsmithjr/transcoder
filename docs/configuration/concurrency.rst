===========
Concurrency
===========

Concurrency, or multitasking, is simply the act of doing multiple tasks at once. Computers do this very well.
However, some activities do not lend themselves well to concurrency - encoding and decoding video is one of them.
On a typical machine this is a very CPU-intensive activity, especially encoding, and leaves little room or other processes to run well.
So CPU and video card vendors have stepped up to provide dedicated hardware for this purpose. Modern Intel CPUs have hardware collectively
referred to as QSV - QuickSync Video - for doing this. AMD's version is AMF/VCE. Also, modern media players like VLC will use these 
extensions to make HD video playback smooth and less CPU-intensive.

For people who encode a lot, using QSV or AMF can speed up your job up to 4x. But if you want a faster solution both nVidia and AMD produce
graphics cards (GPU) cable of encoding at over 10x - that's basically 6 minutes to encode a 1 hour HD video. Furthermore, you can run multiple
encodes at the same time since most processing is handled by the GPU and not the CPU. For example, an nVidia 970 can handle 2 concurrent
jobs hardware decoding and encoding of H264 or HEVC(H265) video. So this means we can encode 2 of our theoretical 1 hour videos in 6 minutes.

pytranscoder was originally created to manage a pair of jobs running on a local host in this manner, handing out jobs to the next available
slot as other jobs finished.  It has since grown into a configurable workflow manager with multi-host clustering support.

You can successfully achieve concurrency with either (or both) of these approaches:

-----------------
Non-Clustered
-----------------

A cluster is just a group of machines working together. If you have access to multiple machines skip down to the next section.
But if you just want to encode on your single host machine your setup overhead is very small.  You've probably already been through
the configuration section and may have noticed the **queues** section under Global config.

.. code-block:: yaml

    queues:
        qsv:   1
        cuda:  2

This is optional and only needed to enable concurrency on your single (local) host.  This configuration snippet reads "create a queue 
called *csv* that does 1 encode at a time and another called *cuda* which can do 2 at a time." They are simply a way of controlling the 
number of concurrent jobs.
So, by themselves these settings do nothing. To make useful you need to associate various **profiles** with a queue.  A good example is
to assign all of your profiles that perform nVidia-based encoding to the *cuda* queue. When you run an encode and specifiy one of these
profiles, or when a rule selects one, the jobs will be managed 2 at a time.

A profile is assigned to a queue using the **queue:** directive, as seen in the sample profiles in the configuration section.
If a profile has no queue:, it defaults to single, sequential encoding - i.e. one job at a time.

So you've probably noticed the qsv: 1 queue above and are wondering why define a queue of 1 if the default is 1 anyhow. Well there's a
good reason. Even though the qsv queue is set to 1, by defining it as another queue it can actually run concurrently with the other queue.
Wait, what??

Consider this scenario.  You have an 8th generation Intel i5 and an nVidia 970 GPU with 4gb. You have a bunch of videos to transcode and 
you want to max out your system to get it done.  You can define one profile (my_qsv) assigned to the **qsv** queue and another (my_cuda) to the **cuda** queue.
Depending on whether you are using the rules engine or commandline you can spread your videos across both profiles, this assigning them 
across 2 queues.  You'll end up with 2 encodes running on your nVidia GPU and 1 on your CPU/QSV hardware. That's 3 concurrent encodes:

.. code-block:: bash

    pytranscoder -p my_qsv /downloads/show.s01e0* -p my_cuda /downloads/show.s01e1*

Only 2 concurrent jobs are known to work with nVidia 970 and nVidia 1050ti cards, but more may work on bigger more expensive cards.


-----------------
Clustered
-----------------

Clustering allows you to use available machines accessible on your network for encoding duties. You don't need to install anything on them
other than **ffmpeg** and **ssh**, which is probably already there.  See Cluster Configuration.


