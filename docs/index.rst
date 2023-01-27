.. PyTranscoder documentation master file, created by
   sphinx-quickstart on Wed May 22 19:38:42 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PyTranscoder
========================================

========
Features
========
* Sequential or concurrent transcoding.
* Concurrent mode allows you to make maximum use of your nVidia CUDA-enabled graphics card or Intel accelerated video (QSV)
* Preserves all streams but allows for filtering by audio and subtitle languages.
* Configurable transcoding profiles
* Configurable rules and criteria to auto-match a video file to a transcoding profile
* Transcode from a list of files (queue) or all on the command line
* Cluster mode allows use of other machines See `Link Cluster.md <https://github.com/mlsmithjr/transcoder/blob/master/Cluster.md>`_ for details.
* On-the-fly compression monitoring and optional early job termination if not compressing as expected.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   configuration/installation
   configuration/quickstart
   configuration/configuration
   configuration/concurrency
   configuration/cluster
   usage/running-local.rst
   usage/running-clustered.rst
   usage/includes.rst
   usage/mixins.rst

Indices and tables

==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

