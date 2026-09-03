import os
from flask import Flask
from flask_cors import CORS
from . import barnes_and_noble_blueprint
from . import (
    barnes_and_noble_auth_blueprint,
)
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file  
def create_app():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "shared", "templates"),
        static_folder=os.path.join(root, "shared", "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
    CORS(app, resources={r"/*": {"origins": os.environ.get("CORS_ORIGINS", "https://tufts.campusgenai.org").split(",")}})
    app.register_blueprint(barnes_and_noble_blueprint, url_prefix='/barnes_and_noble')
    app.register_blueprint(
        barnes_and_noble_auth_blueprint,
        url_prefix="/barnes_and_noble_auth",
    )
    @app.get("/health/live")
    def health_live():
        return {"status": "ok", "component": 'barnes_and_noble'}

    return app
