#!/usr/bin/env python3
from pathlib import Path
import argparse

SERVICES = {
 "main":5010, "barnes-and-noble":5011, "bib-541":5012, "p-and-e":5013,
 "gift-fund":5014, "sql":5015, "concurrent-checkouts":5016, "film-search":5017,
}
MODULES = {
 "main":"services.main.wsgi:app", "barnes-and-noble":"services.barnes_and_noble.wsgi:app",
 "bib-541":"services.bib_2_holdings_541.wsgi:app", "p-and-e":"services.p_and_e_rollup_match.wsgi:app",
 "gift-fund":"services.gift_fund_bibliography.wsgi:app", "sql":"services.combine_analytics_subjects_areas.wsgi:app",
 "concurrent-checkouts":"services.concurrent_checkouts.wsgi:app", "film-search":"services.film_search.wsgi:app",
}

def unit(name, port, root, user, group):
    conf="film_search.conf.py" if name=="film-search" else "component.conf.py"
    return f'''[Unit]\nDescription=Self Service {name}\nAfter=network.target\nPartOf=self-service.target\n\n[Service]\nType=simple\nUser={user}\nGroup={group}\nWorkingDirectory={root}\nEnvironmentFile=-/etc/self-service-app/self-service.env\nExecStart={root}/.venv/bin/gunicorn -c {root}/gunicorn/{conf} --bind 127.0.0.1:{port} {MODULES[name]}\nRestart=on-failure\nRestartSec=5\nTimeoutStopSec=30\n\n[Install]\nWantedBy=self-service.target\n'''

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1])); ap.add_argument("--user", default="libraryapps"); ap.add_argument("--group", default="libraryapps"); ap.add_argument("--output", default=None); a=ap.parse_args()
    root=str(Path(a.root).resolve()); out=Path(a.output or Path(root)/"systemd/generated"); out.mkdir(parents=True, exist_ok=True)
    (out/"self-service.target").write_text('''[Unit]\nDescription=Tufts Libraries Self Service Application Stack\nWants=self-service-gateway.service self-service-main.service self-service-barnes-and-noble.service self-service-bib-541.service self-service-p-and-e.service self-service-gift-fund.service self-service-sql.service self-service-concurrent-checkouts.service self-service-film-search.service\nAfter=network.target\n\n[Install]\nWantedBy=multi-user.target\n''')
    gateway=f'''[Unit]\nDescription=Self Service Gateway\nAfter=network.target\nPartOf=self-service.target\n\n[Service]\nType=simple\nUser={a.user}\nGroup={a.group}\nWorkingDirectory={root}\nEnvironmentFile=-/etc/self-service-app/self-service.env\nExecStart={root}/.venv/bin/gunicorn -c {root}/gunicorn/gateway.conf.py --bind 127.0.0.1:5002 gateway_wsgi:app\nRestart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=self-service.target\n'''
    (out/"self-service-gateway.service").write_text(gateway)
    for n,p in SERVICES.items(): (out/f"self-service-{n}.service").write_text(unit(n,p,root,a.user,a.group))
    print(out)
if __name__=="__main__": main()
