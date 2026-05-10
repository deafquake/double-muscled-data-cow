from flask import Blueprint

video_bp = Blueprint("video_bp", __name__)

from . import video_routes  # noqa: F401,E402
