import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from services.bib_2_holdings_541 import blueprint_541
from services.bib_2_holdings_541.auth_bib_2_holdings_541 import (
    bib_2_holdings_541_auth_blueprint,
)


ROOT = Path(__file__).resolve().parents[2]
SHARED_TEMPLATES = ROOT / "shared" / "templates"
SHARED_STATIC = ROOT / "shared" / "static"


def create_app():
    app = Flask(
        __name__,
        template_folder=str(SHARED_TEMPLATES),
        static_folder=str(SHARED_STATIC),
    )

    app.secret_key = os.environ["SECRET_KEY"]

    CORS(app)

    app.register_blueprint(
        blueprint_541,
        url_prefix="/bib_2_holdings_541",
    )

    app.register_blueprint(
        bib_2_holdings_541_auth_blueprint,
        url_prefix="/auth_bib_2_holdings_541",
    )

    @app.get("/health/live")
    def health():
        return {
            "status": "ok",
            "component": "bib_2_holdings_541",
        }

    return app