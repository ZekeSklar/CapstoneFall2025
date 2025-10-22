from __future__ import annotations

from typing import Iterable

from django.conf import settings
from django.utils import timezone

from .models import Printer, PrinterStatus
from .snmp_client import SnmpNotConfigured, SnmpQueryError, fetch_printer_status

POLL_INTERVAL_SECONDS = int(getattr(settings, 'SNMP_POLL_INTERVAL_SECONDS', 300))


def ensure_latest_status(printer: Printer, *, force: bool = False) -> PrinterStatus:
    """Return the latest SNMP status for a printer, refreshing if needed."""
    status, _ = PrinterStatus.objects.get_or_create(printer=printer)

    if not force and status.fetched_at:
        age = timezone.now() - status.fetched_at
        if age.total_seconds() < POLL_INTERVAL_SECONDS:
            return status

    try:
        snapshot = fetch_printer_status(printer)
    except SnmpNotConfigured as exc:
        _apply_failure(status, message=str(exc), attention=False)
    except SnmpQueryError as exc:
        _apply_failure(status, message=str(exc), attention=True)
    except Exception as exc:  # pragma: no cover
        _apply_failure(status, message=f"SNMP error: {exc}", attention=True)
    else:
        _apply_snapshot(status, snapshot)

    status.fetched_at = timezone.now()
    status.save()
    return status



def build_status_payload(printer: Printer, status: PrinterStatus | None) -> dict:
    if status:
        base_status = status.as_dict()
    else:
        base_status = {
            'printer_id': printer.id,
            'status_code': 0,
            'status_label': 'Unknown',
            'device_status_code': None,
            'device_status_label': '',
            'error_state_raw': '',
            'error_flags': [],
            'alerts': [],
            'supplies': [],
            'attention': False,
            'snmp_ok': False,
            'snmp_message': 'No SNMP data available',
            'fetched_at': None,
            'updated_at': None,
        }

    if status and status.fetched_at:
        display_ts = timezone.localtime(status.fetched_at).strftime('%b %d, %Y %I:%M %p')
    elif status and status.updated_at:
        display_ts = timezone.localtime(status.updated_at).strftime('%b %d, %Y %I:%M %p')
    else:
        display_ts = ''

    base_status['display_timestamp'] = display_ts

    return {
        'printer': {
            'id': printer.id,
            'campus_label': printer.campus_label,
            'asset_tag': printer.asset_tag,
            'building': printer.building,
            'location_in_building': printer.location_in_building,
            'make': printer.make,
            'model': printer.model,
        },
        'status': base_status,
        'poll_interval_seconds': POLL_INTERVAL_SECONDS,
    }

def _apply_snapshot(status: PrinterStatus, data: dict) -> None:
    status.status_code = data.get('status_code', 0) or 0
    status.status_label = data.get('status_label', '')
    status.device_status_code = data.get('device_status_code')
    status.device_status_label = data.get('device_status_label', '')
    status.error_state_raw = data.get('error_state_raw', '')
    status.error_flags = data.get('error_flags', [])
    status.alerts = data.get('alerts', [])
    status.supplies = data.get('supplies', [])
    status.attention = bool(data.get('attention'))
    status.snmp_ok = True
    status.snmp_message = ''


def _apply_failure(status: PrinterStatus, *, message: str, attention: bool) -> None:
    status.snmp_ok = False
    status.snmp_message = message
    status.attention = attention
    if attention:
        status.status_label = status.status_label or 'Attention required'
    else:
        status.status_label = status.status_label or 'Unavailable'
    status.error_flags = status.error_flags or []
    status.alerts = status.alerts or []
    status.supplies = status.supplies or []


def attach_status_to_printers(printers: Iterable[Printer]) -> None:
    """Attach cached PrinterStatus instances to printer objects."""
    printer_list = list(printers)
    if not printer_list:
        return

    status_map = {
        ps.printer_id: ps
        for ps in PrinterStatus.objects.filter(printer__in=printer_list)
    }
    for printer in printer_list:
        printer.status_cached = status_map.get(printer.id)
