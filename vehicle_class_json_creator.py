### Run this program to create json file that contains label of each vehicle type in CARLA
### The JSON file is required to get vehicle's ground truth class when using carla_vehicle_annotator function

### Set this variable to True if you want the program to give label 0 to every vehicle type
autoFill = True

### This dictionary contains the mapping of vehicle types to their respective class IDs
cls2id = {
    "car": 0,
    "truck": 1,
    "van": 2,
    "bus": 3,
    "motorcycle": 4,
    "bicycle": 5,
}

import glob
import os
import sys

try:
    sys.path.append(
        glob.glob(
            "../carla/dist/carla-*%d.%d-%s.egg"
            % (
                sys.version_info.major,
                sys.version_info.minor,
                "win-amd64" if os.name == "nt" else "linux-x86_64",
            )
        )[0]
    )
except IndexError:
    pass

import carla

import math
import random
import json


def get_transform(vehicle_location, angle, d=6.4):
    a = math.radians(angle)
    location = carla.Location(d * math.cos(a), d * math.sin(a), 2.0) + vehicle_location
    return carla.Transform(location, carla.Rotation(yaw=180 + angle, pitch=-15))


def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    spectator = world.get_spectator()
    vehicle_blueprints = world.get_blueprint_library().filter("vehicle")

    location = random.choice(world.get_map().get_spawn_points()).location
    vehicle_dict = {}
    for blueprint in vehicle_blueprints:
        transform = carla.Transform(location, carla.Rotation(yaw=-45.0))
        vehicle = world.spawn_actor(blueprint, transform)
        try:
            spectator.set_transform(get_transform(location, -30))
            if autoFill:
                # Special case for some vehicles
                if (
                    vehicle.type_id == "vehicle.bmw.grandtourer"
                    or vehicle.type_id == "vehicle.mini.cooper_s"
                ):
                    x = 0
                else:
                    base_type = (
                        vehicle_blueprints.find(vehicle.type_id)
                        .get_attribute("base_type")
                        .as_str()
                        .lower()
                    )
                    x = cls2id.get(base_type)
                print(str(vehicle.type_id) + " class " + str(x))
            else:
                x = input(str(vehicle.type_id) + " class? (must be integer) ")
                x = int(x)
            vehicle_dict[str(vehicle.type_id)] = x
        finally:
            vehicle.destroy()
    json_dict = {"reference": cls2id, "classification": vehicle_dict}
    with open("vehicle_class_json_file.txt", "w+") as outfile:
        json_file = json.dump(json_dict, outfile, indent=4)


if __name__ == "__main__":
    main()
