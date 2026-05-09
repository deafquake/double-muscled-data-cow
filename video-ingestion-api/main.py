import os
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

VIDEO_DIR = Path(os.getenv("VIDEO_DIR", "/app/videos"))
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}

app = FastAPI(title="Video Ingestion API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/videos", status_code=201)
async def ingest_video(file: UploadFile = File(...)):
    """Receive and store a video file sent by another service."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix}")

    dest = VIDEO_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    print(f"Saved video: {dest} ({dest.stat().st_size} bytes)") 
    return {"filename": file.filename, "size_bytes": dest.stat().st_size}


@app.get("/videos")
def list_videos():
    """List all ingested video files."""
    videos = [
        {"filename": f.name, "size_bytes": f.stat().st_size}
        for f in sorted(VIDEO_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return {"videos": videos}
