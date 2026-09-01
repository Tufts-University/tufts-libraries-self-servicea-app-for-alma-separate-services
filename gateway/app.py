import os
from urllib.parse import urljoin

import requests
from flask import Flask, Response, jsonify, request

from .routes import SERVICES, match_service

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def _upstream_headers():
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP and key.lower() != "host"
    }
    headers["X-Forwarded-Proto"] = request.headers.get("X-Forwarded-Proto", request.scheme)
    headers["X-Forwarded-Host"] = request.host
    headers["X-Forwarded-For"] = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    return headers


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
    app.config["SERVICE_CONNECT_TIMEOUT"] = float(os.environ.get("SERVICE_CONNECT_TIMEOUT", "3"))
    app.config["SERVICE_READ_TIMEOUT"] = float(os.environ.get("SERVICE_READ_TIMEOUT", "180"))

    @app.get("/health/live")
    def live():
        return {"status": "ok", "component": "gateway"}

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
            details[service.name] = {"available": available, "port": service.port}
            healthy += int(available)
        return jsonify({
            "status": "ok" if healthy == len(SERVICES) else "degraded",
            "available": healthy,
            "total": len(SERVICES),
            "services": details,
        })

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    @app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    def proxy(path):
        full_path = "/" + path
        service = match_service(full_path)
        target = f"http://127.0.0.1:{service.port}{full_path}"
        if request.query_string:
            target += "?" + request.query_string.decode("latin-1")
        try:
            upstream = requests.request(
                method=request.method,
                url=target,
                headers=_upstream_headers(),
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=(app.config["SERVICE_CONNECT_TIMEOUT"], app.config["SERVICE_READ_TIMEOUT"]),
            )
        except requests.Timeout:
            return jsonify({"error": "component_timeout", "component": service.name}), 504
        except requests.RequestException:
            app.logger.exception("Component unavailable: %s", service.name)
            return jsonify({"error": "component_unavailable", "component": service.name}), 503

        excluded = HOP_BY_HOP | {"content-length", "content-encoding"}
        headers = [(k, v) for k, v in upstream.headers.items() if k.lower() not in excluded]
        return Response(upstream.content, status=upstream.status_code, headers=headers)

    return app
