import os
from flask import Flask
from flask_cors import CORS
from . import film_search_blueprint


def create_app():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "shared", "templates"),
        static_folder=os.path.join(root, "shared", "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
    CORS(app, resources={r"/*": {"origins": os.environ.get("CORS_ORIGINS", "https://tufts.campusgenai.org").split(",")}})
    app.register_blueprint(film_search_blueprint, url_prefix='/film_search')

    @app.get("/health/live")
    def health_live():
        return {"status": "ok", "component": 'film_search'}

    return app
