============
Installation
============

############
Requirements
############

* Linux or MacOS, Windows 10, 11. For Windows, WSL (Ubuntu) recommended.
* latest *ffmpeg* (3.4.3-2 or higher, lower versions may still work)
* nVidia graphics card with latest nVidia CUDA drivers (*optional*)
* Intel CPU with QSV enabled (*optional*)
* Python 3 (3.6 or higher)


#######
Support
#######
Please log issues or questions via the github home page for now.

Video Tutorials: `Part 1 - Linux Setup <https://www.youtube.com/watch?v=LHhC_w34Kd0&t=5s>`_, `Part 2 - Usage <https://www.youtube.com/watch?v=Os6UACDAOKA>`_

############
Installation
############

There are a few possible ways to install a python app - one of these should work for you.

**Linux (Ubuntu & others), Windows, MacOS**

The confusion is due to the fact that not all distributions or OS's install pip3 by default. Either way, pytranscoder is available in the **pypi** repo.

.. code-block:: bash

  pip3 install --user pytranscoder-ffmpeg
  # or...
  python3 -m pip install --user pytranscoder-ffmpeg

After installing you will find documentation in $HOME/.local/shared/doc/pytranscoder (on Linux/MacOS)
and in $HOME/AppData/Python/*pythonversion*/shared/doc/pytranscoder** (on Windows). Also available `online <https://github.com/mlsmithjr/transcoder/blob/master/README.md>`_

#########
Upgrading
#########

Whatever method above for installing works for you, just use the --upgrade option to update, ie:

.. code-block:: bash

  pip3 install --upgrade pytranscoder-ffmpeg

