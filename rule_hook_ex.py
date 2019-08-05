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
    # skip video if resolution < 700:  # don't re-encode something this small - no gain in it
    #
    if mediainfo.res_height < 700:
        raise ProfileSKIP()

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
