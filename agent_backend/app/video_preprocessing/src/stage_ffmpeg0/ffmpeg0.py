import sys
import subprocess
import os
import argparse
from pathlib import Path


def execute_command(command):
    print(">_ " + command)
    subprocess.run(command.split())


def main(args):
    orig_input = args['input']
    video_name = os.path.basename(orig_input).split(".")[0]
    orig_output = args.get('output')

    if orig_output:
        print("Using provided output directory:", orig_output)
        output_base = os.path.join(orig_output, 'ffmpegout0')
    else:
        print("No output directory provided, using default 'shared/ffmpeg0out'")
        output_base = str(Path.cwd() / 'shared' / 'ffmpeg0out')

    output_dir = os.path.join(output_base, video_name)
    os.makedirs(output_dir, exist_ok=True)

    audio_path = os.path.join(output_dir, video_name + ".wav")

    print("SCRIPT: Input at '{}' -> writing to '{}'".format(orig_input, output_dir))
    print("Extracting audio to:", audio_path)
    execute_command("ffmpeg -i %s -map 0:a %s" % (orig_input, audio_path))


def run(shared_dir: str, video_name: str) -> None:
    main({"input": f"{shared_dir}/{video_name}.mp4", "output": shared_dir})
