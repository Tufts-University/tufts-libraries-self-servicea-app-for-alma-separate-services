from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
    send_from_directory,
    jsonify,
    session
)
from services.gift_fund_bibliography.gift_fund_bibliography import GiftFundBibliography
from services.gift_fund_bibliography.auth_gift_fund_bibliography import verify_token_or_reject
from flask_cors import CORS, cross_origin
gift_fund_blueprint = Blueprint(
    "gift_fund_bibliography", __name__, url_prefix="/gift_fund_bibliography"
)

import os
from flask_cors import CORS, cross_origin
def is_component_request():
    values = (request.form.get("isComponent"), request.args.get("isComponent"))
    return any((value or "").strip().lower() in ("true", "1", "yes", "y", "on") for value in values)


def require_auth_or_reject():
    if is_component_request():
        ok, message = verify_token_or_reject()
        if not ok:
            return jsonify({"error": message}), 401
    elif "user" not in session:
        return redirect(url_for("blueprint_auth_gift_fund_bibliography.login"))
    return None


# Serve component.js
@gift_fund_blueprint.route('/component.js')
@cross_origin()
def serve_component():
    component_path = os.path.dirname(__file__)  # points to app/gift_fund_bibliography/
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')

# Serve component-template
@gift_fund_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("gift_fund_bibliography.html", is_component=True)



@gift_fund_blueprint.route("/", methods=["GET"])
def index():
    auth_response = require_auth_or_reject()
    if auth_response is not None:
        return auth_response
    return render_template("gift_fund_bibliography.html", is_component=is_component_request())


@gift_fund_blueprint.route("/process", methods=["POST"])
@cross_origin()
def process():
    if request.method == "OPTIONS":
        return ("", 204)
    auth_response = require_auth_or_reject()
    if auth_response is not None:
        return auth_response

    library = request.form.get("library")
    fiscal_year = request.form.get("fiscal_year")
    if not library or not fiscal_year:
        return "Library and Fiscal Year are required", 400

    gift_fund_bibliography = GiftFundBibliography(library, fiscal_year)
    zip_file = gift_fund_bibliography.process()

    return send_file(
        zip_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="gift_fund_bibliography.zip",
    )
