import sys
import subprocess
import os
import argparse


def execute_command(command):
    print(">_ " + command)
    subprocess.run(command.split())


def main(args):
    shared_dir = args['shared']
    video_name = args['video']

    scenes_dir = os.path.join(shared_dir, 'ffmpeg1out', video_name)
    output_root = os.path.join(shared_dir, 'ffmpeg3out', video_name)
    os.makedirs(output_root, exist_ok=True)

    print("SCRIPT: Reading scenes from '{}', saving keyframes under '{}'".format(
        scenes_dir, output_root))

    scene_files = sorted(
        f for f in os.listdir(scenes_dir) if f.endswith('.mp4')
    )

    for scene_file in scene_files:
        scene_stem = os.path.splitext(scene_file)[0]
        scene_path = os.path.join(scenes_dir, scene_file)

        scene_out_dir = os.path.join(output_root, scene_stem)
        os.makedirs(scene_out_dir, exist_ok=True)

        output_pattern = os.path.join(scene_out_dir, 'frame-%04d.jpg')
        command = (
            'ffmpeg -i %s -vf fps=12/60 %s'
            % (scene_path, output_pattern)
        )
        execute_command(command)

    print("SCRIPT: Done. Keyframes written to '{}'".format(output_root))


def run(shared_dir: str, video_name: str) -> None:
    main({"shared": shared_dir, "video": video_name})
