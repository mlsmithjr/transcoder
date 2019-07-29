
from pytranscoder.media import MediaInfo
from pytranscoder.profile import Profile


common = {
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
}

def match_rule(mediainfo: MediaInfo):

    profile = Profile()

    #
    # small enough already
    #
    if mediainfo.filesize_mb < 2500 and 720 < res_height < 1081 and 30 < runtime < 65:
        return 'SKIP'

    #
    # anime
    #
    if '/anime/' in mediainfo.path:
        profile.include(common)                          # include: common
        profile["output_options"] = [
          "-c:v hevc_nvenc",
          "-profile:v main",
          "-preset medium",
          "-crf 20"
        ]
        profile["queue"] = "cuda"                       # queue: cuda
        profile["automap"] = "yes"                      # automap: yes
        return profile

    #
    # high frame rate
    #
    if mediainfo.fps > 30 and mediainfo.filesize_mb > 500:
        profile.include(common)                          # include: common
        profile["output_options"].append([
          "-c:v hevc_nvenc",
          "-profile:v main",
          "-preset medium",
          "-crf 20",
          "-r 30"])
      queue: cuda


    #
    # default to this profile
    #
    return 'hevc_cuda'

