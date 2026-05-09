import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

from stage_ffmpeg0 import ffmpeg0
from stage_librosa import librosa_stage
from stage_ffmpeg1 import ffmpeg1
from stage_ffmpeg2 import ffmpeg2
from stage_deepspeech import whisper_asr
from stage_ffmpeg3 import ffmpeg3
from stage_object_detector import object_detector


def run_pipeline(shared_dir: str, video_name: str) -> None:
    log.info("Stage 1 — ffmpeg0: Extract full audio")
    ffmpeg0.run(shared_dir, video_name)

    log.info("Stage 2 — librosa: Detect silence / find cut points")
    librosa_stage.run(shared_dir, video_name)

    log.info("Stage 3 — ffmpeg1: Segment video into clips")
    ffmpeg1.run(shared_dir, video_name)

    log.info("Stage 4 — ffmpeg2: Per-clip audio extraction")
    ffmpeg2.run(shared_dir, video_name)

    log.info("Stage 5 — Whisper: Speech-to-text transcription")
    whisper_asr.run(shared_dir, video_name)

    log.info("Stage 6 — ffmpeg3: Key frame extraction")
    ffmpeg3.run(shared_dir, video_name)

    log.info("Stage 7 — object_detector: YOLOv4 detection")
    object_detector.run(shared_dir, video_name)

    log.info("Pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full video search pipeline sequentially.")
    parser.add_argument(
        "-s", "--shared",
        default=os.environ.get("SHARED", "/data"),
        help="Shared data directory; input video expected at <shared>/<video>.mp4")
    parser.add_argument(
        "-v", "--video",
        default=os.environ.get("VIDEO", "osc"),
        help="Video base name without extension (e.g. osc)")
    args = parser.parse_args()
    run_pipeline(args.shared, args.video)
