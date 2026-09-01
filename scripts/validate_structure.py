#!/usr/bin/env python3
from pathlib import Path
import ast, sys
root = Path(__file__).resolve().parents[1]
expected = ["main","barnes_and_noble","bib_2_holdings_541","p_and_e_rollup_match","gift_fund_bibliography","combine_analytics_subjects_areas","concurrent_checkouts","film_search"]
errors=[]
for name in expected:
    d=root/"services"/name
    if not d.is_dir(): errors.append(f"missing service: {name}")
    for f in ("__init__.py","service_app.py","wsgi.py"):
        if not (d/f).exists(): errors.append(f"missing {name}/{f}")
for p in list((root/"gateway").rglob("*.py"))+list((root/"services").rglob("*.py")):
    try: ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except Exception as e: errors.append(f"syntax: {p}: {e}")
if errors:
    print("VALIDATION FAILED")
    print("\n".join(f"- {e}" for e in errors))
    sys.exit(1)
print("Structure and Python syntax validation passed.")
