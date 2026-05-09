import os
import shutil
from pathlib import Path

from flask import jsonify, request

from . import video_bp
from ...routes.auth_routes.auth_extensions import token_auth

VIDEO_DIR = Path(os.getenv("VIDEO_DIR", "/app/videos"))
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}

VIDEO_DIR.mkdir(parents=True, exist_ok=True)


@video_bp.get("/videos")
@token_auth.login_required
def list_videos():
    """List all ingested video files."""
    videos = [
        {"filename": f.name, "size_bytes": f.stat().st_size}
        for f in sorted(VIDEO_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return jsonify({"videos": videos}), 200


@video_bp.post("/videos")
@token_auth.login_required
def ingest_video():
    """Receive and store a video file."""
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
    size = dest.stat().st_size
    print(f"Saved video: {dest} ({size} bytes)")
    return jsonify({"filename": file.filename, "size_bytes": size}), 201
