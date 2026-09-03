import os
from pathlib import Path
from urllib.parse import urljoin

import requests
from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
)

from .routes import SERVICES, match_service

from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file  

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


ROOT = Path(__file__).resolve().parent.parent
SHARED_STATIC = ROOT / "shared" / "static"


def _upstream_headers():
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP
        and key.lower() != "host"
    }

    headers["X-Forwarded-Proto"] = request.headers.get(
        "X-Forwarded-Proto",
        request.scheme,
    )
    headers["X-Forwarded-Host"] = request.host
    headers["X-Forwarded-For"] = request.headers.get(
        "X-Forwarded-For",
        request.remote_addr or "",
    )

    return headers


def create_app():
    # The gateway owns /static explicitly below.
    app = Flask(
        __name__,
        static_folder=None,
    )

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")

        allowed_origins = {
            "https://libraries.tufts.edu",
            "https://tufts.campusgenai.org",
        }

        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization"
        )
        return response

    cors_origins = {
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS",
            "https://libraries.tufts.edu"
        ).split(",")
        if origin.strip()
    }


    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")

        if origin and origin in cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"

            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
            )

            requested_headers = request.headers.get(
                "Access-Control-Request-Headers"
            )

            if requested_headers:
                response.headers[
                    "Access-Control-Allow-Headers"
                ] = requested_headers
            else:
                response.headers[
                    "Access-Control-Allow-Headers"
                ] = (
                    "Content-Type, Authorization"
                )

        return response

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "change-me",
    )

    app.config["SERVICE_CONNECT_TIMEOUT"] = float(
        os.environ.get(
            "SERVICE_CONNECT_TIMEOUT",
            "3",
        )
    )

    app.config["SERVICE_READ_TIMEOUT"] = float(
        os.environ.get(
            "SERVICE_READ_TIMEOUT",
            "180",
        )
    )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health/live")
    def live():
        return {
            "status": "ok",
            "component": "gateway",
        }

    @app.get("/health/services")
    def health_services():
        details = {}
        healthy = 0

        for service in SERVICES:
            try:
                response = requests.get(
                    f"http://127.0.0.1:{service.port}/health/live",
                    timeout=(1, 2),
                )
                available = response.ok

            except requests.RequestException:
                available = False

            details[service.name] = {
                "available": available,
                "port": service.port,
            }

            healthy += int(available)

        return jsonify(
            {
                "status": (
                    "ok"
                    if healthy == len(SERVICES)
                    else "degraded"
                ),
                "available": healthy,
                "total": len(SERVICES),
                "services": details,
            }
        )

    # ------------------------------------------------------------------
    # Shared static assets
    #
    # These belong to the gateway rather than an individual component.
    # They are fetched cross-origin by components embedded at
    # https://libraries.tufts.edu.
    # ------------------------------------------------------------------

    @app.route(
        "/static/<path:filename>",
        methods=["GET", "HEAD", "OPTIONS"],
    )
    def shared_static(filename):
        if request.method == "OPTIONS":
            response = Response(status=204)

        else:
            response = send_from_directory(
                SHARED_STATIC,
                filename,
            )

        response.headers[
            "Access-Control-Allow-Origin"
        ] = "*"

        response.headers[
            "Access-Control-Allow-Methods"
        ] = "GET, HEAD, OPTIONS"

        response.headers[
            "Access-Control-Allow-Headers"
        ] = "Content-Type"

        return response

    # ------------------------------------------------------------------
    # Component proxy
    # ------------------------------------------------------------------

    @app.route(
        "/",
        defaults={"path": ""},
        methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
            "HEAD",
        ],
    )
    @app.route(
        "/<path:path>",
        methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
            "HEAD",
        ],
    )
    def proxy(path):
        full_path = "/" + path

        service = match_service(full_path)

        target = (
            f"http://127.0.0.1:"
            f"{service.port}"
            f"{full_path}"
        )

        if request.query_string:
            target += (
                "?"
                + request.query_string.decode("latin-1")
            )

        try:
            upstream = requests.request(
                method=request.method,
                url=target,
                headers=_upstream_headers(),
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=(
                    app.config[
                        "SERVICE_CONNECT_TIMEOUT"
                    ],
                    app.config[
                        "SERVICE_READ_TIMEOUT"
                    ],
                ),
            )

        except requests.Timeout:
            return jsonify(
                {
                    "error": "component_timeout",
                    "component": service.name,
                }
            ), 504

        except requests.RequestException:
            app.logger.exception(
                "Component unavailable: %s",
                service.name,
            )

            return jsonify(
                {
                    "error": "component_unavailable",
                    "component": service.name,
                }
            ), 503

        excluded = HOP_BY_HOP | {
            "content-length",
            "content-encoding",
        }

        headers = [
            (key, value)
            for key, value in upstream.headers.items()
            if key.lower() not in excluded
        ]

        return Response(
            upstream.content,
            status=upstream.status_code,
            headers=headers,
        )

    return app

