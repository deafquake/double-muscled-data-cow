import base64
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import g, jsonify, request

from . import video_bp
from ...routes.auth_routes.auth_extensions import basic_auth, token_auth
from ...video_preprocessing.src.main import run_video_processing
from ...db.mongodb_connector import MongoDBConnector
from ...config.config import FILE_DB_NAME, VIDEO_COLLECTION

VIDEO_DIR = Path(os.getenv("VIDEO_DIR", "/app/videos"))
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}

VIDEO_DIR.mkdir(parents=True, exist_ok=True)

mongo_connector = MongoDBConnector()


@video_bp.get("/videos")
def list_videos():
    """List all ingested video files."""
    videos = [
        {"filename": f.name, "size_bytes": f.stat().st_size}
        for f in sorted(VIDEO_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return jsonify({"videos": videos}), 200


@video_bp.post("/videos")
@basic_auth.login_required
def ingest_video():
    """Receive, store, and process a video file."""
    user = g.user
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No filename provided"}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {suffix}"}), 415

    dest = VIDEO_DIR / file.filename
    file.save(dest)

    # Record when the video was saved so the transcript analyzer can resolve
    # relative time references ("Tuesday at noon") against this anchor.
    created_at = datetime.fromtimestamp(dest.stat().st_ctime, tz=timezone.utc)
    timestamp = created_at.isoformat()

    print(f"Saved video: {dest} ({dest.stat().st_size} bytes)")
    print(f"Starting processing for {dest}...")

    result = run_video_processing(
        shared_dir=str(VIDEO_DIR),
        video_name=dest.stem,
        timestamp=timestamp,
        user_id=user.id,
    )

    print(f"Finished processing for {dest}")

    collection = mongo_connector.get_collection(FILE_DB_NAME, VIDEO_COLLECTION)
    collection.insert_one({"created_at": created_at, "user_id": str(user.id), **result})

    return jsonify({"message": "Video ingested and processed successfully", "result": result}), 201


@video_bp.get("/videos/transcripts")
@token_auth.login_required
def list_transcripts():
    """Return all video transcripts for the authenticated user on a given date."""
    user = g.user
    date_str = request.args.get("date")

    try:
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.now(timezone.utc).date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    date_prefix = target_date.isoformat()  # "YYYY-MM-DD"
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    # user.id is a UUID object; pymongo 4.x with UuidRepresentation.UNSPECIFIED
    # cannot encode raw uuid.UUID in queries. Convert to string and also cover
    # documents without a user_id for backward compat with pre-tracking data.
    user_id_str = str(user.id)
    user_filter = {
        "$or": [
            {"user_id": user_id_str},
            {"user_id": {"$exists": False}},
            {"user_id": None},
        ]
    }

    # Date can be matched against the BSON datetime `created_at` field OR against
    # the ISO-string `timestamp` field (whichever is present in the document).
    date_filter = {
        "$or": [
            {"created_at": {"$gte": start, "$lte": end}},
            {"timestamp": {"$regex": f"^{date_prefix}"}},
        ]
    }
    query = {"$and": [user_filter, date_filter]}

    try:
        collection = mongo_connector.get_collection(FILE_DB_NAME, VIDEO_COLLECTION)
        cursor = collection.find(
            query,
            {"_id": 0, "full_transcript": 0, "running_state": 0},
        ).sort("created_at", 1)

        transcripts = []
        for doc in cursor:
            if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
                doc["created_at"] = doc["created_at"].isoformat()
            transcripts.append(doc)

        return jsonify({"transcripts": transcripts}), 200
    except Exception as exc:
        print(f"[list_transcripts] MongoDB error: {exc}", flush=True)
        return jsonify({"error": f"Database error: {exc}"}), 500


@video_bp.get("/videos/<video_id>/segment/<int:seg_num>/frames")
@token_auth.login_required
def get_segment_frames(video_id: str, seg_num: int):
    """Return base64-encoded keyframes for a specific video segment."""
    shared_dir = Path(os.environ.get("SHARED_DIR", "/app/shared"))
    scene_dir = shared_dir / "objectdetectorout" / video_id / f"{video_id}_{seg_num}"

    if not scene_dir.is_dir():
        return jsonify({"frames": []}), 200

    frames = []
    for frame_path in sorted(scene_dir.glob("*.jpg")):
        with open(frame_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        frames.append({
            "filename": frame_path.name,
            "data_url": f"data:image/jpeg;base64,{b64}",
        })

    return jsonify({"frames": frames}), 200
