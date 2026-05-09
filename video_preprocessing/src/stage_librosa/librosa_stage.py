import librosa
import sys
import time
import math
import os
import argparse
import subprocess
from librosa import feature
from librosa import core


def execute_command(command):
    print(">_ " + command)
    subprocess.run(command.split())


def samples_to_timestamp(sample, is_start):
    time_in_seconds = sample / 22050
    if is_start:
        time_in_seconds = math.floor(time_in_seconds)
    else:
        time_in_seconds = math.ceil(time_in_seconds)
    formatted_time = time.strftime('%H:%M:%S', time.gmtime(time_in_seconds))
    return formatted_time, time_in_seconds


def main(args):
    shared_dir = args['shared']
    video_name = args['video']

    print("SCRIPT: Processing video '{}' | reading from '{}/ffmpegout0/{}' | writing to '{}/lobrosa_out/{}'".format(
        video_name, shared_dir, video_name, shared_dir, video_name))

    ffmpeg_dir = os.path.join(shared_dir, 'ffmpegout0', video_name)
    audio_path = os.path.join(ffmpeg_dir, video_name + ".wav")

    audio, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=audio, sr=sr)

    max_sentence_lenght = 29
    min_sentence_lenght = 6

    min_clips_number = duration / max_sentence_lenght
    max_clips_number = duration / min_sentence_lenght

    for threshold_db in range(15, 40):
        clips = librosa.effects.split(audio, top_db=threshold_db)
        print(">_ %s clips with %s dB as treshold" % (len(clips), threshold_db))
        if len(clips) >= min_clips_number and len(clips) < max_clips_number:
            break
    print(">_ Final number of clips: %s" % len(clips))

    target_dir = os.path.join(shared_dir, 'lobrosa_out', video_name)
    os.makedirs(target_dir, exist_ok=True)
    dmm = 0

    timestamps_path = os.path.join(target_dir, video_name + ".txt")
    with open(timestamps_path, "w") as file:
        last_timestamp = "00:00:00"
        last_seconds = 0
        for i in range(len(clips)):
            c = clips[i]
            start_timestamp = last_timestamp
            start_seconds = last_seconds
            end_timestamp, end_seconds = samples_to_timestamp(c[1], False)
            clip_lenght = end_seconds - start_seconds
            if clip_lenght > max_sentence_lenght:
                end_seconds = start_seconds + max_sentence_lenght
                end_timestamp = time.strftime('%H:%M:%S', time.gmtime(end_seconds))
                clip_lenght = end_seconds - start_seconds

            if start_seconds != end_seconds and clip_lenght > min_sentence_lenght:
                file.write(start_timestamp + " " + end_timestamp + "\n")
                dmm += 1
                last_timestamp = end_timestamp
                last_seconds = end_seconds

    print(
        ">_ Wrote %d timestamps to %s" % (len(open(timestamps_path).read().splitlines()), timestamps_path)
    )


def run(shared_dir: str, video_name: str) -> None:
    main({"shared": shared_dir, "video": video_name})
