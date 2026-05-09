import subprocess
import os
import argparse


def execute_command(command):
    print(">_ " + command)
    subprocess.run(command.split())


def main(args):
    shared_dir = args['shared']
    video_name = args['video']

    print("SCRIPT: shared='{}', video='{}'".format(shared_dir, video_name))

    lobrosa_video_dir = os.path.join(shared_dir, "lobrosa_out", video_name)
    transcript_path   = os.path.join(lobrosa_video_dir, video_name + ".txt")
    video_path        = os.path.join(shared_dir, video_name + ".mp4")

    output_dir = os.path.join(shared_dir, "ffmpeg1out", video_name)
    os.makedirs(output_dir, exist_ok=True)

    print("SCRIPT: Reading transcript from '{}'".format(transcript_path))
    print("SCRIPT: Reading video from '{}'".format(video_path))
    print("SCRIPT: Writing clips to '{}'".format(output_dir))

    with open(transcript_path) as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    for i, line in enumerate(lines):
        start, end = line.split()
        clip_path = os.path.join(output_dir, "{}_{}.mp4".format(video_name, i))
        command = "ffmpeg -ss %s -to %s -i %s -c copy %s" % (start, end, video_path, clip_path)
        execute_command(command)


def run(shared_dir: str, video_name: str) -> None:
    main({"shared": shared_dir, "video": video_name})
