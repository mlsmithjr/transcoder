==========================
Custom Rule & Profile Hook
==========================

The Rule and Profile declarative capabilities are a tradeoff between common, simple tasks and a simple
means of expressing them.  That said, there are situations where the flexibility of the Rule matcher isn't
enough for complicated determinations.  You now have the ability to create a custom Python
"hook" to perform much more complex analyses of your media when determining the correct profile
settings.

Your custom hook is installed with `pytranscoder --hook-install <path>` and removed with `pytranscoder --hook-remove`

The `path` points to a valid Python file (ie. myrules.py). This file will be installed into the pytranscoder
package and becomes active immediately.  If you encounter problems or simply want to stop using the hook
just run with `--hook-remove`.

-------
Example
-------

See rule_hook_ex.py for an example hook.

------------
Minimal Hook
------------

.. code-block:: python

    from pytranscoder.media import MediaInfo
    from pytranscoder.profile import Profile, ProfileSKIP

    # minimal hook
    def rule_hook(mediainfo: MediaInfo) -> Optional[Profile]:
        return None

----------------
MediaInfo object
----------------

See the source code for MediaInfo if you are interested in a deep dive.  But the key properties
you'll use in the hook are:

========    =====
Property    Value
========    =====
path        Full path to the media file
vcodec      Video codec
stream      stream id
res_height  video resolution height
res_width   video resolution width
runtime     video runtime (seconds)
filesize_mb video file size in megabytes
fps         frames per second
colorspace  video colorspace specification
audio       list of audio tracks (list of dictionaries). Keys=stream, lang, format, default
subtitle    list of subtitle tracks (list of dictionaries). Keys=stream, lang
========    =====

