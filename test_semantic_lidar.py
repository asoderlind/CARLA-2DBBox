### Example program to save several sensor data including bounding box
### Sensors: RGB Camera (+BoundingBox), Semantic Lidar
### By Mukhlas Adib
### 2020
### Last tested on CARLA 0.9.10.1

### CARLA Simulator is licensed under the terms of the MIT license
### For a copy, see <https://opensource.org/licenses/MIT>
### For more information about CARLA Simulator, visit https://carla.org/

import glob
import os
import sys
import time
from tqdm import tqdm

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

import argparse
import logging
import random
import queue
import carla_vehicle_annotator as cva

### Set to True if you need to save the data in darknet training format, False otherwise
save_darknet = True
###


def retrieve_data(sensor_queue, frame, timeout=1):
    while True:
        try:
            data = sensor_queue.get(True, timeout)
        except queue.Empty:
            return None
        if data.frame == frame:
            return data


def main():
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        "--host",
        metavar="H",
        default="127.0.0.1",
        help="IP of the host server (default: 127.0.0.1)",
    )
    argparser.add_argument(
        "-p",
        "--port",
        metavar="P",
        default=2000,
        type=int,
        help="TCP port to listen to (default: 2000)",
    )
    argparser.add_argument(
        "-n",
        "--number-of-vehicles",
        metavar="N",
        default=150,
        type=int,
        help="number of vehicles (default: 100)",
    )
    argparser.add_argument(
        "-tm_p",
        "--tm_port",
        metavar="P",
        default=8000,
        type=int,
        help="port to communicate with TM (default: 8000)",
    )
    argparser.add_argument(
        "-m",
        "--map",
        metavar="M",
        default="Town06",
        type=str,
        help="map to load (default: Town06)",
    )
    argparser.add_argument(
        "-t",
        "--training-set",
        metavar="T",
        default="train",
        type=str,
        help="training set to save the data (default: train)",
        choices=["train", "val"],
    )
    argparser.add_argument(
        "-f",
        "--frames",
        metavar="I",
        default=100,
        type=int,
        help="number of frames to run (default: 100)",
    )
    argparser.add_argument(
        "-d",
        "--dataset-path",
        metavar="D",
        default="../yolo-testing/datasets/carla-yolo",
        type=str,
        help="relative path to which we save the yolo files",
    )
    argparser.add_argument(
        "-c",
        "--min-detect",
        metavar="C",
        default=10,
        type=int,
        help="minimum number of detection points for the vehicle to be considered",
    )
    argparser.add_argument(
        "-s",
        "--sun-altitude",
        metavar="S",
        default=-90,
        type=float,
        help="sun altitude angle (default: -90)",
    )

    args = argparser.parse_args()

    vehicles_list = []
    nonvehicles_list = []
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    # For dataset metadata
    train_set = args.training_set
    cur_frame = 0
    max_frames = args.frames
    print("Max frames: %d" % max_frames)
    print("Training set: %s" % train_set)

    available_maps = client.get_available_maps()
    map = f"/Game/Carla/Maps/{args.map}"

    if map not in available_maps:
        print("Map %s is not available. Available maps are: %s" % (map, available_maps))
        sys.exit(1)
    client.load_world(map)
    print("Map %s loaded" % map)

    # Unique video name
    vid_name = (
        str(int(time.time()))[-5:]
        + "-"
        + args.map
        + "-"
        + str(args.number_of_vehicles)
        + "npc"
    )
    print("Video name: %s" % vid_name)

    try:
        traffic_manager = client.get_trafficmanager(args.tm_port)
        traffic_manager.set_global_distance_to_leading_vehicle(2.0)
        world = client.get_world()

        # Set weather
        weather = world.get_weather()
        weather.sun_altitude_angle = args.sun_altitude
        world.set_weather(weather)
        print("Weather set to night")

        # Print argument for number of vehicles
        print("Number of vehicles: %d" % args.number_of_vehicles)

        # Remove parked vehicles
        objects_to_toggle = set()
        parked_cars = world.get_environment_objects(carla.CityObjectLabel.Car)
        parked_buses = world.get_environment_objects(carla.CityObjectLabel.Bus)
        parked_trucks = world.get_environment_objects(carla.CityObjectLabel.Truck)
        parked_motorcycles = world.get_environment_objects(
            carla.CityObjectLabel.Motorcycle
        )
        parked_bicycles = world.get_environment_objects(carla.CityObjectLabel.Bicycle)
        parked_riders = world.get_environment_objects(carla.CityObjectLabel.Rider)
        parked_vehicles = (
            parked_cars
            + parked_buses
            + parked_trucks
            + parked_motorcycles
            + parked_bicycles
            + parked_riders
        )
        for parked_vehicle in parked_vehicles:
            if parked_vehicle.id not in objects_to_toggle:
                objects_to_toggle.add(parked_vehicle.id)
        world.enable_environment_objects(objects_to_toggle, False)
        print("Parked vehicles removed")

        print("\nRUNNING in synchronous mode\n")
        settings = world.get_settings()
        traffic_manager.set_synchronous_mode(True)
        if not settings.synchronous_mode:
            synchronous_master = True
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = 0.05
            world.apply_settings(settings)
        else:
            synchronous_master = False

        blueprints = world.get_blueprint_library().filter("vehicle.*")

        spawn_points = world.get_map().get_spawn_points()
        number_of_spawn_points = len(spawn_points)
        print("Number of spawn points: %d" % number_of_spawn_points)

        if args.number_of_vehicles < number_of_spawn_points:
            random.shuffle(spawn_points)
        elif args.number_of_vehicles > number_of_spawn_points:
            msg = "Requested %d vehicles, but could only find %d spawn points"
            logging.warning(msg, args.number_of_vehicles, number_of_spawn_points)
            args.number_of_vehicles = number_of_spawn_points

        SpawnActor = carla.command.SpawnActor
        SetAutopilot = carla.command.SetAutopilot
        FutureActor = carla.command.FutureActor

        # --------------
        # Spawn vehicles
        # --------------
        batch = []
        for n, transform in enumerate(spawn_points):
            if n >= args.number_of_vehicles:
                break
            blueprint = random.choice(blueprints)
            if blueprint.has_attribute("color"):
                color = random.choice(
                    blueprint.get_attribute("color").recommended_values
                )
                blueprint.set_attribute("color", color)
            if blueprint.has_attribute("driver_id"):
                driver_id = random.choice(
                    blueprint.get_attribute("driver_id").recommended_values
                )
                blueprint.set_attribute("driver_id", driver_id)
            blueprint.set_attribute("role_name", "autopilot")
            batch.append(
                SpawnActor(blueprint, transform).then(SetAutopilot(FutureActor, True))
            )
            spawn_points.pop(0)

        for response in client.apply_batch_sync(batch, synchronous_master):
            if response.error:
                logging.error(response.error)
            else:
                vehicles_list.append(response.actor_id)

        print("Created %d npc vehicles \n" % len(vehicles_list))

        # -----------------------------
        # Spawn ego vehicle and sensors
        # -----------------------------
        q_list = []
        idx = 0

        tick_queue = queue.Queue()
        world.on_tick(tick_queue.put)
        q_list.append(tick_queue)
        tick_idx = idx
        idx = idx + 1

        # Spawn ego vehicle
        ego_bp = random.choice(blueprints)
        ego_transform = random.choice(spawn_points)
        ego_vehicle = world.spawn_actor(ego_bp, ego_transform)
        vehicles_list.append(ego_vehicle)
        ego_vehicle.set_autopilot(True)
        print("Ego-vehicle ready")

        # Turn on the lights of all vehicles
        light_mask = carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam
        all_vehicles = world.get_actors()
        for ve in all_vehicles:
            if "vehicle." in ve.type_id:
                ve.set_light_state(carla.VehicleLightState(light_mask))
        print("All vehicles lights on")

        # Spawn RGB camera
        cam_transform = carla.Transform(carla.Location(x=1.5, z=2.4))
        cam_bp = world.get_blueprint_library().find("sensor.camera.rgb")
        cam_bp.set_attribute("sensor_tick", "1.0")
        cam = world.spawn_actor(cam_bp, cam_transform, attach_to=ego_vehicle)
        nonvehicles_list.append(cam)
        cam_queue = queue.Queue()
        cam.listen(cam_queue.put)
        q_list.append(cam_queue)
        cam_idx = idx
        idx = idx + 1
        print("RGB camera ready")

        # Spawn LIDAR sensor
        lidar_bp = world.get_blueprint_library().find("sensor.lidar.ray_cast_semantic")
        lidar_bp.set_attribute("sensor_tick", "1.0")
        lidar_bp.set_attribute("channels", "64")
        lidar_bp.set_attribute("points_per_second", "1120000")
        lidar_bp.set_attribute("upper_fov", "40")
        lidar_bp.set_attribute("lower_fov", "-40")
        lidar_bp.set_attribute("range", "100")
        lidar_bp.set_attribute("rotation_frequency", "20")
        lidar_transform = carla.Transform(carla.Location(x=1.5, z=2.4))
        lidar = world.spawn_actor(lidar_bp, lidar_transform, attach_to=ego_vehicle)
        nonvehicles_list.append(lidar)
        lidar_queue = queue.Queue()
        lidar.listen(lidar_queue.put)
        q_list.append(lidar_queue)
        lidar_idx = idx
        idx = idx + 1
        print("LIDAR ready")

        # Begin the loop
        time_sim = 0
        progress_bar = tqdm(total=max_frames, desc="Frames", unit="frames")
        while True:
            # Extract the available data
            nowFrame = world.tick()

            # Check whether it's time for sensor to capture data
            if time_sim >= 1:
                data = [retrieve_data(q, nowFrame) for q in q_list]
                assert all(x.frame == nowFrame for x in data if x is not None)

                # Skip if any sensor data is not available
                if None in data:
                    continue

                vehicles_raw = world.get_actors().filter("vehicle.*")
                snap = data[tick_idx]
                rgb_img = data[cam_idx]
                lidar_img = data[lidar_idx]

                # Attach additional information to the snapshot
                vehicles = cva.snap_processing(vehicles_raw, snap)

                # Calculating visible bounding boxes
                filtered_out, _ = cva.auto_annotate_lidar(
                    vehicles,
                    cam,
                    lidar_img,
                    show_img=rgb_img,
                    min_detect=args.min_detect,
                    json_path="vehicle_class_json_file.txt",
                )

                # Save the results
                cva.save_output(
                    rgb_img,
                    filtered_out["bbox"],
                    filtered_out["class"],
                    save_patched=True,
                    out_format="json",
                )

                # Save the results to darknet format
                if save_darknet:
                    cva.save2darknet(
                        cur_frame,
                        filtered_out["bbox"],
                        filtered_out["class"],
                        filtered_out["distances"],
                        rgb_img,
                        video_name=vid_name,
                        dataset_path=args.dataset_path,
                        train_set=train_set,
                    )

                time_sim = 0
                cur_frame += 1
                progress_bar.update(1)  # <-- Update progress bar
            if cur_frame >= max_frames:
                break
            time_sim = time_sim + settings.fixed_delta_seconds

        progress_bar.close()  # <-- Close progress bar when done

    finally:
        try:
            if save_darknet:
                cva.save2darknet(None, None, None, None, save_train=True)
        except:
            print("No darknet formatted data directory found")
        try:
            cam.stop()
            lidar.stop()
        except:
            print("Sensors has not been initiated")

        settings = world.get_settings()
        settings.synchronous_mode = False
        settings.fixed_delta_seconds = None
        world.apply_settings(settings)

        print("\ndestroying %d vehicles" % len(vehicles_list))
        client.apply_batch([carla.command.DestroyActor(x) for x in vehicles_list])

        print("destroying %d nonvehicles" % len(nonvehicles_list))
        client.apply_batch([carla.command.DestroyActor(x) for x in nonvehicles_list])

        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        print("\ndone.")
