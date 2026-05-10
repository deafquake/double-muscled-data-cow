import os
import argparse
import subprocess


def execute_command(cmd_list):
    print(">_ " + " ".join(cmd_list))
    subprocess.run(cmd_list, check=True)


def parse_time_range_line(line):
    parts = line.strip().split()
    if len(parts) < 2:
        raise ValueError("Invalid transcript line: '{}'".format(line))
    return parts[0], parts[1]


def main(shared_dir, video_name):
    transcript_path = os.path.join(shared_dir, 'lobrosa_out', video_name, f"{video_name}.txt")
    source_wav = os.path.join(shared_dir, 'ffmpegout0', video_name, f"{video_name}.wav")
    out_base_dir = os.path.join(shared_dir, 'ffmpeg2out', video_name)

    print(f"Using transcript: {transcript_path}")
    print(f"Source WAV: {source_wav}")
    print(f"Output directory: {out_base_dir}")

    if not os.path.isfile(transcript_path):
        raise SystemExit(f"Transcript file not found: {transcript_path}")
    if not os.path.isfile(source_wav):
        raise SystemExit(f"Source WAV not found: {source_wav}")

    os.makedirs(out_base_dir, exist_ok=True)

    with open(transcript_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    for idx, line in enumerate(lines):
        try:
            start, end = parse_time_range_line(line)
        except ValueError as e:
            print(f"Skipping invalid line {idx}: {line}")
            continue

        out_filename = f"{video_name}_{idx}.wav"
        out_path = os.path.join(out_base_dir, out_filename)

        cmd = [
            'ffmpeg', '-y', '-i', source_wav,
            '-ss', start, '-to', end,
            '-ar', '16000', '-ac', '1', out_path
        ]
        try:
            execute_command(cmd)
        except subprocess.CalledProcessError:
            print(f"ffmpeg failed for segment {idx} ({start} - {end}), continuing")


def run(shared_dir: str, video_name: str) -> None:
    main(shared_dir, video_name)
