# Printer system

## Repository layout

- `printer_system/` – Django project (settings, urls, wsgi/asgi)
- `tickets/` – Main Django app (models, views, templates, static)
- `data/` – Local data artifacts (SQLite DB and CSVs)
  - SQLite path: `data/db.sqlite3`
- `scripts/` – Utility scripts for CSV cleanup and SNMP debugging
  - Run from repo root, e.g.: `python scripts/clean_printer_csv.py`

## Daily issue summary emails

The application automatically sends one summary per 24-hour window the next time any web request is processed. Ensure the site receives at least one request a day or run the manual command below.

Superusers can mark staff to receive the summary via the Users admin page (toggle 'Receive daily issue summary').

Set the `ISSUE_SUMMARY_RECIPIENT` environment variable (or leave blank to fall back to `EMAIL_TO`/`sklarz@berea.edu`).
Run the management command once a day (for example via Task Scheduler or cron):

```
python manage.py send_issue_summary
```

Optional flags:
- `--lookback-hours N` to limit issues to the last `N` hours.
- `--include-closed` to include resolved issues in the report.

The email lists each issue with the printer identifier, current status, and how long it has been open.

## Deployment (Windows Server)

This project runs as a Django site. On Windows, the simplest production setup is a Python virtual environment with the `waitress` server, optionally installed as a Windows Service.

- Prerequisites
  - Python 3.11 installed and on PATH
  - Clone this repository to a stable path (for example `C:\Services\printer-system`)

- Configure environment
  - Create `.env` (or edit the existing one) and set at least:
    - `DEBUG=false`
    - `SECRET_KEY=<long-random-string>`
    - `ALLOWED_HOSTS=<server-name-or-ip>` (comma-separated for multiple)
    - Email: `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `EMAIL_TO`
    - SNMP: `SNMP_COMMUNITY`, `SNMP_TIMEOUT`, `SNMP_RETRIES`, `SNMP_POLL_INTERVAL_SECONDS`

- Create virtual environment and install requirements
  - `py -3.11 -m venv .venv`
  - `.venv\Scripts\Activate.ps1`
  - `python -m pip install --upgrade pip`
  - `pip install -r requirements.txt`

- Initialize database (SQLite by default at `data/db.sqlite3`)
  - `python manage.py migrate`
  - `python manage.py createsuperuser`

- Run the app (test)
  - `waitress-serve --listen=0.0.0.0:8000 printer_system.wsgi:application`
  - Visit `http://<server>:8000/admin/`

- Optional: Serve static files directly (Whitenoise)
  - Add `'whitenoise.middleware.WhiteNoiseMiddleware'` near the top of `MIDDLEWARE` in `printer_system/settings.py`.
  - Add `STATIC_ROOT = BASE_DIR / 'staticfiles'`.
  - Run once: `python manage.py collectstatic`.

- Optional: Run as a Windows Service (NSSM)
  - Install NSSM: https://nssm.cc/download
  - `nssm install printer-system`
    - Application: `C:\path\to\repo\.venv\Scripts\waitress-serve.exe`
    - Arguments: `--listen=0.0.0.0:8000 printer_system.wsgi:application`
    - Startup directory: `C:\path\to\repo`
    - Environment (optional): `DJANGO_SETTINGS_MODULE=printer_system.settings`, `PYTHONUNBUFFERED=1`
  - Start: `nssm start printer-system`

- Backups
  - SQLite: stop the service (or quiesce writes) and copy `data/db.sqlite3`.
  - Portable export: `python manage.py dumpdata --natural-foreign --indent 2 > data/backup.json`

Notes
- For heavier concurrency or multiple writers, consider PostgreSQL; update `DATABASES` in settings and run `migrate`.
- Run `python manage.py check --deploy` for production recommendations.
\n## Live printer status (SNMP)\n\n- Portal and manager views show the current device state, alert feed, and supply readings.\n- Devices auto-refresh every 5 minutes (SNMP_POLL_INTERVAL_SECONDS) and expose a manual refresh button for immediate re-queries.\n- Only the latest snapshot is stored per printer (	ickets_printerstatus), keeping historical noise out of the database.\n- Admin and manager dashboards surface printers that require attention or have failed SNMP checks.\n\n### Configuration\n- SNMP_COMMUNITY (default public): v2c community string used for each printer.\n- SNMP_TIMEOUT (seconds, default 3): per-request socket timeout.\n- SNMP_RETRIES (default 1): retry attempts before marking the device offline.\n- SNMP_POLL_INTERVAL_SECONDS (default 300): cache window before another automatic poll is attempted.\n\n### Monitored OIDs\n- 1.3.6.1.2.1.25.3.5.1.1.1 (hrPrinterStatus) - overall printer state (idle, printing, warming up).\n- 1.3.6.1.2.1.25.3.5.1.2.1 (hrPrinterDetectedErrorState) - bit flags for jams, door open, toner empty, etc.\n- 1.3.6.1.2.1.25.3.2.1.5.1 (hrDeviceStatus) - base hardware status.\n- 1.3.6.1.2.1.43.18.1.1.2 (prtAlertSeverityLevel) - severity for current alerts.\n- 1.3.6.1.2.1.43.18.1.1.8 (prtAlertDescription) - human-readable alert context.\n- 1.3.6.1.2.1.43.11.1.1.6 (prtMarkerSuppliesDescription) - consumable name.\n- 1.3.6.1.2.1.43.11.1.1.8 (prtMarkerSuppliesMaxCapacity) - supply max capacity.\n- 1.3.6.1.2.1.43.11.1.1.9 (prtMarkerSuppliesLevel) - current supply level for percentage calculation.\n
