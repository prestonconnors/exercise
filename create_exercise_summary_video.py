#!/usr/bin/env python
"""Create Instagram Reel / YouTube Short"""

import argparse
import subprocess
import os

import humanfriendly
import yaml



def create_snippets(args, style, routine):
    """Create snippets of video."""

    already_snipped_exercises = []
    snippets = []
    start_time = args.intro_length + sum(_["length"] for _ in routine)
    video_name  = os.path.splitext(args.source_video)[0]

    if style["subject_positioning"] == "Near":
        video_filter = "transpose=1"
    else:
        video_filter = f"crop='{args.crop}'"

    for i, exercise in reversed(list(enumerate(routine))):
        if exercise["name"] not in args.ignored_exercises \
        and exercise["name"] not in already_snipped_exercises:
            tmp_file = f"{video_name}_{i}.h264"
            cmd = [
                    "ffmpeg",
                    "-ss", str(start_time - exercise["length"]),
                    "-i", args.source_video,
                    "-t", str(exercise["length"]),
                    "-async", "1",
                    "-vf", video_filter,
                    "-map", "0:v:",
                    "-bsf:v", "h264_mp4toannexb",
                    #"-c", "copy",
                    "-y",
                    tmp_file,
                  ]
            subprocess.run(cmd, check=True)
            already_snipped_exercises.append(exercise["name"])
            snippets.append(tmp_file)
        start_time -= exercise["length"]

    with open(args.concat_file, "w", encoding="utf-8") as concat_file:
        for snippet in reversed(snippets):
            concat_file.write(f"file '{snippet}'\n")

def merge_snippets(args):
    """Merge Snippets"""

    video_name = os.path.splitext(args.source_video)[0]

    cmd = [
           "ffmpeg",
            "-safe", "0",
            "-f",  "concat",
            "-i", args.concat_file,
            "-c", "copy",
            "-y",
            f"{video_name}_merged.h264",
          ]
    subprocess.run(cmd, check=True)


def change_duration(args):
    """Change Duration  """

    video_name, video_container = os.path.splitext(args.source_video)

    cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=nb_read_frames",
            "-print_format", "default=nokey=1:noprint_wrappers=1",
            f"{video_name}_merged.h264",
          ]

    frames = subprocess.check_output(cmd)
    frames = float(frames.decode("utf-8").strip())

    target_frame_rate = (frames / (args.length * args.frame_rate)) * args.frame_rate

    cmd = [
           "ffmpeg",
           "-fflags", "+genpts",
           "-r", str(target_frame_rate),
           "-i", f"{video_name}_merged.h264",
           "-c:v", "copy",
           "-y",
           f"{video_name}_merged_and_duration_changed{video_container}"
          ]
    subprocess.run(cmd, check=True)

    cmd = [
           "ffmpeg",
           "-i", f"{video_name}_merged_and_duration_changed{video_container}",
           "-filter:v", "fps=fps=30",
           "-y",
           f"final_reel{video_container}"
          ]
    subprocess.run(cmd, check=True)

def print_post(args, style, routine, description, url):
    """Print Post Text"""

    print("")
    print(description)
    print("")
    print(f"Full Video: {url}")
    print("")

    exercises = []

    duration = {}
    duration["total"] = round(sum(_["length"] for _ in routine))
    duration["warmup"] = [_["length"] for _ in routine if _["name"] == "warmup"][0]
    duration["cooldown"] = [_["length"] for _ in routine if _["name"] == "cool down"][0]

    for exercise in routine:
        if exercise["name"] not in args.ignored_exercises:
            exercises.append(exercise)

    print(f"{os.path.basename(args.routine_yaml).split('_')[0]}")
    if style["repeat_conditioning_blocks"] > 0:
        print(f"Routine: {humanfriendly.format_timespan(duration['total']).title()} / {style['conditioning_blocks']} x Rounds")
    else:
        print(f"Routine: {humanfriendly.format_timespan(duration['total']).title()}")
    if duration["warmup"] > 0:
        print(f"Warmup: {humanfriendly.format_timespan(duration['warmup']).title()}")
    #print(f"Exercise: {humanfriendly.format_timespan(duration['exercise']).title()}")
    #print(f"Rest: {humanfriendly.format_timespan(duration['rest']).title()}")
    if duration["cooldown"] > 0:
        print(f"Cooldown: {humanfriendly.format_timespan(duration['cooldown']).title()}")

    print("")

    if style["repeat_conditioning_blocks"] > 0:
        for block in range(0, style['conditioning_blocks']):
            start_exercise = block*len(style["exercises_per_block"])*style["repeat_conditioning_blocks"]
            end_exercise = start_exercise + len(style["exercises_per_block"])*style["repeat_conditioning_blocks"]
            print(f"\nRound {block + 1} - Repeat {style['repeat_conditioning_blocks']} x Times")
            already_printed = []
            for exercise in exercises[start_exercise:end_exercise]:
                if exercise["name"] not in already_printed:
                    print(f"{exercise['name']} / {humanfriendly.format_timespan(round(exercise['length']))}".title())
                    if style["rest_time_after_exercise"] > 0:
                        print(f"rest / {humanfriendly.format_timespan(style['rest_time_after_exercise'])}".title())
                    already_printed.append(exercise["name"])
            if style["rest_time_after_block"] > 0:
                print(f"rest / {humanfriendly.format_timespan(style['rest_time_after_block'])}".title())
    else:
        for exercise in exercises:
            print(f"{exercise['name']} / {humanfriendly.format_timespan(round(exercise['length']))}".title())

    print(f"{' '.join(style['hashtags'])}")



def main():
    """Main Function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("source_video")
    parser.add_argument("style")
    parser.add_argument("routine_yaml")
    parser.add_argument("length", type=float)
    parser.add_argument("--styles_yaml", default="C:\\Users\\Preston Connors\\Code\\Exercise\\styles.yaml")
    parser.add_argument("--intro_length", type=float, default=5)
    parser.add_argument("--ignored_exercises", default="warmup,cool down,rest")
    parser.add_argument("--crop", default="720:1080")
    parser.add_argument("--frame_rate", default=30)
    parser.add_argument("--concat_file", default="snippets.txt")

    args = parser.parse_args()
    args.ignored_exercises = args.ignored_exercises.split(",")

    print(f"Reading style from {args.styles_yaml}")
    with open(args.styles_yaml, "r", encoding="utf-8") as infile:
        style = yaml.safe_load(infile)[args.style]

    print(f"Reading routine from {args.routine_yaml}")
    with open(fr"{args.routine_yaml}", "r", encoding="utf-8") as infile:
        routine = yaml.safe_load(infile)

    description = input("Reel Description: ")
    url = input("Full Routine URL: ")

    create_snippets(args, style, routine)
    merge_snippets(args)
    change_duration(args)
    print_post(args, style, routine, description, url)

if __name__ == "__main__":
    main()
