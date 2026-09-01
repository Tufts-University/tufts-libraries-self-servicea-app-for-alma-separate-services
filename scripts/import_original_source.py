#!/usr/bin/env python3
"""Transform the original monolithic app/ tree into independent service packages.

The original checkout is needed only while this script runs. After a successful import,
the new tree is self-contained and systemd never references the old checkout.
"""
from __future__ import annotations

import argparse
import ast
import shutil
from pathlib import Path

COMPONENTS = {
    "main": {
        "blueprints": [("main_blueprint", "")],
    },
    "barnes_and_noble": {
        "blueprints": [
            ("barnes_and_noble_blueprint", "/barnes_and_noble"),
            ("barnes_and_noble_auth_blueprint", "/barnes_and_noble_auth"),
        ],
    },
    "bib_2_holdings_541": {
        "blueprints": [
            ("blueprint_541", "/bib_2_holdings_541"),
            ("bib_2_holdings_541_auth_blueprint", "/auth_bib_2_holdings_541"),
        ],
    },
    "p_and_e_rollup_match": {
        "blueprints": [("p_and_e_blueprint", "/p_and_e")],
    },
    "gift_fund_bibliography": {
        "blueprints": [
            ("gift_fund_blueprint", "/gift_fund_bibliography"),
            (
                "blueprint_auth_gift_fund_bibliography",
                "/auth_gift_fund_bibliography",
            ),
        ],
    },
    "combine_analytics_subjects_areas": {
    "blueprints": [
        ("sql_blueprint", "/sql"),
    ],
},
    "concurrent_checkouts": {
        "blueprints": [("concurrent_checkouts_blueprint", "/concurrent_checkouts")],
    },
    "film_search": {
        "blueprints": [("film_search_blueprint", "/film_search")],
    },
}

TEXT_SUFFIXES = {
    ".py", ".js", ".html", ".jinja", ".jinja2", ".txt", ".sql", ".css", ".json", ".md"
}


def rewrite_text(path: Path):
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    for component in COMPONENTS:
        text = text.replace(f"from app.{component}", f"from services.{component}")
        text = text.replace(f"import app.{component}", f"import services.{component}")
        text = text.replace(f"app.{component}", f"services.{component}")

    text = text.replace(
        "from app.rollUpMultipleResourceMatch",
        "from services.p_and_e_rollup_match.rollUpMultipleResourceMatch",
    )
    text = text.replace(
        "from app.2ProcessOverlapAnalysis",
        "from services.p_and_e_rollup_match.2ProcessOverlapAnalysis",
    )
    path.write_text(text, encoding="utf-8")



def normalize_component_route(path: Path):
    """Serve component.js from the copied service package itself.

    The original monolith often used current_app.root_path plus the old app
    subdirectory. Once imported into services/<component>, that assumption is
    no longer valid. Normalize every Flask /component.js view after copying.
    """
    if path.suffix.lower() != ".py":
        return

    source = path.read_text(encoding="utf-8")
    if "/component.js" not in source:
        return

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    def is_component_route(node):
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute) or func.attr != "route":
                continue
            first = decorator.args[0]
            if isinstance(first, ast.Constant) and first.value == "/component.js":
                return True
        return False

    targets = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and is_component_route(node)
    ]
    if not targets:
        return

    lines = source.splitlines(keepends=True)
    for node in sorted(targets, key=lambda n: n.lineno, reverse=True):
        if not node.body:
            continue
        body_start = node.body[0].lineno - 1
        body_end = node.end_lineno
        indent = " " * (node.col_offset + 4)
        lines[body_start:body_end] = [
            f'{indent}return send_from_directory(\n',
            f'{indent}    Path(__file__).resolve().parent,\n',
            f'{indent}    "component.js",\n',
            f'{indent}    mimetype="application/javascript",\n',
            f'{indent})\n',
        ]

    if not any(line.strip() == "from pathlib import Path" for line in lines):
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("from __future__ import"):
                insert_at = i + 1
            elif insert_at:
                break
        lines.insert(insert_at, "from pathlib import Path\n")

    new_source = "".join(lines)
    ast.parse(new_source)
    path.write_text(new_source, encoding="utf-8")

def write_service_app(service_dir: Path, component: str, blueprints):
    blueprint_names = ", ".join(name for name, _prefix in blueprints)
    registrations = "\n".join(
        f"    app.register_blueprint({name}, url_prefix={prefix!r})"
        for name, prefix in blueprints
    )

    service_dir.joinpath("service_app.py").write_text(
        f'''import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from . import {blueprint_names}

ROOT = Path(__file__).resolve().parents[2]


def create_app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / "shared" / "templates"),
        static_folder=str(ROOT / "shared" / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )

    CORS(
        app,
        resources={{
            r"/*": {{
                "origins": os.environ.get(
                    "CORS_ORIGINS", "https://tufts.campusgenai.org"
                ).split(",")
            }}
        }},
    )

{registrations}

    @app.get("/health/live")
    def health_live():
        return {{"status": "ok", "component": {component!r}}}

    return app
''',
        encoding="utf-8",
    )
    service_dir.joinpath("wsgi.py").write_text(
        "from .service_app import create_app\napp = create_app()\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source_repo",
        type=Path,
        help="Original tufts-libraries-self-servicea-app-for-alma checkout",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="New encapsulated repository root",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = args.source_repo.resolve()
    target = args.target.resolve()
    old_app = source / "app"
    if not old_app.is_dir():
        raise SystemExit(f"Expected {old_app} to exist")

    services_root = target / "services"
    shared = target / "shared"
    services_root.mkdir(parents=True, exist_ok=True)
    shared.mkdir(parents=True, exist_ok=True)

    for name in ("templates", "static"):
        src = old_app / name
        dst = shared / name
        if src.exists():
            if dst.exists() and args.force:
                shutil.rmtree(dst)
            if dst.exists() and any(dst.iterdir()) and not args.force:
                raise SystemExit(f"{dst} is not empty; rerun with --force")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    pe_helpers = ["rollUpMultipleResourceMatch.py", "2ProcessOverlapAnalysis.py"]

    for component, meta in COMPONENTS.items():
        src = old_app / component
        dst = services_root / component
        if not src.is_dir():
            print(f"WARNING: component directory missing: {src}")
            continue
        if dst.exists():
            if not args.force:
                raise SystemExit(f"{dst} already exists; rerun with --force")
            shutil.rmtree(dst)
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".gpteng"),
        )
        if component == "p_and_e_rollup_match":
            for helper in pe_helpers:
                helper_src = old_app / helper
                if helper_src.exists():
                    shutil.copy2(helper_src, dst / helper)
        for file in dst.rglob("*"):
            if file.is_file():
                rewrite_text(file)
                normalize_component_route(file)
        write_service_app(dst, component, meta["blueprints"])

    if (source / "requirements.txt").exists():
        shutil.copy2(
            source / "requirements.txt",
            target / "docs" / "original-requirements.txt",
        )

    print("\nImport complete.")
    print(f"New services are under: {services_root}")
    print("The old checkout is no longer required at runtime after validation.")


if __name__ == "__main__":
    main()
