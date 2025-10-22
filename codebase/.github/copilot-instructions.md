## Quick orientation for AI contributors

This repository is a small Django app that tracks campus printers, polls them via SNMP, and lets staff submit supply/issue tickets.

Keep the guidance below focused on patterns discoverable in the codebase so you (the agent) can make safe, local edits.

### Big picture
- Django project root: `manage.py`, settings in `printer_system/settings.py`, primary app `tickets/`.
- Data: printers are `tickets.Printer` with a one-to-one `PrinterStatus` snapshot (latest-only cache). Historical snapshots are intentionally not stored.
- SNMP polling: async SNMP collectors live in `tickets/snmp_client.py` (uses `pysnmp` if installed). The web code calls `tickets/printer_status.ensure_latest_status` which respects a cache window (`SNMP_POLL_INTERVAL_SECONDS`).
- Daily emails: middleware `tickets/middleware.py` triggers `tickets/summary.maybe_send_daily_issue_summary()` on incoming requests; a management command `tickets.management.commands.send_issue_summary` exists for cron/task-scheduler use.

### Key files to reference when making changes
- `tickets/models.py` — printer, groups, tickets, and `PrinterStatus` JSON shape (single latest snapshot).
- `tickets/snmp_client.py` — SNMP OIDs, decoding rules, `fetch_printer_status(printer)` (raises `SnmpNotConfigured` if pysnmp missing or printer IP missing).
- `tickets/printer_status.py` — caching policy (`POLL_INTERVAL_SECONDS`), `ensure_latest_status`, `build_status_payload`, and error handling.
- `tickets/summary.py` — how recipients are resolved and how the issue summary is rendered/sent.
- `tickets/views.py` — examples of `force` query flags, rate limiting (`ISSUE_RATE_LIMIT_MAX`), permission patterns (`_user_can_manage_printer`).

### Project-specific conventions and gotchas
- SNMP is optional: code checks for `pysnmp` import. If missing, functions raise `SnmpNotConfigured` — handle that when editing SNMP-related flows.
- Single latest snapshot: updates write to a OneToOne `PrinterStatus`; avoid adding historical snapshots unless you update `models.py` and migrations.
- Generic placeholder values (e.g. `'UNKNOWN-MACADDRESS'`, `'0.0.0.0'`) are treated specially in `Printer.clean()` — uniqueness is enforced only for non-generic values.
- Email backend defaults to console (`EMAIL_BACKEND`), so tests and local runs will print emails to stdout unless environment variables change (`printer_system/settings.py`).

### Common developer workflows (what to run)
- Run dev server: `python manage.py runserver` (uses settings in `printer_system/settings.py`).
- Send issue summary manually: `python manage.py send_issue_summary [--include-closed] [--lookback-hours N]` — this mirrors the middleware behavior and is useful for testing scheduled emails.
- Quick SNMP debug from shell:
  - Open Django shell: `python manage.py shell`
  - Example: `from tickets.models import Printer; p=Printer.objects.get(pk=1); from tickets.snmp_client import fetch_printer_status; fetch_printer_status(p)`
  - If `pysnmp` missing, `SnmpNotConfigured` will be raised.

### Integration and environment notes
- Default DB: SQLite at `db.sqlite3` (see `printer_system/settings.py`). Migrations exist in `tickets/migrations/`.
- SNMP config via settings/env: `SNMP_COMMUNITY`, `SNMP_TIMEOUT`, `SNMP_RETRIES`, `SNMP_POLL_INTERVAL_SECONDS`.
- Issue summary recipients resolved by `tickets/summary._resolve_recipients()` — it checks explicit argument, flagged users, `ISSUE_SUMMARY_RECIPIENT`, `EMAIL_TO`, then falls back to `sklarz@berea.edu`.

### Small, safe change checklist (what an AI should do first)
1. Run `python manage.py check` and `python manage.py migrate` locally before touching DB-affecting code.
2. When changing SNMP logic, guard against missing `pysnmp` (see `snmp_client.py` import guard) and test via the management command or shell.
3. If you edit model fields, update `tickets/migrations/` via `python manage.py makemigrations` and include the migration in the PR.

### Example patterns to copy
- Force-refresh pattern: `ensure_latest_status(printer, force=True)` (used by manager feeds and `?force` query flag).
- Rate-limiting pattern for issues: `_issue_rate_limit_reached` in `tickets/views.py` — use the same window (`ISSUE_RATE_LIMIT_WINDOW`) and max (`ISSUE_RATE_LIMIT_MAX`) when adding similar protections.

If anything here is unclear or you want the guidance expanded to include CI, dependency installs, or more examples, say which area to expand and I will iterate.
