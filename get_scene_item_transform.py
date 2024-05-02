import argparse
import pprint
import os
import random
import time

import obswebsocket
import yaml


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--obs_websocket_host", default="localhost")
    parser.add_argument("--obs_websocket_port", default="4455")
    parser.add_argument("--obs_websocket_secret", default="NL57EZrfB8Mby02l")
    parser.add_argument("--random_effect_name", default="Random Effect")
    parser.add_argument("--random_effect_dir", default=(
                                                        "C:\\Users\\Preston Connors\\Videos"
                                                        "\\Exercise\\Random Effects"
                                                       ))

    args = parser.parse_args()

    random_effect_file = random.choice(os.listdir(args.random_effect_dir))
    random_effect_file = os.path.join(args.random_effect_dir, random_effect_file)

    obsws = obswebsocket.obsws(args.obs_websocket_host,
                               args.obs_websocket_port,
                               args.obs_websocket_secret)
    obsws.connect()

    source = {"sceneName": "Routine", "sourceName": args.random_effect_name}
    scene_item_id = obsws.call(obswebsocket.requests.GetSceneItemId(**source)).__dict__
    time.sleep(1)
    scene_item_id = scene_item_id["datain"]["sceneItemId"]

    scene_item = {}
    scene_item["sceneItemId"] = scene_item_id
    scene_item["sceneName"] = source["sceneName"]

    input_settings = {}

    input_settings["inputName"] = args.random_effect_name
    input_settings = obsws.call(obswebsocket.requests.GetInputSettings(**input_settings)).__dict__
    local_file = os.path.basename(input_settings["datain"]["inputSettings"]["local_file"])
    output = obsws.call(obswebsocket.requests.GetSceneItemTransform(**scene_item)).__dict__
    time.sleep(1)
    print(yaml.dump(output, default_flow_style=False))
    scene_item = scene_item | output["datain"]
    scene_item = scene_item | {"sceneItemTransform": {}}
    #scene_item["sceneItemTransform"]["sourceHeight"] = 500
    #scene_item["sceneItemTransform"]["scaleX"] = 0.7249999761581421
    #output = obsws.call(obswebsocket.requests.SetSceneItemTransform(**scene_item)).__dict__
    time.sleep(1)
    output = {local_file: output["datain"]}
    print(yaml.dump(output, default_flow_style=False))
    obsws.disconnect()

if __name__ == "__main__":
    main()
