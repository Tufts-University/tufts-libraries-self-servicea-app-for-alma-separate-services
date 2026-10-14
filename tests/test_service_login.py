"""Exercise real service routes and login handlers without Alma or job execution."""
import importlib
import sys
from types import ModuleType
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from gateway.routes import match_service


SERVICES = [
    ("bib_2_holdings_541", "auth_bib_2_holdings_541", "upload"),
    ("bulk_create_pol", "auth_bulk_create_pol", "upload"),
    ("gift_fund_bibliography", "auth_gift_fund_bibliography", "process"),
    ("barnes_and_noble", "barnes_and_noble_auth", "upload"),
]


@pytest.fixture(params=SERVICES, ids=[service[0] for service in SERVICES])
def service(request, monkeypatch, tmp_path):
    name, login_prefix, action = request.param
    monkeypatch.setenv("CREDENTIALS", '{"username":"tester","password":"test-password"}')
    monkeypatch.setenv("CREDENTIALS_BARNES_AND_NOBLE", '[]')
    for key in ("BIB2HOLDINGS541_UPLOAD_FOLDER", "BIB2HOLDINGS541_RESULTS_DIR",
                "BULK_CREATE_POL_UPLOAD_FOLDER", "BULK_CREATE_POL_RESULTS_DIR"):
        monkeypatch.setenv(key, str(tmp_path))
    # Only processors are stubbed; authentication, templates and app registration are real.
    processors = {
        "bib_2_holdings_541": "Bib2Holdings541",
        "gift_fund_bibliography": "GiftFundBibliography",
        "barnes_and_noble": "OverlapAnalysis",
    }
    if name in processors:
        module_name = f"services.{name}.{name}"
        stub = ModuleType(module_name)
        setattr(stub, processors[name], type(processors[name], (), {}))
        monkeypatch.setitem(sys.modules, module_name, stub)
    package = f"services.{name}"
    app = importlib.import_module(f"{package}.service_app").create_app()
    app.config.update(TESTING=True, SECRET_KEY="test-login-secret")
    routes = importlib.import_module(f"{package}.routes")
    auth_name = "auth_barnes_and_noble" if name == "barnes_and_noble" else login_prefix
    auth = importlib.import_module(f"{package}.{auth_name}")
    if name == "gift_fund_bibliography":
        monkeypatch.setattr(auth, "USERNAME", "tester")
        monkeypatch.setattr(auth, "PASSWORD", "test-password")
    else:
        monkeypatch.setattr(auth, "credentials_list", [{"username": "tester", "password": "test-password"}])
    return name, f"/{login_prefix}/login", f"/{name}/{action}", app.test_client(), routes


def test_browser_redirect_and_login(service):
    name, login, action, client, _ = service
    assert match_service(login).name == name
    response = client.get(f"/{name}/")
    assert response.status_code == 302
    assert response.headers["Location"] == login
    page = client.get(login)
    assert page.status_code == 200 and b'name="password"' in page.data
    response = client.post(login, data={"username": "tester", "password": "wrong"})
    assert response.status_code == 302 and response.headers["Location"] == login
    with client.session_transaction() as session:
        assert "user" not in session
    response = client.post(login, data={"username": "tester", "password": "test-password"})
    assert response.headers["Location"] == f"/{name}/"
    page = client.get(f"/{name}/")
    assert page.status_code == 200
    assert b'name="isComponent" value="false"' in page.data
    # Authenticated submission gets as far as form validation, with no token needed.
    assert client.post(action, data={"isComponent": "false"}).status_code == 400


def test_browser_submission_requires_login(service):
    _, login, action, client, _ = service
    for data in ({}, {"isComponent": "false"}):
        response = client.post(action, data=data)
        assert response.status_code == 302 and response.headers["Location"] == login


def test_component_requires_token_even_with_session(service, monkeypatch):
    name, _, action, client, routes = service
    with client.session_transaction() as session:
        session["user"] = "tester"
    assert client.get(f"/{name}/?isComponent=true").status_code == 401
    assert client.post(action, data={"isComponent": "true"}).status_code == 401
    monkeypatch.setattr(routes, "verify_token_or_reject", lambda: (True, "authorized"))
    assert client.post(action, data={"isComponent": "true"}).status_code == 400


def test_json_auth_failure_provides_login_path(service):
    name, login, action, client, _ = service
    if name not in ("bib_2_holdings_541", "bulk_create_pol"):
        return
    response = client.post(action, data={"isComponent": "false"}, headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.json["login_url"] == login


def test_gateway_follows_browser_login_redirect(service, monkeypatch):
    from gateway import app as gateway_app

    name, login, _, service_client, _ = service
    upstream_urls = []

    def upstream_request(method, url, **kwargs):
        upstream_urls.append(url)
        response = service_client.open(urlsplit(url).path, method=method)
        return SimpleNamespace(content=response.data, status_code=response.status_code,
                               headers=response.headers)

    monkeypatch.setattr(gateway_app.requests, "request", upstream_request)
    client = gateway_app.create_app().test_client()
    response = client.get(f"/{name}/", base_url="https://stage.example", follow_redirects=True)
    assert response.status_code == 200
    assert b'name="password"' in response.data
    port = match_service(login).port
    assert upstream_urls == [f"http://127.0.0.1:{port}/{name}/",
                             f"http://127.0.0.1:{port}{login}"]
