import os
from flask import Flask
from flask_cors import CORS
from . import gift_fund_blueprint
from . import (
    blueprint_auth_gift_fund_bibliography,
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
    app.register_blueprint(gift_fund_blueprint, url_prefix='/gift_fund_bibliography')
    app.register_blueprint(
        blueprint_auth_gift_fund_bibliography,
        url_prefix="/auth_gift_fund_bibliography",
    )
    @app.get("/health/live")
    def health_live():
        return {"status": "ok", "component": 'gift_fund_bibliography'}

    return app
