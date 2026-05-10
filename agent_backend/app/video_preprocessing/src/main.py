import os
from .pipeline import run_pipeline
from .agent.orchestrator import Orchestrator, _TRANSCRIPT_BASE
from ...services.agent.transcript_analyzer import analyze_transcript
from ...services.vector_db.video_catalogue_connector import VideoCatalogueConnector
from ...services.vector_db.video_segments_connector import VideoSegmentsConnector
from ...utils.logger import get_logger

logger = get_logger(__name__)


def _merge_transcripts(video_name: str) -> str:
    """Concatenate all per-segment transcript files into one string."""
    transcripts_dir = os.path.join(_TRANSCRIPT_BASE, video_name)
    parts = []
    for entry in os.scandir(transcripts_dir):
        with open(entry.path, "r", encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)


def run_video_processing(
    shared_dir: str,
    video_name: str,
    timestamp: str | None = None,
    user_id=None,
) -> dict:
    """
    Run the full video processing pipeline and return the structured result.

    Steps
    -----
    1. Run the ffmpeg / Whisper / YOLO pipeline stages.
    2. Run the LLM orchestrator to produce a structured daily summary.
    3. Pass the full transcript and pre-extracted events to the transcript
       analyzer, which resolves relative time references to absolute datetimes
       and (when a user_id is supplied) persists them as calendar candidates.
    4. Store the video-level summary and each segment in Milvus for later
       retrieval via the research agent.

    Parameters
    ----------
    shared_dir  : path to the shared volume (videos + outputs live here)
    video_name  : stem of the video filename (no extension)
    timestamp   : ISO datetime the video was recorded; used as the reference
                  anchor when resolving relative times like "Tuesday at noon"
    user_id     : authenticated user — pass None to skip calendar DB persistence

    Returns
    -------
    dict — the final metadata produced by the orchestrator, augmented with
           the merged full_transcript and the recording timestamp.
    """
    logger.info("Starting video processing — video: %s", video_name)

    # Stage 1-7: ffmpeg, librosa, Whisper ASR, YOLO key-frame detection.
    run_pipeline(shared_dir, video_name)
    logger.info("Pipeline finished — starting orchestrator analysis for %s", video_name)

    # LLM orchestrator: produces the structured daily summary with people,
    # decisions, calendar events (with relative times), and a brief summary.
    orch = Orchestrator()
    metadata = orch.analyse_video(video_name)

    # Attach metadata that downstream steps need.
    metadata["full_transcript"] = _merge_transcripts(video_name)
    print(metadata["full_transcript"])
    if timestamp:
        metadata["timestamp"] = timestamp

    # Pass the transcript and the orchestrator's pre-extracted events to the
    # transcript analyzer so it can resolve relative times ("Tuesday at noon")
    # to absolute datetimes anchored at the video's recording timestamp.
    preextracted_events = metadata.get("calendar_events", [])
    try:
        analyze_transcript(
            transcript_text=metadata["full_transcript"],
            user_id=user_id,
            reference_datetime=timestamp,
            preextracted_events=preextracted_events,
        )
        logger.info("calendar analysis complete")
    except Exception as exc:
        # Calendar extraction is best-effort — don't fail the whole pipeline.
        logger.warning("transcript_analyzer failed (non-fatal): %s", exc)

    # Store the video-level summary and per-segment entries in Milvus so
    # the research agent can answer questions like "when did I discuss X?".
    try:
        VideoCatalogueConnector().store_video(metadata)
        VideoSegmentsConnector().store_segments(metadata)
    except Exception as exc:
        logger.warning("Milvus storage failed (non-fatal): %s", exc)

    logger.info("Video processing complete — video: %s", video_name)
    return metadata
