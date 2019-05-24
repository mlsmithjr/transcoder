============
Installation
============

############
Requirements
############

* Linux or MacOS, Windows 10. For Windows, WSL (Ubuntu) recommended.
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* nVidia graphics card with latest nVidia CUDA drivers (*optional*)
* Intel CPU with QSV enabled (*optional*)
* Python 3 (3.6 or higher)
* Python PlexAPI package (*optional*).  Install with `pip3 install --user plexapi`


#######
Support
#######
Please log issues or questions via the github home page for now.

Video Tutorials: `Part 1 - Linux Setup <https://www.youtube.com/watch?v=LHhC_w34Kd0&t=5s>`_, `Part 2 - Usage <https://www.youtube.com/watch?v=Os6UACDAOKA>`_

############
Installation
############

There are a few possible ways to install a python app - one of these should work for you.

**Linux**

The confusion is due to the fact that not all distributions or OS's install pip3 by default. Either way, pytranscoder is available in the **pypi** repo.

.. code-block:: bash

  pip3 install --user pytranscoder-ffmpeg
  # or...
  python3 -m pip install --user pytranscoder-ffmpeg 


**Windows (WSL - Ubuntu)**

Windows Subsystem for Linux is the best option, but requires a couple of maintenance steps first if you don't have pip3:

.. code-block:: bash

  sudo apt update
  sudo apt upgrade
  sudo install python3-pip

  # now we can install
  pip3 install --user pytranscoder-ffmpeg


At this point you have a choice - either install *ffmpeg* for Windows `ffmpeg.exe <https://www.ffmpeg.org>`_ or install in *bash* as an Ubuntu package. Either will work but there are caveats, or you could install both and not worry.

* *ffmpeg.exe* can be run in Windows command shell or from *bash* but requires special attention when configuring pytranscoder paths.
* *ffmpeg* apt package can only be run from *bash* but is a more natural Linux path mapping.

After installing you will find documentation in $HOME/.local/shared/doc/pytranscoder (on Linux/MacOS)
and in $HOME/AppData/Python/*pythonversion*/shared/doc/pytranscoder** (on Windows). Also available `online <https://github.com/mlsmithjr/transcoder/blob/master/README.md>`_


#########
Upgrading
#########

Whatever method above for installing works for you, just use the --upgrade option to update, ie:

.. code-block:: bash

  pip3 install --upgrade pytranscoder-ffmpeg

