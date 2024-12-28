#!/usr/bin/env python
"""Create A Dynamic Exercise Routine"""

import argparse
import copy
import datetime
import glob
import itertools
import os
import random
import requests
import subprocess
import time
import tabulate
import yaml

import google_auth_oauthlib.flow
import google.auth.transport.requests
import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.errors

from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

from ahk import AHK

import dateutil.parser
import obswebsocket
import pytz

'''def create_thumbnail(args):
    """Create thumbnail for YouTube"""

    size = {"x": 1920, "y": 1080}
    random_color = f"#{random.randint(0, 0xFFFFFF):06x}"
    random_position = f"+{random.randint(0, size['x'])-500}+{random.randint(0, size['y']-500)}"
    #random_position = "+0+0"

    minutes = str(datetime.timedelta(seconds=args.length*60)).split(":")[1]
    title = f"{minutes} MINUTE\n{args.style.upper()} WORKOUT"

    cmd = [
            "magick",
            "convert",
            "-size", "1920x1080",
            f"xc:{random_color}",
            "-gravity", "northwest",
            "-font", "TitlingGothicFBComp-Medium",
            "-pointsize", "128",
            "-annotate", f"{random_position}",
            f"{title}",
            "thumbnail.png"
          ]
    subprocess.run(cmd, check=True)
'''


def generate_routine(args):
    """Generate Routine"""
    with open(args.styles_yaml, "r", encoding="utf-8") as stream:
        style = yaml.safe_load(stream)

    with open(args.exercises_yaml, "r", encoding="utf-8") as stream:
        exercise = yaml.safe_load(stream)

    length = args.length * 60
    elapsed = 0

    routine = []
    routine_text = {}
    routine_text["blocks"] = []
    routine_text["exercises"] = {}

    warmup = exercise["warmup"]
    warmup["name"] = "warmup"
    warmup["length"] = style[args.style]["percent_of_time"]["warmup"] * length
    warmup["reel_or_short"] = False

    cool_down = exercise["cool down"]
    cool_down["name"] = "cool down"
    cool_down["length"] = style[args.style]["percent_of_time"]["cool down"] * length
    cool_down["reel_or_short"] = False

    routine.append(warmup)

    rest_length = style[args.style]["rest_time_after_block"] * \
                  (
                    (style[args.style]["conditioning_blocks"] * \
                    style[args.style]["repeat_conditioning_blocks"]) \
                   - 1
                  )
    rest_length += style[args.style]["rest_time_after_exercise"] * \
                   (
                    (len(style[args.style]["exercises_per_block"]) * \
                        style[args.style]["conditioning_blocks"] * \
                        style[args.style]["repeat_conditioning_blocks"]) \
                    - 1
                   )

    elapsed += warmup["length"] + cool_down["length"]

    conditioning_block = generate_conditioning_block(args, style[args.style], exercise, elapsed)

    if style[args.style]["repeat_conditioning_blocks"] > 0:
        total_exercises_in_conditioning_block = len(style[args.style]["exercises_per_block"]) * \
                                                style[args.style]["conditioning_blocks"] * \
                                                style[args.style]["repeat_conditioning_blocks"]
        exercise_count = 0
        block_count = 0
        block_name = (
                       f"Block {block_count+1} x {style[args.style]['repeat_conditioning_blocks']} "
                       "Times"
                     ).upper()
        #block_name = f"Block {j+1}".upper()
        routine_text["blocks"].append(block_name)
        routine_text["exercises"][block_name] = []

        for current_exercise in conditioning_block:
            routine.append(current_exercise)

            if current_exercise["name"].lower() != style[args.style]["rest_name"]:
                routine_text["exercises"][block_name].append(current_exercise["name"])
                exercise_count += 1
                total_exercises_this_block = (len(style[args.style]["exercises_per_block"])
                                              * style[args.style]["repeat_conditioning_blocks"])

                if (
                        exercise_count % total_exercises_this_block == 0 and
                        exercise_count != total_exercises_in_conditioning_block
                   ):
                    routine_text["exercises"][block_name] = routine_text["exercises"][block_name][:len((style[args.style]["exercises_per_block"]))]
                    block_count += 1
                    block_name = f"Block {block_count+1} x {style[args.style]['repeat_conditioning_blocks']} Times".upper()
                    routine_text["blocks"].append(block_name)
                    routine_text["exercises"][block_name] = []
            #block_name = f"{style[args.style]['conditioning_blocks']} Repeating Blocks {style[args.style]['repeat_conditioning_blocks']} Times".upper()
        routine_text["exercises"][block_name] = routine_text["exercises"][block_name][:len((style[args.style]["exercises_per_block"]))]


    else:
        for i, block in enumerate(conditioning_block):
            routine.append(block)
            block_name = f"Block {i+1}".upper()
            routine_text["blocks"].append(block_name)
        routine_text["exercises"][block_name] = {_["name"].upper() for _ in conditioning_block if _["name"].lower() != style[args.style]["rest_name"]}

    with open(args.routine_title, "w", encoding="utf-8") as f:
        t = ":".join(str(datetime.timedelta(seconds=args.length*60)).split(":")[1:])
        f.write(f"{args.style.upper()} for {t}".upper())

    with open(args.routine_exercises, "w") as f:
        f.write(tabulate.tabulate(routine_text["exercises"], routine_text["blocks"], "plain"))

    routine.append(cool_down)

    return routine

def generate_conditioning_block(args, style, exercise, elapsed):
    """Generate Conditioning Block"""

    conditioning_blocks = []
    already_used_exercises = []

    if style["repeat_conditioning_blocks"] > 0:
        total_exercises_in_conditioning_block = style["conditioning_blocks"] * style["repeat_conditioning_blocks"] * len(style["exercises_per_block"])
    else:
        total_exercises_in_conditioning_block = style["conditioning_blocks"] * len(style["exercises_per_block"])

    if style["rest_time_after_exercise"] > 0:
        total_exercises_in_conditioning_block += len(style["exercises_per_block"]) * style["conditioning_blocks"] * style["repeat_conditioning_blocks"]

    while len(conditioning_blocks) < total_exercises_in_conditioning_block:

        conditioning_block = []

        for targeted_group in style["exercises_per_block"]:
            if targeted_group == 'any':
                matching_exercises = [_ for _ in exercise if _ not in already_used_exercises and "stretch" not in exercise[_]["targeted groups"] and _ not in ["warmup", "cool down"]]
            else:
                matching_exercises = [_ for _ in exercise if targeted_group in exercise[_]["targeted groups"] and _ not in already_used_exercises and _ not in ["warmup", "cool down"]]

            for matching_exercise in matching_exercises[:]:
                for word in matching_exercise.split():
                    if word.isalpha():
                        for already_used_exercise in already_used_exercises:
                            if word.lower() in [_.lower() for _ in already_used_exercise.split()]:
                                print(f"skipping {matching_exercise} because {word} matches.")
                                if len(matching_exercises) > 2:
                                    try:
                                        matching_exercises.remove(matching_exercise)
                                    except ValueError:
                                        pass

            for matching_exercise in matching_exercises[:]:
                if len(exercise[matching_exercise]["targeted groups"]) > style["targeted groups limit"]:
                    matching_exercises.remove(matching_exercise)

            name = random.choice(matching_exercises)

            chosen_exercise = copy.deepcopy(exercise[name])
            chosen_exercise["name"] = name
            if "length" in exercise[name]:
                chosen_exercise["length"] = exercise[name]["length"]
            chosen_exercise["reel_or_short"] = False
            already_used_exercises.append(name)

            '''if "random reps" in chosen_exercise:
                for random_rep in chosen_exercise["random reps"]:
                    rep_count = 0.1
                    while rep_count % chosen_exercise["random reps"][random_rep]["multiple"] != 0:
                        rep_count = random.randint(chosen_exercise["random reps"][random_rep]["min"],
                                                   chosen_exercise["random reps"][random_rep]["max"])
                    chosen_exercise["name"] = chosen_exercise["name"].replace(f"<{random_rep}>", f"{rep_count}")'''

            conditioning_block.append(chosen_exercise)

            if style["rest_time_after_exercise"] > 0:
                rest = copy.deepcopy(exercise["rest"])
                rest["name"] = style["rest_name"]
                rest["length"] = style["rest_time_after_exercise"]
                rest["reel_or_short"] = False
                conditioning_block.append(rest)


        if style["rest_time_after_block"] > 0:
            rest = copy.deepcopy(exercise["rest"])
            rest["name"] = style["rest_name"]
            rest["length"] = style["rest_time_after_block"]
            rest["reel_or_short"] = False
            conditioning_block.append(rest)

        if style["repeat_conditioning_blocks"] > 0:
            conditioning_blocks += conditioning_block * style["repeat_conditioning_blocks"]

        else:
            conditioning_blocks += conditioning_block
    if conditioning_blocks[-1]['name'] == style["rest_name"]:
        conditioning_blocks.pop()

    length = args.length * 60
    predefined_exercise_lengths = [_["length"] for _ in conditioning_blocks if "length" in _ if _["name"] != style["rest_name"]]
    elapsed += sum(predefined_exercise_lengths)

    rest_length = style["rest_time_after_block"] * ((style["conditioning_blocks"] * style["repeat_conditioning_blocks"]) - 1)
    if style["repeat_conditioning_blocks"] > 0:
        rest_length += style["rest_time_after_exercise"] * ((len(style["exercises_per_block"]) * style["conditioning_blocks"] * style["repeat_conditioning_blocks"]) - 1)
    else:
        rest_length += style["rest_time_after_exercise"] * ((len(style["exercises_per_block"]) * style["conditioning_blocks"]) - 1)

    elapsed += rest_length

    if "exercise_length" in style:
        exercise_length = style["exercise_length"]
        conditioning_length = exercise_length * ((len(style["exercises_per_block"]) - len(predefined_exercise_lengths)) * (style["conditioning_blocks"] * style["repeat_conditioning_blocks"]))
    else:
        conditioning_length = length - elapsed

        if style["repeat_conditioning_blocks"] > 0:
            exercise_length = conditioning_length / ((len(style["exercises_per_block"]) - len(predefined_exercise_lengths)) * (style["conditioning_blocks"] * style["repeat_conditioning_blocks"]))
        else:
            exercise_length = conditioning_length / ((len(style["exercises_per_block"]) - len(predefined_exercise_lengths)) * style["conditioning_blocks"])

    for e in conditioning_blocks:
        if "length" not in e:
            e["length"] = exercise_length

    if style["subject_positioning"].lower() == "far":
        reel_or_short = random.randrange(0,len(conditioning_blocks))

        while conditioning_blocks[reel_or_short]["name"] == style["rest_name"]:
            reel_or_short = random.randrange(0,len(conditioning_blocks))

        conditioning_blocks[reel_or_short]["reel_or_short"] = True
        print(conditioning_blocks[reel_or_short])

    return conditioning_blocks

def do_routine(args, routine):
    """Do The Routine"""

    start_time = {}
    start_time["routine"] = datetime.datetime.now()
    start_time["exercise"] = start_time["routine"]

    end_time = {}
    end_time["routine"] = start_time["routine"] + datetime.timedelta(seconds=args.length*60)
    end_time["exercise"] = start_time["exercise"]

    time_left = {"routine": 0, "exercise": 0}
    previous_time_left = {"routine": 0, "exercise": 0}

    percent = {"routine": 0, "exercise": 0}
    previous_percent = {"routine": 0, "exercise": 0}

    routine = itertools.cycle(routine)
    first_exercise = next(routine)
    next_exercise = first_exercise
    sleep_time = 0.1

    reel_or_short_recorded = False


    running = True
    while running:

        exercise, next_exercise = next_exercise, next(routine)

        print(exercise)

        if next_exercise == first_exercise:
            running = False
            next_exercise["name"] = "all finished!"

        start_time["exercise"] = end_time["exercise"]
        end_time["exercise"] = start_time["exercise"] + datetime.timedelta(seconds=exercise["length"])

        now = datetime.datetime.now()

        tmi_args = { 'inputName': args.exercise_transition,
                     'mediaAction': "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
                   }
        obsws = obswebsocket.obsws(args.obs_websocket_host,
                                   args.obs_websocket_port,
                                   args.obs_websocket_secret)
        obsws.connect()
        obsws.call(obswebsocket.requests.TriggerMediaInputAction(**tmi_args))
        obsws.disconnect()

        if "random reps" in exercise:
            if "original_name" not in exercise:
                    exercise["original_name"] = copy.deepcopy(exercise["name"]) 
            exercise["name"] = exercise["original_name"]
            for random_rep in exercise["random reps"]:
                rep_count = 0.1
                while rep_count % exercise["random reps"][random_rep]["multiple"] != 0:
                    rep_count = random.randint(exercise["random reps"][random_rep]["min"],
                                               exercise["random reps"][random_rep]["max"])
                exercise["name"] = exercise["name"].replace(f"<{random_rep}>", f"{rep_count}")

        update_exercise_name(args, exercise["name"])

        if exercise["reel_or_short"] and not reel_or_short_recorded:
            obsws = obswebsocket.obsws(args.obs_websocket_host,
                                       args.obs_websocket_port,
                                       args.obs_websocket_secret)
            obsws.connect()
            record_status = obsws.call(obswebsocket.requests.GetRecordStatus()).__dict__["datain"]
            if not record_status["outputActive"]:
                obsws.call(obswebsocket.requests.SetCurrentProgramScene(**{"sceneName": "9:16"}))
                time.sleep(1)
                obsws.call(obswebsocket.requests.StartRecord())
                stop_record = True
            else:
                stop_record = False
            obsws.disconnect()

        else:
            with open(args.reel_or_short_transition, "w") as f:
                f.write(f"{exercise['name']} not reel or short")

        if random.randint(0,100) <= args.random_effect_percent:
            show_random_effect(args)

        while now < end_time["exercise"]:
            time_left["routine"] = (end_time["routine"] - now).seconds
            time_left["exercise"] = (end_time["exercise"] - now).seconds
            percent["routine"] = round(time_left["routine"] / (args.length*60), 2)
            percent["exercise"] = round(time_left["exercise"] / exercise["length"], 2)
            elapsed = (now-start_time["routine"]).total_seconds()
            
            if int(elapsed) == 10:
                for source_name in ["Intro - Heart Rate Monitor", "Intro - Heart Rate Monitor - Black Box"]:
                    source = {"sceneName": "Heart Beat Group", "sourceName": source_name}
                    obs_scene_item(args, source, True)

            if int(elapsed) == 20:
                for source_name in ["Intro - Heart Rate Monitor", "Intro - Heart Rate Monitor - Black Box"]:
                    source = {"sceneName": "Heart Beat Group", "sourceName": source_name}
                    obs_scene_item(args, source, False)

            if int(elapsed) == 20:
                for source_name in ["Intro - Battery", "Intro - Battery - Black Box"]:
                    source = {"sceneName": "Battery Group", "sourceName": source_name}
                    obs_scene_item(args, source, True)

            if int(elapsed) == 30:
                for source_name in ["Intro - Battery", "Intro - Battery - Black Box"]:
                    source = {"sceneName": "Battery Group", "sourceName": source_name}
                    obs_scene_item(args, source, False)

            if int(elapsed) == 30:
                for source_name in ["Inbody Test Summary"]:
                    source = {"sceneName": "Routine", "sourceName": source_name}
                    obs_scene_item(args, source, True)

            if int(elapsed) == 40:
                for source_name in ["Inbody Test Summary"]:
                    source = {"sceneName": "Routine", "sourceName": source_name}
                    obs_scene_item(args, source, False)

            if time_left["exercise"] == 5:
                tmi_args = { 'inputName': args.play_sound,
                             'mediaAction': "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
                           }
                obsws = obswebsocket.obsws(args.obs_websocket_host,
                                           args.obs_websocket_port,
                                           args.obs_websocket_secret)
                obsws.connect()
                obsws.call(obswebsocket.requests.TriggerMediaInputAction(**tmi_args))
                obsws.disconnect()

            if previous_time_left != time_left:
                if next_exercise["reel_or_short"]:
                    write_dynamic_data(args, time_left["routine"], time_left["exercise"], round(percent["routine"]*100), f"{exercise['name']}", f"Reel / {next_exercise['name']}")
                else:
                    write_dynamic_data(args, time_left["routine"], time_left["exercise"], round(percent["routine"]*100), f"{exercise['name']}", f"{next_exercise['name']}")
                previous_time_left = copy.deepcopy(time_left)

            if previous_percent["routine"] != percent["routine"]:
                create_countdown_image(args, percent["routine"])
                previous_percent = copy.deepcopy(percent)

            time.sleep(sleep_time)
            now = datetime.datetime.now()

        if exercise["reel_or_short"]:
            if stop_record is True:
                obsws = obswebsocket.obsws(args.obs_websocket_host,
                                           args.obs_websocket_port,
                                           args.obs_websocket_secret)
                obsws.connect()
                obsws.call(obswebsocket.requests.StopRecord())
                obsws.call(obswebsocket.requests.SetCurrentProgramScene(**{"sceneName": "Routine"}))
                obsws.disconnect()
                reel_or_short_recorded = True






    write_dynamic_data(args, 0, 0, 0, "all finished!", "all finished!")




def write_dynamic_data(args, countdown_time, interval_time, percent, current_exercise, next_exercise):
    """Write Dynamic Data"""

    with open(args.styles_yaml, "r", encoding="utf-8") as stream:
        style = yaml.safe_load(stream)

    input_settings = {
                      "inputName": "",
                      "inputSettings": {"text": ""}
                     }
    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    try:
        obsws.connect()
    except obswebsocket.exceptions.ConnectionFailure:
        return False

    with open(args.countdown_timer, "w") as f:
        t = ":".join(str(datetime.timedelta(seconds=round(countdown_time))).split(":")[1:])
        f.write(t)

    input_settings["inputName"] = "Countdown Timer"
    input_settings["inputSettings"]["text"] = t
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))

    with open(args.interval_timer, "w") as f:
        t = ":".join(str(datetime.timedelta(seconds=round(interval_time))).split(":")[1:])
        f.write(t)

    input_settings["inputName"] = "Interval Countdown"
    input_settings["inputSettings"]["text"] = t
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))

    with open(args.current_exercise, "w") as f:
        f.write(current_exercise.upper())

    input_settings["inputName"] = "Exercise Name - Now"
    input_settings["inputSettings"]["text"] = current_exercise.upper()
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))

    input_settings["inputName"] = "Interval Stopwatch"

    with open(args.current_exercise_type, "w") as f:
        if current_exercise.lower() == style[args.style]["rest_name"]:
            f.write(style[args.style]["rest_name"].upper())
            input_settings["inputSettings"]["text"] = style[args.style]["rest_name"].upper()
        elif current_exercise.lower() == "warmup":
            f.write("warmup".upper())
            input_settings["inputSettings"]["text"] = "warmup".upper()
        elif current_exercise.lower() == "cool down":
            f.write("cool down".upper())
            input_settings["inputSettings"]["text"] = "cool down".upper()
        else:
            f.write("exercise".upper())
            input_settings["inputSettings"]["text"] = "exercise".upper()

    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))


    with open(args.next_exercise, "w") as f:
        f.write(next_exercise.upper())
    input_settings["inputName"] = "Exercise Name - Next - Monitor"
    input_settings["inputSettings"]["text"] = next_exercise.upper()
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))

    with open(args.routine_countdown_text_file_name, "w") as f:
        f.write(f"{percent}%")

    input_settings["inputName"] = "Routine Countdown Percent"
    input_settings["inputSettings"]["text"] = f"{percent}%"
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))

    obsws.disconnect()

def create_thumbnail(args):
    """Create Video Thumbnail"""

    with open(args.styles_yaml, "r", encoding="utf-8") as stream:
        style = yaml.safe_load(stream)

    #minutes = str(datetime.timedelta(seconds=args.length*60)).split(":")[1]
    today = datetime.datetime.today().strftime('%Y-%m-%d')


    '''if "STRETCH" in args.style.upper().split():
        session_type = "SESSION"
    else:
        session_type = "WORKOUT"
    caption = f"{minutes} MINUTE {args.style.upper()} {session_type.upper()}"'''
    caption = f"{style[args.style]['thumbnail_text']}"

    thumbnail_output = os.path.join(args.thumbnail_output, f"{caption} - {today}.png")

    #Create multiple color biceps randomly around the image

    flexed_biceps = []
    bicep_images = []

    thumbnail_size = (1920, 1080)
    title_size = (1920, 430)

    circle_size = (450, 450)
    head_size = (703, 1100)

    division_coordinates = []
    division_coordinates.append(((0, thumbnail_size[0]/2), (title_size[1], thumbnail_size[1])))
    division_coordinates.append(((thumbnail_size[0]/2, thumbnail_size[0]), (title_size[1], thumbnail_size[1])))

    print(division_coordinates)

    for _ in range(0, random.randint(1,20)):

        geometry = f"+{random.randint(0,1300)}+{random.randint(350, 600)}"
        rgb = random.sample(range(0, 255), 3)
        fill = f"rgb({','.join(map(str, rgb))})"
        bicep_image = f"{os.path.join(args.thumbnail_templates, f'Flexed Biceps {fill}.png')}"
        bicep_images.append(bicep_image)
        cmd = [
                "magick",
                "convert",
                f"{os.path.join(args.thumbnail_templates, 'Flexed Biceps Grayscale.png')}",
                "-fill", fill,
                "-colorize", "100%",
                bicep_image,
              ]
        subprocess.run(cmd, check=True)

        flexed_biceps += [bicep_image,
                          "-gravity", "NorthWest",
                          "-geometry", geometry,
                          "-composite"
                         ]

    rgb = random.sample(range(0, 255), 3)
    cmd = [
            "magick",
            "-size", f"{'x'.join(str(_) for _ in circle_size)}",
            "xc:transparent",
            "-fill", f"rgb({','.join(map(str, rgb))})",
            "-draw", f"translate %[fx:w/2],%[fx:h/2] circle 0,0 0,{circle_size[0]/2}",
            "-gravity", "Center",
            "-fill", "White",
            "-pointsize", "200",
            "-font", "TitlingGothicFBComp-Medium",
            "-annotate", "0",
            f"{int(args.length)}",
            "-gravity", "Center",
            "-fill", "White",
            "-pointsize", "125",
            "-font", "TitlingGothicFBComp-Medium",
            "-annotate", "+0+125",
            "min",
            f"{os.path.join(args.thumbnail_templates, 'Duration Circle.png')}"
          ]
    print(cmd)
    subprocess.run(cmd, check=True)
    rgb = random.sample(range(0, 255), 3)
    cmd = [
            "magick",
            "convert",
            "-background",
            f"rgb({','.join(map(str, rgb))})",
            "-bordercolor",
            f"rgb({','.join(map(str, rgb))})",
            "-font",
            "TitlingGothicFBComp-Medium",
            "-fill",
            "white",
            "-gravity",
            "North",
            "-size",
            "1920x430",
            f"caption:{caption}",
            #"-trim",
            "-border",
            "20",
            "-background",
            "black",
            "-extent",
            "1920x1080",
          ]
    #cmd += flexed_biceps
    circle_coordinates = random.choice(division_coordinates)
    division_coordinates.remove(circle_coordinates)
    circle_coordinates = (
                          random.randint(circle_coordinates[0][0], circle_coordinates[0][1] - circle_size[0]),
                          random.randint(circle_coordinates[1][0] - 100, circle_coordinates[1][1] - circle_size[1])
                         )
    #circle_coordinates = (circle_coordinates[0] - circle_size[0], circle_coordinates[1] - circle_size[1])
    print(circle_coordinates)
    cmd += [
            f"{os.path.join(args.thumbnail_templates, 'Duration Circle.png')}",
            "-gravity",
            "NorthWest",
            "-geometry",
            f"+{circle_coordinates[0]}+{circle_coordinates[1]}",
            "-composite"
           ]

    head_coordinates = random.choice(division_coordinates)
    division_coordinates.remove(head_coordinates)
    print(head_coordinates)
    head_coordinates = (
                          random.randint(head_coordinates[0][0], head_coordinates[0][1] - head_size[0]),
                          random.randint(head_coordinates[1][0] - 100, head_coordinates[1][1] - head_size[1]*.66)
                         )
    #head_coordinates = (head_coordinates[0] - head_size[0], head_coordinates[1] - head_size[1])
    print(head_coordinates)
    cmd += [
            f"{os.path.join(args.thumbnail_templates, 'Prestons Head.png')}",
            "-gravity",
            "NorthWest",
            "-geometry",
            f"+{head_coordinates[0]}+{head_coordinates[1]}",
            "-composite",
            f"{thumbnail_output}"
           ]
    print(' '.join(cmd))
    subprocess.run(cmd, check=True)

    for bicep_image in bicep_images:
        os.remove(bicep_image)

    return thumbnail_output

def create_countdown_image(args, percent):
    """Create YouTube Thumbnail"""

    #magick convert -size 20x390 xc:green -fill green -draw "rectangle 0,0 675,390" charge.png

    new_width = round(args.routine_countdown_image_width * percent)

    green = 255 * percent
    red = 255 * (1 - percent)
    blue = 0

    rgb = (red, green, blue)

    cmd = [
            "magick",
            "convert",
            "-size",
            f"{new_width}x{args.routine_countdown_image_height}",
            f"xc:rgb({','.join(map(str, rgb))})",
            "-fill",
            f"rgb({','.join(map(str, rgb))})",
            "-draw",
            f"rectangle 0,0, {new_width},{args.routine_countdown_image_height}",
            f"{args.routine_countdown_image_file_name}"
          ]

    subprocess.run(cmd)

    return True


def refresh_google_access_token(args):
    """ Create YouTube Live Broadcast"""

    creds = None
    if os.path.exists(args.google_access_token_file):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(args.google_access_token_file, args.google_scopes)

    print(creds.valid, creds.expired, creds.refresh_token)

    #if not creds.refresh_token:
    if not creds or not creds.valid or creds.expired:
        # or not creds.refresh_token

        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(args.google_client_secret_file, args.google_scopes)
        creds = flow.run_local_server(port=0)

        with open(args.google_access_token_file, 'w') as token:
            token.write(creds.to_json())

def get_google_credentials(args):

    return Credentials.from_authorized_user_file(args.google_access_token_file, args.google_scopes)

def create_youtube_scheduled_stream(args, routine, thumbnail_file, google_credentials):
    minutes = str(datetime.timedelta(seconds=args.length*60)).split(":")[1]

    with open(args.styles_yaml, "r", encoding="utf-8") as stream:
        style = yaml.safe_load(stream)

    title = style[args.style]["stream_title"]
    print(title)
    title = title.format(length=minutes)

    print("description: exercises include".title())
    list_of_exercises = ["00:00 Intro"]
    elapsed = args.intro_length
    for exercise in routine:
        chapter_time = ':'.join(str(datetime.timedelta(seconds=elapsed)).split(':')[1:]).split('.')[0]
        list_of_exercises.append(" ".join([chapter_time,exercise["name"]]))
        elapsed += exercise["length"]

    chapter_time = ':'.join(str(datetime.timedelta(seconds=(args.length*60)+args.intro_length)).split(':')[1:]).split('.')[0]
    list_of_exercises.append(" ".join([chapter_time, "outro"]))

    print('\n'.join(list_of_exercises).title())

    with open(args.styles_yaml, "r", encoding="utf-8") as stream:
        style = yaml.safe_load(stream)

    description = "exercises include\n"
    description += "\n".join(list_of_exercises)


    scheduled_start_time = dateutil.parser.parse(args.start_datetime).isoformat()
    scheduled_end_time = (dateutil.parser.parse(args.start_datetime) + datetime.timedelta(seconds=(args.length*60)+args.intro_length+args.outro_length)).isoformat()

    print(f"{title.upper()}")
    print(f"{description.title()}" + "\n" + f"{' '.join(style[args.style]['hashtags'])}")
    print(scheduled_start_time, scheduled_end_time)

    youtube = googleapiclient.discovery.build(args.google_api_service_name, args.google_api_version,credentials=google_credentials)

    description = description.replace("<", "")
    description = description.replace(">", "")

    part = "snippet,contentDetails,status"
    body = {
              "snippet": {
                "title": f"{title.upper()}",
                "scheduledStartTime": f"{scheduled_start_time}",
                "scheduledEndTime": f"{scheduled_end_time}",
                "description": f"{description.title()}" + "\n" + f"{' '.join(style[args.style]['hashtags'])}"
              },
              "contentDetails": {
                "enableClosedCaptions": False,
                "enableDvr": True,
                "enableEmbed": True,
                "recordFromStart": True,
                "startWithSlate": True,
                "enableAutoStart": True,
              },
              "status": {
                "privacyStatus": "public"
              }
            }

    import pprint
    pprint.pprint(body)
    request = youtube.liveBroadcasts().insert(part=part, body=body)
    response = request.execute()

    video_id = response["id"]

    print(response)

    request = youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_file))
    response = request.execute()
    print(response)

    request = youtube.videos().update(
        part = "snippet",
        body={
          "id": video_id,
          "snippet": {
            "title": f"{title.upper()}",
            "description": f"{description.title()}" + "\n" + f"{' '.join(style[args.style]['hashtags'])}",
            "categoryId": "26"
          }
        }
    )
    response = request.execute()

    print(response)

def update_exercise_name(args, exercise_name):
    input_settings = {
                          "inputName": "Exercise Name - Now",
                          "inputSettings": {"text": exercise_name.upper()}
                         }
    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))
    obsws.disconnect()

def obs_scene_item(args, source, enabled):

    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()


    scene_item_id = obsws.call(obswebsocket.requests.GetSceneItemId(**source)).__dict__
    scene_item_id = scene_item_id["datain"]["sceneItemId"]

    scene_item = {}
    scene_item["sceneItemId"] = scene_item_id
    scene_item["sceneName"] = source["sceneName"]
    scene_item["sceneItemEnabled"] = enabled

    obsws.call(obswebsocket.requests.SetSceneItemEnabled(**scene_item))

    obsws.disconnect()


def show_random_effect(args):

    print("playing random effect")
    random_effect_file = random.choice(os.listdir(args.random_effect_dir))
    

    with open(fr"{args.random_effect_yaml}", "r", encoding="utf-8") as infile:
        random_effect_yaml = yaml.safe_load(infile)

    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()

    source = {"sceneName": "Routine", "sourceName": args.random_effect_name}
    scene_item_id = obsws.call(obswebsocket.requests.GetSceneItemId(**source)).__dict__
    scene_item_id = scene_item_id["datain"]["sceneItemId"]

    scene_item = {}
    scene_item["sceneItemId"] = scene_item_id
    scene_item["sceneName"] = source["sceneName"]
    scene_item["sceneItemEnabled"] = False

    obsws.call(obswebsocket.requests.SetSceneItemEnabled(**scene_item))

    if random_effect_file in random_effect_yaml:
        scene_item_transform = scene_item
        scene_item_transform["sceneItemTransform"] = random_effect_yaml[random_effect_file]["sceneItemTransform"]
        obsws.call(obswebsocket.requests.SetSceneItemTransform(**scene_item_transform))

        print(random_effect_yaml[random_effect_file])
        if "Speech Balloon" in random_effect_yaml[random_effect_file]:
            for speech_balloon in random_effect_yaml[random_effect_file]["Speech Balloon"]:
                show_speech_balloon(args, random_effect_yaml[random_effect_file]["Speech Balloon"][speech_balloon])



    input_settings = {}

    input_settings["inputName"] = args.random_effect_name
    input_settings["inputSettings"] = { "local_file": os.path.join(args.random_effect_dir, random_effect_file) }
    obsws.call(obswebsocket.requests.SetInputSettings(**input_settings))
    time.sleep(0.2)
    scene_item["sceneItemEnabled"] = True
    obsws.call(obswebsocket.requests.SetSceneItemEnabled(**scene_item))
    obsws.disconnect()

def show_speech_balloon(args, speech_balloon):
    print(speech_balloon)
    '''x
    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()

    source = {"sceneName": "Routine", "sourceName": args.random_effect_name}
    scene_item_id = obsws.call(obswebsocket.requests.GetSceneItemId(**source)).__dict__
    scene_item_id = scene_item_id["datain"]["sceneItemId"]

    scene_item = {}
    scene_item["sceneItemId"] = scene_item_id
    scene_item["sceneName"] = source["sceneName"]
    scene_item["sceneItemEnabled"] = False

    obsws.call(obswebsocket.requests.SetSceneItemEnabled(**scene_item))'''

def main():
    """main Function"""

    start_datetime = datetime.datetime.now(pytz.timezone('America/New_York')).replace(hour=13,minute=0,second=0,microsecond=0)
    #start_datetime += datetime.timedelta(days=1)

    parser = argparse.ArgumentParser()
    parser.add_argument("style")
    parser.add_argument("length", type=float)
    parser.add_argument("--styles_yaml", default="styles.yaml")
    parser.add_argument("--exercises_yaml", default="exercises.yaml")
    parser.add_argument("--routine_yaml")
    parser.add_argument("--routines_dir", default="Routines")
    parser.add_argument("--intro_length", type=int, default=5)
    parser.add_argument("--outro_length", type=int, default=30)
    parser.add_argument("--story_length", type=int, default=15)
    #parser.add_argument("--start_datetime", default=str(datetime.datetime.now()))
    parser.add_argument("--start_datetime", default=str(start_datetime))
    parser.add_argument("--skip_livestream_creation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--record_now", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--record_countdown", type=int, default=60)
    parser.add_argument("--play_sound", default="Countdown Timer Audio")
    parser.add_argument("--countdown_timer", default="countdown_timer.txt")
    parser.add_argument("--interval_timer", default="interval_timer.txt")
    parser.add_argument("--current_exercise", default="current_exercise.txt")
    parser.add_argument("--current_exercise_type", default="current_exercise_type.txt")
    parser.add_argument("--next_exercise", default="next_exercise.txt")
    parser.add_argument("--routine_exercises", default="routine_exercises.txt")
    parser.add_argument("--routine_title", default="routine_title.txt")
    parser.add_argument("--start_routine", default="start_routine.txt")
    parser.add_argument("--start_outro", default="start_outro.txt")
    parser.add_argument("--start_streaming", default="start_streaming.txt")
    parser.add_argument("--stop_streaming", default="stop_streaming.txt")
    parser.add_argument("--start_recording", default="start_recording.txt")
    parser.add_argument("--stop_recording", default="stop_recording.txt")
    parser.add_argument("--exercise_transition", default="Exercise Transition")
    parser.add_argument("--reel_or_short_transition", default="reel_or_short_transition.txt")
    parser.add_argument("--thumbnail_templates", default="C:\\Users\\Preston Connors\\Pictures\\Exercise\\Thumbnails\\Templates")
    parser.add_argument("--thumbnail_output", default="C:\\Users\\Preston Connors\\Pictures\\Exercise\\Thumbnails")
    parser.add_argument("--routine_countdown_image_file_name", default="C:\\Users\\Preston Connors\\Pictures\\Exercise\\charge.png")
    parser.add_argument("--routine_countdown_text_file_name", default="routine_countdown_percent.txt")
    parser.add_argument("--routine_countdown_image_width", default=675)
    parser.add_argument("--routine_countdown_image_height", default=390)
    parser.add_argument("--random_effect_name", default="Random Effect")
    parser.add_argument("--random_effect_dir", default=(
                                                        "C:\\Users\\Preston Connors\\Videos"
                                                        "\\Exercise\\Random Effects"
                                                       ))
    parser.add_argument("--random_effect_percent", type=int, default=25)
    parser.add_argument("--random_effect_yaml", default="random_effect.yaml")
    parser.add_argument("--google_access_token_file", default="google_access_token.json")
    parser.add_argument("--google_scopes", nargs='?', default=["https://www.googleapis.com/auth/youtube"])
    parser.add_argument("--google_client_secret_file", default="google_client_secret.json")
    parser.add_argument("--google_api_service_name", default="youtube")
    parser.add_argument("--google_api_version", default="v3")
    parser.add_argument("--obs_websocket_host", default="localhost")
    parser.add_argument("--obs_websocket_port", default="4455")
    parser.add_argument("--obs_websocket_secret", default="SAY6rbij3Q7rWxcN")

    args = parser.parse_args()

    routine_accepted = 'N'

    if not args.routine_yaml:

        while not routine_accepted.upper().startswith('Y'):
            routine = generate_routine(args)
            exercise_names = "\n".join([f"{_['name'].title()} {_['length']}" for _ in routine])
            print(f"{exercise_names}")

            routine_accepted = input("Enter Y or N to accept this routine: ")

        routine_yaml = os.path.join(args.routines_dir,
                                    f"{args.style}_{args.length}_mins_{args.start_datetime}.yaml"
                                    .replace(":","_"))
        args.routine_yaml = routine_yaml

        print(f"Writing routine to {args.routine_yaml}")
        with open(fr"{args.routine_yaml}", "w", encoding="utf-8") as outfile:
            yaml.dump(routine, outfile, default_flow_style=False)

    print(f"Reading routine from {args.routine_yaml}")
    with open(fr"{args.routine_yaml}", "r", encoding="utf-8") as infile:
        routine = yaml.safe_load(infile)
        exercise_names = "\n".join([_["name"].title() for _ in routine])
        print(f"{exercise_names}")

    if not args.skip_livestream_creation:
        refresh_google_access_token(args)
        google_credentials = get_google_credentials(args)

        thumbnail_file = create_thumbnail(args)

        create_youtube_scheduled_stream(args, routine, thumbnail_file, google_credentials)

        write_dynamic_data(args, args.length*60, 0, 100, "starting soon!", routine[0]["name"])

    if args.record_now:

        start_routine = 'N'

        while not start_routine.upper().startswith('Y'):
            start_routine = input("Enter Y when you are ready for the countdown to start: ")

        t = args.record_countdown
        while t > 0:
            write_dynamic_data(args, args.length*60, 0, 100, f"recording in {t}", routine[0]["name"])
            update_exercise_name( args, f"recording in {t}")
            t -= 1
            time.sleep(1)

        with open(args.start_recording, "w", encoding="utf=8") as f:
            f.write('start!')

    else:

        while datetime.datetime.now(pytz.timezone('America/New_York')) < dateutil.parser.parse(args.start_datetime):
            #print(f"Waiting until {args.start_datetime} before starting... currently it is {datetime.datetime.now()}")
            t = str(dateutil.parser.parse(args.start_datetime) - datetime.datetime.now(pytz.timezone('America/New_York')))
            t = ':'.join(t.split(":", maxsplit=1)[1:2]).split('.', maxsplit=1)[0]
            write_dynamic_data(args, args.length*60, 0, 100, f"streaming in {t}", routine[0]["name"])
            time.sleep(1)

        with open(args.start_streaming, "w") as f:
            f.write('start!')

    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()
    obsws.call(obswebsocket.requests.SetSceneSceneTransitionOverride(**{"sceneName": "Intro", "transitionName": "Cut"}))
    obsws.call(obswebsocket.requests.SetCurrentProgramScene(**{"sceneName": "Intro"}))
    obsws.call(obswebsocket.requests.StartStream())
    obsws.call(obswebsocket.requests.StartRecord())
    obsws.disconnect()

    elapsed = 0
    while elapsed < args.intro_length:
        t = ':'.join(str(datetime.timedelta(seconds=args.intro_length-elapsed)).split(':')[1:])
        write_dynamic_data(args, args.length*60, 0, 100, f"starting in {t}", routine[0]["name"])
        elapsed += 1
        time.sleep(1)

    with open(args.start_routine, "w") as f:
        f.write('start!')

    obsws.connect()
    obsws.call(obswebsocket.requests.SetCurrentProgramScene(**{"sceneName": "Routine"}))
    obsws.disconnect()

    do_routine(args, routine)

    with open(args.start_outro, "w", encoding="utf-8") as f:
        f.write('start!')

    obsws.connect()
    obsws.call(obswebsocket.requests.SetSceneSceneTransitionOverride(**{"sceneName": "Outro", "transitionName": "Fade", "transitionDuration": 3000}))
    obsws.call(obswebsocket.requests.SetCurrentProgramScene(**{"sceneName": "Outro"}))
    obsws.disconnect()

    time.sleep(args.outro_length)

    with open(args.stop_streaming, "w") as f:
        f.write('stop!')

    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()
    obsws.call(obswebsocket.requests.StopStream())
    obsws.call(obswebsocket.requests.StopRecord())
    obsws.disconnect()

    write_dynamic_data(args, 0, 0, 0, "LIVE EVERY WEEKDAY @ 1PM ET", "LIVE EVERY WEEKDAY @ 1PM ET")

    ahk = AHK()
    win = ahk.win_get(title=[_.title for _ in ahk.list_windows() if 'OBS' in _.title][0])
    win.activate() 
    time.sleep(5)
    ahk.click(2346, 1173)

    '''
    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()
    obsws.call(obswebsocket.requests.SetCurrentProgramScene(**{"sceneName": "9:16"}))
    time.sleep(1)
    obsws.call(obswebsocket.requests.StartRecord())
    time.sleep(args.story_length)
    obsws.call(obswebsocket.requests.StopRecord())
    obsws.disconnect()
    '''


if __name__ == "__main__":
    main()
