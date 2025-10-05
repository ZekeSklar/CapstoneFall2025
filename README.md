# Berea College Printing Services — Inventory, Tickets, and Device Status

Admin portal for Printing Services to manage printer inventory, track requests/issues, and view live device status via SNMP. Public QR pages let users submit supply requests and report issues that route to Printing Services.

## Vision
Provide a single pane for staff to see inventory, track tickets, and view health across campus printers. Show actionable device alerts and supplies status to reduce downtime and improve response time.

## Scope
- In scope: printer inventory, request/issue tickets, per‑printer live SNMP status (5‑minute cadence + manual refresh), admin index alert summary, daily issue summary email, per‑printer rate limiting (max 3 issues/hour), QR request portal.
- Out of scope: enterprise reporting/BI, network device provisioning, authentication beyond Django admin, historical SNMP trending (current version shows latest only).

## Current Status (Oct 2025)
- Admin → Printers: Live Device Status panel with Refresh; SNMP v2c with v1 fallback; shows status, error flags, alerts, supplies when exposed by device.
- Admin index: “Printer Device Alerts” for attention/SNMP faults.
- Manager dashboard: per‑printer status, auto‑refresh every 5 minutes, manual refresh for one/all.
- Tickets: issue report rate‑limited per printer (3/hour) but users still receive “thank you.”
- Daily email summary: once per interval to configured recipients; superusers can opt‑in via admin toggle.

## Setup
- Requirements: Python 3.11, SQLite (dev), access to SMTP for email, SNMP community for printers.
- Environment (`codebase/.env`):
  - EMAIL_BACKEND/EMAIL_HOST/… for mail delivery
  - SNMP_COMMUNITY, SNMP_TIMEOUT, SNMP_RETRIES, SNMP_POLL_INTERVAL_SECONDS
- Run from `codebase/`:
  1) `.venv\Scripts\python.exe manage.py migrate`
  2) `.venv\Scripts\python.exe manage.py runserver`

## Tech Stack
- Django 5.2, Python 3.11, SQLite
- django-import-export
- pysnmp (asyncio) for SNMP polling
- python-dotenv for config

## Key Features
- Inventory management for printers, comments, groups
- Ticketing for supplies/issues with email notifications
- Live SNMP device status (status/device status/error flags/alerts/console/supplies when available)
- Daily issue summary with per‑user subscription toggle
- Admin and manager dashboards with cache‑safe JSON feeds and client cache‑busting

## Documents
- Concept: `R01.concept.proposal.md`
- Vision & Scope: `R02.vision.scope.md`
- Requirements: `R03.requirements.md`
- Design: `R04.design.md` and `R05.design2.md`
- Prototype build notes: `R07.prototype.build.md`

## Author
- Zechariah Sklar — https://github.com/ZekeSklar

## Acknowledgments
- Course scaffolding adapted from CSC 493 materials
