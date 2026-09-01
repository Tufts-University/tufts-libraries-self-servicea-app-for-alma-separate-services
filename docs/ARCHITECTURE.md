# Architecture

The gateway is the only process exposed on the historical upstream port 5002. It has no imports from any business service. Each component is a distinct Flask/Gunicorn process with a separate Python module graph and worker pool. A component crash therefore cannot crash the gateway or another component.

The source tree is also separated: component files live under `services/<component>`. Shared templates/static files live under `shared/`. Each service's `service_app.py` points Flask at those shared presentation assets while registering only that service's blueprint.
