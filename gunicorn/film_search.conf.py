# Intentionally small worker pool: browser/vendor failures cannot consume the rest of the app.
workers = 2
worker_class = "gthread"
threads = 1
timeout = 150
graceful_timeout = 20
max_requests = 100
max_requests_jitter = 20
accesslog = "-"
errorlog = "-"
capture_output = True
