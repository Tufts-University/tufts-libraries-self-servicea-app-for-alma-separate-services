import os
from flask import Flask
from flask_cors import CORS
from . import blueprint_541
from . import (
    bib_2_holdings_541_auth_blueprint,
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
    app.register_blueprint(blueprint_541, url_prefix='/bib_2_holdings_541')
    app.register_blueprint(
        bib_2_holdings_541_auth_blueprint,
        url_prefix="/auth_bib_2_holdings_541",
    )
    @app.get("/health/live")
    def health_live():
        return {"status": "ok", "component": 'bib_2_holdings_541'}

    return app
