from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
    jsonify, 
    session 
)

from werkzeug.utils import secure_filename
import os
from .barnes_and_noble import OverlapAnalysis
from .auth_barnes_and_noble import verify_token_or_reject
from flask_cors import CORS, cross_origin
from flask import current_app, send_from_directory
barnes_and_noble_blueprint = Blueprint("barnes_and_noble", __name__)
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parent
def is_component_request():
    values = (request.form.get("isComponent"), request.args.get("isComponent"))
    return any((value or "").strip().lower() in ("true", "1", "yes", "y", "on") for value in values)


def require_auth_or_reject():
    if is_component_request():
        ok, message = verify_token_or_reject()
        if not ok:
            return jsonify({"error": message}), 401
    elif "user" not in session:
        return redirect(url_for("barnes_and_noble_auth.login"))
    return None


# Serve component.js
@barnes_and_noble_blueprint.route("/component.js")
@cross_origin()
def serve_component():
    return send_from_directory(
        COMPONENT_DIR,
        "component.js",
        mimetype="application/javascript",
    )


# Serve component-template
@barnes_and_noble_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("barnes_and_noble.html", is_component=True)


@barnes_and_noble_blueprint.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])

def upload_file():
    if request.method == "OPTIONS":
        return ("", 204)
    auth_response = require_auth_or_reject()
    if auth_response is not None:
        return auth_response

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400
    # filename = secure_filename(file.filename)
    # file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    # file.save(file_path)
    analysis = OverlapAnalysis(file)
    output_path = analysis.process()
    return send_file(
        output_path,
        as_attachment=True,
        download_name="Updated_Barnes_and_Noble.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@barnes_and_noble_blueprint.route("/", methods=["GET"])
def index():
    auth_response = require_auth_or_reject()
    if auth_response is not None:
        return auth_response
    return render_template("barnes_and_noble.html", is_component=is_component_request())
