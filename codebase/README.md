# Printer system

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
\n## Live printer status (SNMP)\n\n- Portal and manager views show the current device state, alert feed, and supply readings.\n- Devices auto-refresh every 5 minutes (SNMP_POLL_INTERVAL_SECONDS) and expose a manual refresh button for immediate re-queries.\n- Only the latest snapshot is stored per printer (	ickets_printerstatus), keeping historical noise out of the database.\n- Admin and manager dashboards surface printers that require attention or have failed SNMP checks.\n\n### Configuration\n- SNMP_COMMUNITY (default public): v2c community string used for each printer.\n- SNMP_TIMEOUT (seconds, default 3): per-request socket timeout.\n- SNMP_RETRIES (default 1): retry attempts before marking the device offline.\n- SNMP_POLL_INTERVAL_SECONDS (default 300): cache window before another automatic poll is attempted.\n\n### Monitored OIDs\n- 1.3.6.1.2.1.25.3.5.1.1.1 (hrPrinterStatus) - overall printer state (idle, printing, warming up).\n- 1.3.6.1.2.1.25.3.5.1.2.1 (hrPrinterDetectedErrorState) - bit flags for jams, door open, toner empty, etc.\n- 1.3.6.1.2.1.25.3.2.1.5.1 (hrDeviceStatus) - base hardware status.\n- 1.3.6.1.2.1.43.18.1.1.2 (prtAlertSeverityLevel) - severity for current alerts.\n- 1.3.6.1.2.1.43.18.1.1.8 (prtAlertDescription) - human-readable alert context.\n- 1.3.6.1.2.1.43.11.1.1.6 (prtMarkerSuppliesDescription) - consumable name.\n- 1.3.6.1.2.1.43.11.1.1.8 (prtMarkerSuppliesMaxCapacity) - supply max capacity.\n- 1.3.6.1.2.1.43.11.1.1.9 (prtMarkerSuppliesLevel) - current supply level for percentage calculation.\n
