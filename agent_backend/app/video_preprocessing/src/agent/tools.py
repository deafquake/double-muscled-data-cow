import os
import glob

# Inside Docker the shared volume is mounted at /app/shared.
# On the host (development) it lives at ../local-shared relative to this file.
_SHARED = os.environ.get(
    "SHARED_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "local-shared"),
)
_BASE            = _SHARED
_TRANSCRIPT_BASE = os.path.join(_BASE, "deepspeechout")
_KEYFRAME_BASE   = os.path.join(_BASE, "objectdetectorout")


def get_current_scene_transcript(name_of_video: str, scene_number: int) -> str:
    """Return the transcript text for the given video and scene number.

    File layout: local-shared/deepspeechout/<name_of_video>/<name_of_video>_<scene_number>.txt
    Returns the transcript string, or raises FileNotFoundError if missing.
    """
    path = os.path.join(
        _TRANSCRIPT_BASE,
        name_of_video,
        f"{name_of_video}_{scene_number}.txt",
    )
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Transcript not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_current_scene_keyframes(name_of_video: str, scene_number: int) -> list[str]:
    """Return a sorted list of absolute paths to keyframe JPGs for the given scene.

    File layout: local-shared/objectdetectorout/<name_of_video>/<name_of_video>_<scene_number>/frame-XXXX.jpg
    Returns a list of file paths (may be empty if no frames exist yet).
    """
    scene_dir = os.path.join(
        _KEYFRAME_BASE,
        name_of_video,
        f"{name_of_video}_{scene_number}",
    )
    if not os.path.isdir(scene_dir):
        raise FileNotFoundError(f"Keyframe directory not found: {scene_dir}")
    frames = sorted(glob.glob(os.path.join(scene_dir, "*.jpg")))
    return frames


def get_currentscene(name_of_video: str, scene_number: int) -> dict:
    """Return both the transcript and keyframe paths for the given scene.

    Returns a dict:
    {
        "transcript": <str>,          # full transcript text
        "keyframes":  [<str>, ...],   # sorted list of absolute keyframe JPG paths
    }
    Raises FileNotFoundError if either resource is missing.
    """
    return {
        "transcript": get_current_scene_transcript(name_of_video, scene_number),
        "keyframes":  get_current_scene_keyframes(name_of_video, scene_number),
    }

