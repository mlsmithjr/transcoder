===============
Running (Local)
===============

This contain general information about running the tool locally on one host.  For cluster support see Running (Clustered).

pytranscoder is intended to be run in the foreground as it produces helpful progress output.  You can still run in the background and redirect 
to /dev/null if you choose.

Throughout this document all examples are showing using Linux-style invocations. However, it does work equally well under Windows 10, just obviously
adjusting the way pathnames are expressed.



Now with everything configured here are some tips for using the tool.

########
Examples
########

Get help:
    `pytranscoder -h`

Try to encode everything listed in the default queue file:
    `pytranscoder`

    If you configured a *default_queue_file* in your Global config section, it will be opened and read for a list of files to process.
    Each file that is successfully encoded will be removed from that file.

Test a profile match:
    `pytranscoder --dry-run /downloads/myvideo.mp4`

    The matching profile is display but no encoding is performed.

Encode a file using a given profile:
    `pytranscoder -p h264_small /downloads/myvideo.mp4`

    Rules are not used since a profile was specified with **-p**.

Encode several files using rules:
    `pytranscoder /downloads/*.mp4`

    No profile specified so use rules defined in ~/.transcode.yml to find an appropriate one.

Encode using multiple different profiles, no rules:
    `pytranscoder -p h264_small /downloads/stuff_0*.mp4 -p h264_large /downloads/stuff_1*.mp4`

Encode but keep the original:
    `pytranscoder -k /downloads/myvideo.mp4`

    The encoded file can be found as /downloads/myvideo.mp4.tmp

Show rule-matched profiles for a bunch of files:
    `pytranscoder --dry-run /downloads/*.mp4`

    Each .mp4 file will be matched to a profile and displayed.

Use an alternate (non-default) configuration file:
    `pytranscoder -y /tmp/sandbox.yml /downloads/myvideo.mp4`

Encode all files listed in a text file:
    `pytranscoder --from-file /tmp/stuff_to_encode.txt`

    The file must contain a list of fully-qualified pathnames on separate lines.

Force sequential (non-concurrent) mode, regardless of profile and queues:
    `pytranscoder -s /tmp/*.mp4`

Verbose mode (for debugging and troubleshooting):
    `pytranscoder -v /tmp/*.mp4`

