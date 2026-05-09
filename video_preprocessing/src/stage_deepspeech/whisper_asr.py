import os
import argparse
import torch
from transformers import pipeline

_asr_pipeline = None


def _get_asr_pipeline(model_id: str = os.environ.get("WHISPER_MODEL", "openai/whisper-base")):
    global _asr_pipeline
    if _asr_pipeline is None:
        device = 0 if torch.cuda.is_available() else -1
        print(f"Loading Whisper model '{model_id}' on {'GPU' if device == 0 else 'CPU'} ...")
        _asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            device=device,
        )
        print("Model loaded.")
    return _asr_pipeline


def transcribe(audio_path: str) -> str:
    asr = _get_asr_pipeline()
    print(f">_ whisper transcribe: {audio_path}")
    result = asr(audio_path)
    transcript = result.get("text", "").strip()
    print(transcript)
    return transcript


def main(args):
    shared_dir = args["shared"]
    video_name = args["video"]

    video_stem = os.path.splitext(video_name)[0]

    print(f"SCRIPT: shared='{shared_dir}'  video='{video_stem}'")

    audio_segments_dir = os.path.join(shared_dir, "ffmpeg2out", video_stem)
    librosa_txt = os.path.join(shared_dir, "lobrosa_out", video_stem, f"{video_stem}.txt")
    deepspeech_out_dir = os.path.join(shared_dir, "deepspeechout", video_stem)

    if not os.path.isdir(audio_segments_dir):
        raise RuntimeError(f"Audio segments directory not found: '{audio_segments_dir}'")
    if not os.path.isfile(librosa_txt):
        raise RuntimeError(f"Librosa scene file not found: '{librosa_txt}'")

    with open(librosa_txt, "r") as f:
        scenes = [line.strip() for line in f if line.strip()]

    num_scenes = len(scenes)
    print(f"Found {num_scenes} scene(s) in '{librosa_txt}'")

    os.makedirs(deepspeech_out_dir, exist_ok=True)

    for idx in range(num_scenes):
        wav_path = os.path.join(audio_segments_dir, f"{video_stem}_{idx}.wav")

        if not os.path.isfile(wav_path):
            print(f"WARNING: expected audio segment not found, skipping: '{wav_path}'")
            continue

        print(f"\n--- Segment {idx} / {num_scenes - 1}  [{scenes[idx]}] ---")
        transcript = transcribe(wav_path)
        print(f"Transcript: {transcript}")

        out_txt = os.path.join(deepspeech_out_dir, f"{video_stem}_{idx}.txt")
        with open(out_txt, "w") as f:
            f.write(transcript + "\n")
        print(f"Saved → '{out_txt}'")

    print(f"\nDone. Transcripts written to '{deepspeech_out_dir}'")


def run(shared_dir: str, video_name: str) -> None:
    main({"shared": shared_dir, "video": video_name})
