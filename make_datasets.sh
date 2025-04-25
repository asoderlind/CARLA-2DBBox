#!/bin/bash

# This script creates the datasets for the project.

mkdir ../yolo-testing/datasets/carla-world06-night
mkdir ../yolo-testing/datasets/carla-world06-night/labels
mkdir ../yolo-testing/datasets/carla-world06-night/images

mkdir ../yolo-testing/datasets/carla-world06-sunset
mkdir ../yolo-testing/datasets/carla-world06-sunset/labels
mkdir ../yolo-testing/datasets/carla-world06-sunset/images

mkdir ../yolo-testing/datasets/carla-world06-day
mkdir ../yolo-testing/datasets/carla-world06-day/labels
mkdir ../yolo-testing/datasets/carla-world06-day/images

python3.8 test_semantic_lidar.py --frames 10000 --training-set train --dataset-path "../yolo-testing/datasets/carla-world06-night"
python3.8 test_semantic_lidar.py --frames 3000  --training-set val --dataset-path "../yolo-testing/datasets/carla-world06-night"

python3.8 test_semantic_lidar.py --frames 10000 -s 0.5 --training-set train --dataset-path "../yolo-testing/datasets/carla-world06-sunset"
python3.8 test_semantic_lidar.py --frames 3000 -s 0.5 --training-set val --dataset-path "../yolo-testing/datasets/carla-world06-sunset"

python3.8 test_semantic_lidar.py --frames 10000 -s 90 --training-set train --dataset-path "../yolo-testing/datasets/carla-world06-day"
python3.8 test_semantic_lidar.py --frames 3000 -s 90 --training-set val --dataset-path "../yolo-testing/datasets/carla-world06-day"

