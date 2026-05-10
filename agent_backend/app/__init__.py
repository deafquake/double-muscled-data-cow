
import os

from flask import Flask, g
from flask_cors import CORS

from app.config.config import JWT_SECRET, FRONTEND_URL
from app.db import init_db
from app.routes.chat_routes import chat_bp
from app.routes.file_routes import file_bp
from app.routes.auth_routes import auth_bp
from app.routes.video_routes import video_bp
from app.routes.calendar_candidate_routes import candidate_bp

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = JWT_SECRET
    # "origins: *" with credentials is invalid CORS — browsers silently drop Set-Cookie.
    # Read the allowed origin from FRONTEND_URL so cookies work cross-origin.
    allowed_origin = os.environ.get("FRONTEND_URL", FRONTEND_URL) or "http://localhost:3000"
    CORS(app, resources={r"/*": {"origins": allowed_origin}}, supports_credentials=True)
    app.register_blueprint(chat_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(video_bp)
    app.register_blueprint(candidate_bp)
    init_db()
    
    @app.teardown_appcontext
    def close_db_session(exception=None):
        """Automatically close database session after each request."""
        db = g.pop('db', None)
        if db is not None:
            db.close()
    
    return app

app = create_app()