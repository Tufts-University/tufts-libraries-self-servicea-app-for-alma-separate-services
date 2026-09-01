#!/usr/bin/env python3
"""Normalize component.js routes in an already-imported encapsulated app.

Run from the encapsulated repository root:

    python scripts/fix_component_routes.py

or pass the repository root explicitly:

    python scripts/fix_component_routes.py /var/www/html/self-service-app-encapsulated-v2

Any Flask view decorated with route('/component.js') is rewritten so component.js
is served from the directory containing that route module. This avoids assumptions
about current_app.root_path after components are moved into independent services.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path


def _is_component_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
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


def _ensure_path_import(lines: list[str]) -> list[str]:
    if any(line.strip() == "from pathlib import Path" for line in lines):
        return lines

    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("from __future__ import"):
            insert_at = i + 1
        elif insert_at:
            break

    lines.insert(insert_at, "from pathlib import Path\n")
    return lines


def patch_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"SKIP syntax error: {path}: {exc}")
        return False

    targets = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_component_route(node)
    ]
    if not targets:
        return False

    lines = source.splitlines(keepends=True)

    # Replace from bottom to top so line indexes stay valid.
    for node in sorted(targets, key=lambda n: n.lineno, reverse=True):
        if not node.body:
            continue
        body_start = node.body[0].lineno - 1
        body_end = node.end_lineno
        indent = " " * (node.col_offset + 4)
        replacement = [
            f'{indent}return send_from_directory(\n',
            f'{indent}    Path(__file__).resolve().parent,\n',
            f'{indent}    "component.js",\n',
            f'{indent}    mimetype="application/javascript",\n',
            f'{indent})\n',
        ]
        lines[body_start:body_end] = replacement

    lines = _ensure_path_import(lines)
    new_source = "".join(lines)

    if new_source == source:
        return False

    # Validate before writing.
    ast.parse(new_source)
    path.write_text(new_source, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Encapsulated repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    services = repo_root / "services"
    if not services.is_dir():
        raise SystemExit(f"Expected services directory: {services}")

    changed: list[Path] = []
    discovered: list[Path] = []

    for path in sorted(services.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "/component.js" not in text:
            continue
        discovered.append(path)
        if patch_file(path):
            changed.append(path)

    print(f"Found component.js routes in {len(discovered)} file(s).")
    for path in discovered:
        marker = "UPDATED" if path in changed else "already OK"
        print(f"  {marker:10} {path.relative_to(repo_root)}")

    print(f"Updated {len(changed)} file(s).")


if __name__ == "__main__":
    main()
