from typing import Optional

from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile, ProfileSKIP

common = Profile("common", {
    'extension': '.mkv',
    'threshold': 20,         # 20% minimum size reduction %, otherwise source is preserved as-is
    'threshold_check': 60,   # start checking threshold at 60% done, kill job if threshold not met
    'input_options': [
        '-hwaccel cuvid'
    ],
    'output_options': [
        "-f matroska",
        "-c:a copy",
        "-c:s copy",
    ]
})


##
# Example hook that replicates functionality of rules in transcode.yml sample, only using pure Python.
# Here you have the full flexibility of Python for your rule tests and profile creation.
# Profile names here are more for your visual verification than anything functional.
#
# The result of calling rule_hook() should be one of:
#   - raise ProfileSKIP(), which raises an exception telling pytranscoder to skip the file
#   - return a valid Profile of your custom settings
#   - return None, indicating no match was made and to continue by evaluating the transcoder.yml rules.
##
def rule_hook(mediainfo: MediaInfo) -> Optional[Profile]:

    #
    # skip of already hevc
    #
    if mediainfo.vcodec == "hevc":
        raise ProfileSKIP()

    #
    # small enough already
    #
    if mediainfo.filesize_mb < 2500 and 720 < mediainfo.res_height < 1081 and 30 < mediainfo.runtime < 65:
        raise ProfileSKIP()

    #
    # skip video if resolution < 700:  # don't re-encode something this small - no gain in it
    #
    if mediainfo.res_height < 700:
        raise ProfileSKIP()

    #
    # Here is a complex example you can only perform with a custom hook.
    #
    # strip redundant HD audio tracks from 4k to make it smaller
    #
    if mediainfo.vcodec == 'hevc' and mediainfo.res_height >= 2160 and len(mediainfo.audio) > 1:
        profile = Profile("strip-DTS")

        truehd_track = None
        ac3_track = None
        for track in mediainfo.audio:
            if track['lang'] != 'eng':
                continue
            if track['format'] == 'truehd':
                truehd_track = track['stream']
            elif track['format'] == 'ac3':
                ac3_track = track['stream']

        # if both English tracks exist, eliminate truehd and keep ac3 - don't transcode video
        if truehd_track and ac3_track:
            profile.automap = False             # override default
            profile.output_options.merge({
                '-map': ac3_track,
                '-c:v': 'copy',
                '-c:s': 'copy',
                '-c:a': 'copy',
                '-f'  : 'matroksa'
            })
            profile.extension = '.mkv'
            return profile

    #
    # anime
    #
    if '/anime/' in mediainfo.path:
        profile = Profile("anime")
        profile.include(common)                          # include: common
        profile.output_options.merge([
          "-c:v hevc_nvenc",
          "-profile:v main",
          "-preset medium",
          "-crf 20"
        ])
        profile.queue_name = "cuda"                # queue: cuda
        profile.automap = True                     # automap: yes
        return profile

    #
    # high frame rate
    #
    if mediainfo.fps > 30 and mediainfo.filesize_mb > 500:
        profile = Profile("high-frame-rate")
        profile.include(common)                          # include: common
        profile.output_options.merge([
          "-c:v hevc_nvenc",
          "-profile:v main",
          "-preset medium",
          "-crf 20",
          "-r 30"])
        profile.queue_name = "cuda"

    #
    # default to no profile to continue on and evaluate defined rules next (transcoder.yml)
    #
    return None
