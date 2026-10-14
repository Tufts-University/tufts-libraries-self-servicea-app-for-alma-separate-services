# app/bulk_create_pol/routes.py

from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    current_app,
    render_template,
    send_from_directory,
    session,
    jsonify,
)
from werkzeug.utils import secure_filename
from flask_cors import cross_origin, CORS

import os
import uuid
from redis import Redis
from rq import Queue
from pathlib import Path


from .auth_bulk_create_pol import verify_token_or_reject
from .tasks import run_bulk_create_pol_job


blueprint_541 = Blueprint("bulk_create_pol", __name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_FOLDER = os.getenv("BULK_CREATE_POL_UPLOAD_FOLDER", "/tmp/bulk_create_pol_uploads")
RESULTS_DIR = os.getenv("BULK_CREATE_POL_RESULTS_DIR", "/tmp/bulk_create_pol_results")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def get_queue():
    redis_conn = Redis.from_url(REDIS_URL)
    return Queue("polBulkCreate", connection=redis_conn)


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("true", "1", "yes", "y", "on")


def is_component_request() -> bool:
    # Uploads will send isComponent in form-data; page loads should use querystring ?isComponent=true
    return _truthy(request.form.get("isComponent")) or _truthy(request.args.get("isComponent"))


def require_auth_or_reject():
    """
    Component -> JWT Authorization header
    Browser   -> Flask session
    """
    if is_component_request():
        ok, message = verify_token_or_reject()
        if not ok:
            return jsonify({"error": message}), 401
        return None

    if "user" not in session:
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        if wants_json:
            return jsonify({"error": "Not authenticated", "login_url": url_for("auth_bulk_create_pol.login")}), 401
        return redirect(url_for("auth_bulk_create_pol.login"))

    return None


# ----------------------------------------------------------------------
# Static assets for web component
# ----------------------------------------------------------------------
CORS(blueprint_541)
COMPONENT_DIR = Path(__file__).resolve().parent
@blueprint_541.route("/component.js")
def serve_component():

    component_path = os.path.join(os.path.dirname(__file__))  # correct package directory
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')


@blueprint_541.route("/component-template")
@cross_origin()
def serve_component_template():
    # component-template is meant to be embedded, so treat it as component mode
    return render_template("bulk_create_pol.html", is_component=True)


# ----------------------------------------------------------------------
# Upload -> enqueue RQ job
# ----------------------------------------------------------------------

@blueprint_541.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])
def upload_file():

    # CORS preflight must succeed without auth headers
    if request.method == "OPTIONS":
        return ("", 204)
    auth_response = require_auth_or_reject()
    if auth_response:
        return auth_response

    ingest_method = request.form.get("ingest_method", "spreadsheet")
    environment = request.form.get("environment", "sandbox")
    if ingest_method not in ("spreadsheet", "managed_set") or environment not in ("sandbox", "prod"):
        return jsonify({"error": "Invalid ingest method or environment"}), 400
    set_id = (request.form.get("set_id") or "").strip()
    if ingest_method == "managed_set" and not set_id.isdigit():
        return jsonify({"error": "A numeric managed set ID is required"}), 400
    fields = ("material_type", "library", "location", "item_policy", "vendor", "vendor_account",
              "fund", "interested_user", "reporting_code", "secondary_reporting_code", "currency", "type")
    form_data = {key: request.form.get(key, "").strip() for key in fields}
    if ingest_method == "managed_set":
        missing = [key for key in ("library", "location", "vendor", "vendor_account", "fund") if not form_data[key]]
        if missing:
            return jsonify({"error": "Required form fields: " + ", ".join(missing)}), 400

    email = (request.form.get("email") or "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    email_as_attachment = _truthy(request.form.get("email_as_attachment"))

    file = request.files.get("file")
    if ingest_method == "spreadsheet" and (not file or not file.filename):
        return jsonify({"error": "No file selected"}), 400

    job_id = str(uuid.uuid4())
    safe_name = secure_filename(file.filename) if file and file.filename else "input.csv"
    saved_path = None
    if ingest_method == "spreadsheet":
        if not safe_name.lower().endswith((".csv", ".xlsx")):
            return jsonify({"error": "Upload a CSV or XLSX spreadsheet"}), 400
        saved_path = os.path.join(UPLOAD_FOLDER, f"{job_id}__{safe_name}")
        file.save(saved_path)

    if saved_path and (not os.path.exists(saved_path) or os.path.getsize(saved_path) == 0):
        return jsonify({"error": f"Upload save failed: {saved_path}"}), 500

    q = get_queue()
    q.enqueue(
        run_bulk_create_pol_job,
        kwargs={
            "job_id": job_id,
            "input_path": saved_path,
            "email": email,
            "email_as_attachment": email_as_attachment,
            "environment": environment,
            "ingest_method": ingest_method,
            "form_data": form_data,
            "set_id": set_id,
            "filename": safe_name,
        },
        job_timeout=60 * 60,
        result_ttl=7 * 24 * 3600,
    )

    return jsonify({"status": "queued", "job_id": job_id})


# ----------------------------------------------------------------------
# Download results (browser session only)
# ----------------------------------------------------------------------

@blueprint_541.route("/results/<path:filename>", methods=["GET"])
def download_result(filename):
    if "user" not in session:
        return redirect(url_for("auth_bulk_create_pol.login"))
    return send_from_directory(RESULTS_DIR, filename, as_attachment=True)


# ----------------------------------------------------------------------
# Main UI
# ----------------------------------------------------------------------

@blueprint_541.route("/", methods=["GET"])
def index():
    # For a normal browser load, this uses session auth
    # For component loads, use ?isComponent=true (GET has no form-data)
    auth_response = require_auth_or_reject()
    if auth_response:
        return auth_response

    return render_template("bulk_create_pol.html", is_component=is_component_request())
