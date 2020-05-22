==========================
Custom Rule & Profile Hook
==========================
CURRENTLY NOT IMPLEMENTED - DISREGARD

The Rule and Profile declarative capabilities are a tradeoff between common, simple tasks and a simple
means of expressing them (yaml).  That said, there are situations where the flexibility of the Rule matcher isn't
enough for complicated determinations.  You now have the ability to create a custom Python
"hook" to perform much more complex analyses of your media when determining the correct profile
settings. You could even create your own alternative declarative rule-based system if you are that ambitious.

Your custom hook is installed with `pytranscoder --hook-install <path>` and removed with `pytranscoder --hook-remove`

The `path` points to a valid Python file (ie. myrules.py). This file will be installed into the pytranscoder
package and becomes active immediately.  If you encounter problems or simply want to stop using the hook
just run with `--hook-remove`.

-------
Example
-------

See `rule_hook_ex.py` for an example hook.

------------
Minimal Hook
------------

.. code-block:: python

    from pytranscoder.media import MediaInfo
    from pytranscoder.profile import Profile, ProfileSKIP

    # minimal hook
    def rule_hook(mediainfo: MediaInfo) -> Optional[Profile]:
        return None

------------------------
MediaInfo object (input)
------------------------

See the source code for MediaInfo if you are interested in more detail.  But the key properties
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

-----------------------
Profile object (output)
-----------------------

See the source code for Profile if you are interested in more detail. Values in Profile are used to
dynamically construct the ffmpeg command line.

A Profile object is constructed with a name and optional dictionary of initial values.
The input_options and output_options are contained in an Options object, which provides an encapsulated
means to merge same options - necessary for included profiles.

========        =====
Property        Value
========        =====
input_options   Options object (see source). Use `merge` method to add options. Existing options of the same `name` will be replaced with the new `value`.
output_options  Options object (see source).  See above.
extension       extension of the output file.
queue_name      Name of the queue to assign this job to (optional).
threshold       Threshold percentage (whole integer)
threshold_check Percentage (whole integer) to start monitoring threshold.
automap         True or False. You can set to False to control your own `-map` options.
========        =====


-------
Testing
-------

You are free to add a __main__ to your code and any unit tests you like.
You can perform final testing by installing and using the --dry-run option to check your media.
