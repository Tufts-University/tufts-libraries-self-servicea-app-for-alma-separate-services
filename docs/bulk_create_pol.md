# Bulk Create POL

Open `/bulk_create_pol/`. Submissions run on the RQ queue `bulk_create_pol`.
The service listens on port 5018. Run `scripts/render_systemd.py` during installation
to generate the web service and worker units; no running services are changed by this implementation.

Configure `REDIS_URL`, `SECRET_KEY`, `CREDENTIALS_BULK_CREATE_POL` (the same JSON
username/password format as the other services), SMTP settings, and `PUBLIC_BASE_URL`.
Configure `sandbox_acq_api_key` / `prod_acq_api_key` with acquisitions write and
bibliographic read permissions (plus configuration read permissions for managed sets).
The existing environment-specific bib keys are fallback keys.
Use `sandbox_alma_api_url` / `prod_alma_api_url` for regional `/almaws/v1` base URLs;
otherwise the base is derived from `bib_url`.

CSV/XLSX headers are case-insensitive and accept spaces or underscores. Required
per-row values are MMS ID, Library, Location, Vendor, Vendor Account, Fund, Price.
The form can supply defaults for everything except MMS ID and Price. Title is
optional and is retrieved from the bib API when absent. Format MMS IDs as text in
Excel; numeric cells may already have lost precision. Defaults: BOOK, Default item
policy, print reporting code, USD, PRINTED_BOOK_OT order type. Supply your configured
Alma codes, including the material-type code for Zines and the code representing
the Default item policy. Optional Interested User uses a primary identifier;
notification and hold flags are left at Alma defaults. Each order allocates its
entire price to one fund and creates one inventory copy in the supplied location.

Managed sets must contain bibliographic/physical titles. The form supplies the
shared fields, and all member pages are fetched. Per-item pricing is intentionally
a placeholder: records are logged as skipped without POSTing until prices can be
supplied. No zero-price substitute is used.

Completion email contains a download link or optional ZIP attachment. The ZIP
contains results.csv (MMS ID, title, price, HTTP status, POL number, error),
requests_and_responses.json, and summary.txt. Successful POSTs indicate creation;
Alma processes PO lines asynchronously, so they do not guarantee a final workflow
status. Individual failures do not stop later rows. POSTs are never retried
automatically, and connection failures may have an unknown creation outcome.
Check Alma before resubmitting. Saved results remain available even if delivery fails.

API references:
- https://developers.exlibrisgroup.com/alma/apis/docs/acq/UE9TVCAvYWxtYXdzL3YxL2FjcS9wby1saW5lcw==/
- https://developers.exlibrisgroup.com/alma/apis/docs/xsd/rest_po_line.xsd/?tags=POST

Verification: `python -m pytest tests/test_bulk_create_pol.py tests/test_gateway_routing.py -q`
uses mocked HTTP, queue, and email; it creates no live orders.
