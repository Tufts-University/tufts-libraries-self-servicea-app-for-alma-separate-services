# Tufts Self-Service App — isolated service rewrite v2

This is the replacement for the earlier `tufts-self-service-isolated-rewrite` scaffold.

## What is different

There is **no `legacy/` directory** and no runtime import of the old monolithic `app` package. The original checkout is used once as migration input. `scripts/import_original_source.py` copies each component into `services/<component>/`, rewrites absolute imports, copies shared templates/static assets, and creates an independent Flask `service_app.py` + `wsgi.py` for every component.

After import, the runtime is self-contained:

```
Apache/nginx (unchanged)
        |
        v
127.0.0.1:5002  self-service-gateway
        |
        +-- 5010 main
        +-- 5011 barnes_and_noble
        +-- 5012 bib_2_holdings_541
        +-- 5013 p_and_e_rollup_match
        +-- 5014 gift_fund_bibliography
        +-- 5015 combine_analytics_subjects_areas
        +-- 5016 concurrent_checkouts
        +-- 5017 film_search
```

## Start again from the first generated version

Yes: remove the first generated units before installing this version. Do **not** remove your original working application yet.

```
./scripts/remove_first_generation.sh
```

Then remove whichever first-generation generated directory you created (for example `/opt/tufts-self-service-isolated` or `self-service-app-encapsulated`) only after checking the path. Keep the original Git checkout until this migration has been tested.

## Build the new self-contained source tree

Extract this zip to the directory from which you want the new application to run, for example:

```
/var/www/html/self-service-app-encapsulated
```

Then:

```
cd /var/www/html/self-service-app-encapsulated
./scripts/import_original_source.py /var/www/html/tufts-libraries-self-servicea-app-for-alma --force
./scripts/validate_structure.py
```

At that point `services/film_search/routes.py`, `services/bib_2_holdings_541/bib_2_holdings_541.py`, etc. are real files in the new application. They are not loaded from the old checkout.

Inspect for old absolute imports:

```
grep -R "from app\.\|import app\." services || true
```

That command should normally be empty. Any remaining result is a migration issue to fix before deployment.

## Install

```
sudoedit /etc/self-service-app/self-service.env   # if it already exists, or run install first to create it
./scripts/install.sh
sudoedit /etc/self-service-app/self-service.env
sudo systemctl start self-service.target
./scripts/status.sh
```

The installer generates systemd units using the **actual directory in which this repository lives**. Nothing is hard-coded to `/opt/tufts-self-service-isolated`.

## Apache/nginx

No change is expected if the existing proxy already points to `127.0.0.1:5002`.

## Important migration limitation

This rewrite changes package and process boundaries while preserving the existing business algorithms. Because the GitHub repository contains application-specific imports and runtime files, `import_original_source.py` performs deterministic import rewriting and the validation script catches Python syntax problems. You should test each component on stage before deleting the original application.
