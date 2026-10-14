# app/bulk_create_pol/auth_bulk_create_pol.py

from flask import Blueprint, request, redirect, url_for, render_template, session, flash
from functools import wraps
import jwt
import os
import json
from dotenv import load_dotenv


# âœ… Blueprint name MUST match all url_for() references:
#    url_for("auth_bulk_create_pol.login") etc.
bulk_create_pol_auth_blueprint = Blueprint("auth_bulk_create_pol", __name__)

load_dotenv()

credentials_list = json.loads(os.getenv("CREDENTIALS_BULK_CREATE_POL", "[]"))


def check_credentials(username, password):
    return any(
        c.get("username") == username and c.get("password") == password
        for c in credentials_list
    )


@bulk_create_pol_auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if check_credentials(username, password):
            session["user"] = username
            return redirect(url_for("bulk_create_pol.index"))

        flash("Invalid username or password", "error")
        return redirect(url_for("auth_bulk_create_pol.login"))

    return render_template("login.html")


@bulk_create_pol_auth_blueprint.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth_bulk_create_pol.login"))


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth_bulk_create_pol.login"))
        return f(*args, **kwargs)
    return decorated_function


def verify_token_or_reject():
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return False, "Missing or invalid Authorization header."

    token = auth_header.split(" ", 1)[1].strip()
    public_key_path = os.getenv("PUBLIC_KEY_PATH", "public.pem")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    public_key_path = os.path.join(BASE_DIR, public_key_path)
    try:
        with open(public_key_path, "rb") as key_file:
            public_key = key_file.read()
    except Exception as e:
        return False, "Server configuration error."

    try:
        header = jwt.get_unverified_header(token)

        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        return True, "authorized"

    except jwt.InvalidAlgorithmError as e:
        return False, f"Algorithm not supported: {e}"

    except jwt.InvalidSignatureError:
        return False, "Invalid signature."

    except jwt.ExpiredSignatureError:
        return False, "Token expired."

    except jwt.InvalidTokenError as e:
        return False, f"Invalid token: {str(e)}"

