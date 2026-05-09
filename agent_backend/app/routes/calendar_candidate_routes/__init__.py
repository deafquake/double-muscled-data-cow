from flask import Blueprint

candidate_bp = Blueprint("candidate_bp", __name__)

from . import routes  # noqa: E402, F401
