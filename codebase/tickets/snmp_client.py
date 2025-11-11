from __future__ import annotations

import asyncio
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from django.conf import settings

# Defer importing pysnmp to runtime to avoid noisy deprecation warnings
# (e.g., when an alternate package like pysnmp-lextudio is present) and
# to keep startup fast if SNMP is unused. _ensure_pysnmp() performs the
# actual import the first time SNMP is needed.
CommunityData = ContextData = ObjectIdentity = ObjectType = None  # type: ignore
SnmpEngine = UdpTransportTarget = getCmd = bulkCmd = None  # type: ignore
_PYSNMP_OK = False


def _ensure_pysnmp() -> bool:
    global CommunityData, ContextData, ObjectIdentity, ObjectType
    global SnmpEngine, UdpTransportTarget, getCmd, bulkCmd, _PYSNMP_OK
    if _PYSNMP_OK:
        return True
    try:  # pragma: no cover
        # Suppress noisy deprecation warning emitted by the transitional
        # 'pysnmp-lextudio' distribution. We prefer the official 'pysnmp'
        # package (requirements.txt already specifies it), but some envs may
        # still have the lextudio fork installed which emits a RuntimeWarning
        # on import. Filtering here avoids log spam without affecting errors.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*pysnmp-lextudio.*deprecated.*",
                category=RuntimeWarning,
            )
            from pysnmp.hlapi.asyncio import (
                CommunityData as _CommunityData,
                ContextData as _ContextData,
                ObjectIdentity as _ObjectIdentity,
                ObjectType as _ObjectType,
                SnmpEngine as _SnmpEngine,
                UdpTransportTarget as _UdpTransportTarget,
                getCmd as _getCmd,
                bulkCmd as _bulkCmd,
            )
        CommunityData = _CommunityData
        ContextData = _ContextData
        ObjectIdentity = _ObjectIdentity
        ObjectType = _ObjectType
        SnmpEngine = _SnmpEngine
        UdpTransportTarget = _UdpTransportTarget
        getCmd = _getCmd
        bulkCmd = _bulkCmd
        _PYSNMP_OK = True
    except Exception:
        _PYSNMP_OK = False
    return _PYSNMP_OK


class SnmpNotConfigured(RuntimeError):
    pass


class SnmpQueryError(RuntimeError):
    pass


# Column base OIDs (append hrDeviceIndex dynamically)
PRINTER_STATUS_BASE_OID = "1.3.6.1.2.1.25.3.5.1.1"
PRINTER_ERROR_STATE_BASE_OID = "1.3.6.1.2.1.25.3.5.1.2"
DEVICE_STATUS_BASE_OID = "1.3.6.1.2.1.25.3.2.1.5"
HR_DEVICE_TYPE_OID = "1.3.6.1.2.1.25.3.2.1.2"
HR_DEVICE_PRINTER_OID = "1.3.6.1.2.1.25.3.1.5"

# Alerts and console
ALERT_SEVERITY_OID = "1.3.6.1.2.1.43.18.1.1.2"
ALERT_DESCRIPTION_OID = "1.3.6.1.2.1.43.18.1.1.8"
CONSOLE_DISPLAY_TEXT_OID = "1.3.6.1.2.1.43.16.5.1.2"

# Supplies
SUPPLY_DESCRIPTION_OID = "1.3.6.1.2.1.43.11.1.1.6"
SUPPLY_MAX_CAPACITY_OID = "1.3.6.1.2.1.43.11.1.1.8"
SUPPLY_LEVEL_OID = "1.3.6.1.2.1.43.11.1.1.9"

PRINTER_STATUS_MAP = {1: "Other", 2: "Unknown", 3: "Idle", 4: "Printing", 5: "Warming Up"}
DEVICE_STATUS_MAP = {1: "Other", 2: "Unknown", 3: "Running", 4: "Warning", 5: "Testing", 6: "Down"}

ERROR_FLAG_MAP = [
    {"label": "Other error reported", "code": "other"},
    {"label": "Unknown error reported", "code": "unknown"},
    {"label": "Paper is empty", "code": "noPaper"},
    {"label": "Toner is empty", "code": "noToner"},
    {"label": "Door open", "code": "doorOpen"},
    {"label": "Paper jam", "code": "jammed"},
    {"label": "Offline", "code": "offline"},
    {"label": "Service requested", "code": "serviceRequested"},
]


@dataclass
class PrinterSnmpSnapshot:
    status_code: int
    status_label: str
    device_status_code: int | None
    device_status_label: str | None
    error_state_raw: str
    error_flags: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    supplies: List[Dict[str, Any]]
    attention: bool
    console_lines: List[str]


async def _get_single(
    engine: SnmpEngine,
    auth: CommunityData,
    target: UdpTransportTarget,
    context: ContextData,
    oid: str,
) -> Any:
    err_ind, err_stat, err_idx, var_binds = await getCmd(
        engine,
        auth,
        target,
        context,
        ObjectType(ObjectIdentity(oid)),
        lookupMib=False,
    )
    if err_ind:
        raise SnmpQueryError(str(err_ind))
    if err_stat:
        raise SnmpQueryError(f"{err_stat.prettyPrint()} at index {err_idx}")
    vb0 = var_binds[0]
    try:
        return vb0[1]
    except Exception:
        return getattr(vb0, "value", vb0)


async def _walk_column(
    engine: SnmpEngine,
    auth: CommunityData,
    target: UdpTransportTarget,
    context: ContextData,
    base_oid: str,
    *,
    max_rows: int = 16,
) -> Dict[Tuple[int, ...], Any]:
    prefix = f"{base_oid}."
    results: Dict[Tuple[int, ...], Any] = {}
    rows = 0
    iterator = bulkCmd(
        engine,
        auth,
        target,
        context,
        0,
        12,
        ObjectType(ObjectIdentity(base_oid)),
        lookupMib=False,
        lexicographicMode=False,
    )
    if hasattr(iterator, "__aiter__"):
        async for err_ind, err_stat, err_idx, var_binds in iterator:  # type: ignore
            if err_ind:
                raise SnmpQueryError(str(err_ind))
            if err_stat:
                raise SnmpQueryError(f"{err_stat.prettyPrint()} at index {err_idx}")
            stop = False
            for vb in var_binds:
                try:
                    oid_obj, val = vb[0], vb[1]
                except Exception:
                    oid_obj = getattr(vb, "objectIdentity", None) or getattr(vb, "oid", None) or vb
                    val = getattr(vb, "value", None)
                oid_str = oid_obj.prettyPrint() if hasattr(oid_obj, "prettyPrint") else str(oid_obj)
                if not oid_str.startswith(prefix):
                    stop = True
                    break
                index = tuple(int(x) for x in oid_str[len(prefix) :].split("."))
                results[index] = val
                rows += 1
                if rows >= max_rows:
                    stop = True
                    break
            if stop:
                break
    else:
        err_ind, err_stat, err_idx, var_binds = await iterator  # type: ignore
        if err_ind:
            raise SnmpQueryError(str(err_ind))
        if err_stat:
            raise SnmpQueryError(f"{err_stat.prettyPrint()} at index {err_idx}")
        for vb in var_binds:
            try:
                oid_obj, val = vb[0], vb[1]
            except Exception:
                oid_obj = getattr(vb, "objectIdentity", None) or getattr(vb, "oid", None) or vb
                val = getattr(vb, "value", None)
            oid_str = oid_obj.prettyPrint() if hasattr(oid_obj, "prettyPrint") else str(oid_obj)
            if not oid_str.startswith(prefix):
                break
            index = tuple(int(x) for x in oid_str[len(prefix) :].split("."))
            results[index] = val
    return results


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    if hasattr(value, "prettyPrint"):
        text = value.prettyPrint()
        if isinstance(text, str) and text.startswith("0x"):
            try:
                return int(text, 16)
            except ValueError:
                return None
        try:
            return int(text)
        except (TypeError, ValueError):
            return None
    if hasattr(value, "asNumbers"):
        total = 0
        try:
            for b in value.asNumbers():
                total = (total << 8) | int(b)
            return total
        except Exception:
            return None
    return None


def _decode_error_flags(value: Any) -> Tuple[str, List[Dict[str, str]]]:
    if value is None:
        return "", []
    if hasattr(value, "asNumbers"):
        raw = 0
        try:
            for b in value.asNumbers():
                raw = (raw << 8) | int(b)
        except Exception:
            raw = 0
    else:
        text = value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)
        try:
            raw = int(text, 16) if isinstance(text, str) and text.startswith("0x") else int(text)
        except Exception:
            raw = 0
    active: List[Dict[str, str]] = []
    for bit, entry in enumerate(ERROR_FLAG_MAP):
        if raw & (1 << bit):
            active.append({"label": entry["label"], "code": entry["code"]})
    return hex(raw), active


async def _collect_alerts(
    engine: SnmpEngine,
    auth: CommunityData,
    target: UdpTransportTarget,
    context: ContextData,
) -> List[Dict[str, Any]]:
    severities = await _walk_column(engine, auth, target, context, ALERT_SEVERITY_OID, max_rows=20)
    descriptions = await _walk_column(engine, auth, target, context, ALERT_DESCRIPTION_OID, max_rows=20)
    alerts: List[Dict[str, Any]] = []
    for index, desc_val in descriptions.items():
        description = desc_val.prettyPrint().strip()
        if not description:
            continue
        sev_val = severities.get(index)
        sev_code = int(sev_val) if sev_val is not None else 0
        sev_label = {1: "Other", 2: "Unknown", 3: "Warning", 4: "Critical"}.get(sev_code, "Unknown")
        alerts.append({"severity_code": sev_code, "severity": sev_label, "description": description, "index": index})
    alerts.sort(key=lambda a: a["severity_code"], reverse=True)
    return alerts[:10]


async def _collect_supplies(
    engine: SnmpEngine,
    auth: CommunityData,
    target: UdpTransportTarget,
    context: ContextData,
) -> List[Dict[str, Any]]:
    descriptions = await _walk_column(engine, auth, target, context, SUPPLY_DESCRIPTION_OID, max_rows=20)
    max_caps = await _walk_column(engine, auth, target, context, SUPPLY_MAX_CAPACITY_OID, max_rows=20)
    levels = await _walk_column(engine, auth, target, context, SUPPLY_LEVEL_OID, max_rows=20)
    supplies: List[Dict[str, Any]] = []
    for index, level_val in levels.items():
        level = _safe_int(level_val)
        if level is None:
            continue
        max_cap_val = _safe_int(max_caps.get(index))
        percent: int | None = None
        if (max_cap_val and max_cap_val > 0) and (level is not None) and (level >= 0):
            percent = max(0, min(100, int(round((level / max_cap_val) * 100))))
        desc_val = descriptions.get(index)
        desc_text = desc_val.prettyPrint().strip() if desc_val else ""
        supplies.append(
            {
                "description": desc_text or f"Supply {index[-1]}",
                "level": level,
                "max_capacity": max_cap_val,
                "percent": percent,
            }
        )
    supplies.sort(key=lambda s: s["description"])
    return supplies[:10]


async def _collect_console(
    engine: SnmpEngine,
    auth: CommunityData,
    target: UdpTransportTarget,
    context: ContextData,
) -> List[str]:
    rows = await _walk_column(engine, auth, target, context, CONSOLE_DISPLAY_TEXT_OID, max_rows=20)
    if not rows:
        return []
    items: List[str] = []
    for key in sorted(rows.keys()):
        val = rows.get(key)
        text = val.prettyPrint().strip() if hasattr(val, "prettyPrint") else str(val).strip()
        if text:
            items.append(text)
    seen: set[str] = set()
    unique: List[str] = []
    for line in items:
        if line in seen:
            continue
        seen.add(line)
        unique.append(line)
    return unique[:10]


async def _resolve_printer_index(
    engine: SnmpEngine,
    auth: CommunityData,
    target: UdpTransportTarget,
    context: ContextData,
) -> int | None:
    try:
        status_rows = await _walk_column(engine, auth, target, context, PRINTER_STATUS_BASE_OID, max_rows=8)
        if status_rows:
            keys = list(status_rows.keys())
            keys.sort()
            k = keys[0]
            return int(k[0] if isinstance(k, tuple) and k else k)
    except Exception:
        pass
    try:
        type_rows = await _walk_column(engine, auth, target, context, HR_DEVICE_TYPE_OID, max_rows=32)
        candidates: List[int] = []
        for key, val in type_rows.items():
            text = val.prettyPrint() if hasattr(val, 'prettyPrint') else str(val)
            if HR_DEVICE_PRINTER_OID in text:
                try:
                    candidates.append(int(key[0] if isinstance(key, tuple) and key else key))
                except Exception:
                    continue
        if candidates:
            candidates.sort()
            return candidates[0]
    except Exception:
        pass
    return None


async def _poll_printer(
    ip: str,
    community: str,
    *,
    timeout: float,
    retries: int,
    mpModel: int = 1,
) -> PrinterSnmpSnapshot:
    engine = SnmpEngine()
    try:
        target = await UdpTransportTarget.create((ip, 161), timeout=timeout, retries=retries)  # type: ignore[attr-defined]
    except AttributeError:
        target = UdpTransportTarget((ip, 161), timeout=timeout, retries=retries)
    auth = CommunityData(community, mpModel=mpModel)
    context = ContextData()
    idx = await _resolve_printer_index(engine, auth, target, context) or 1
    try:
        status_val = await _get_single(engine, auth, target, context, f"{PRINTER_STATUS_BASE_OID}.{idx}")
        error_val = await _get_single(engine, auth, target, context, f"{PRINTER_ERROR_STATE_BASE_OID}.{idx}")
        device_status_val = await _get_single(engine, auth, target, context, f"{DEVICE_STATUS_BASE_OID}.{idx}")
        alerts = await _collect_alerts(engine, auth, target, context)
        supplies = await _collect_supplies(engine, auth, target, context)
        console_lines = await _collect_console(engine, auth, target, context)
    finally:
        engine.transportDispatcher.closeDispatcher()

    status_code = _safe_int(status_val) or 0
    status_label = PRINTER_STATUS_MAP.get(status_code, "Unknown")
    device_status_code = _safe_int(device_status_val)
    device_status_label = DEVICE_STATUS_MAP.get(device_status_code, "") if device_status_code is not None else ""
    error_state_raw, error_msgs = _decode_error_flags(error_val)
    attention = bool(error_msgs) or any(a.get("severity_code", 0) >= 3 for a in alerts)

    return PrinterSnmpSnapshot(
        status_code=status_code,
        status_label=status_label,
        device_status_code=device_status_code,
        device_status_label=device_status_label,
        error_state_raw=error_state_raw,
        error_flags=error_msgs,
        alerts=alerts,
        supplies=supplies,
        attention=attention,
        console_lines=console_lines,
    )


def fetch_printer_status(printer) -> dict:
    if not _ensure_pysnmp():
        raise SnmpNotConfigured("pysnmp is not installed or failed to import. Install pysnmp to enable SNMP polling.")
    ip = (printer.ip_address or "").strip()
    if not ip:
        raise SnmpNotConfigured("Printer does not have an IP address configured.")

    community = getattr(settings, "SNMP_COMMUNITY", "public")
    timeout = float(getattr(settings, "SNMP_TIMEOUT", 3))
    retries = int(getattr(settings, "SNMP_RETRIES", 1))

    async def _runner_with_fallback():
        # Try SNMPv2c first (mpModel=1), then fall back to SNMPv1 (mpModel=0)
        try:
            return await _poll_printer(ip, community, timeout=timeout, retries=retries, mpModel=1)
        except SnmpQueryError as e_v2:
            try:
                return await _poll_printer(ip, community, timeout=timeout, retries=retries, mpModel=0)
            except Exception as e_v1:
                raise SnmpQueryError(f"v2c failed: {e_v2}; v1 failed: {e_v1}")

    snapshot = asyncio.run(_runner_with_fallback())

    alerts: List[Dict[str, Any]] = [
        {"severity": a["severity"], "severity_code": a["severity_code"], "description": a["description"], "index": a["index"]}
        for a in snapshot.alerts
    ]
    if snapshot.console_lines:
        for i, line in enumerate(snapshot.console_lines, start=1):
            alerts.append({
                "severity": "Panel",
                "severity_code": 2,
                "description": line,
                "index": (i,),
            })

    supplies: List[Dict[str, Any]] = [
        {
            "description": s["description"],
            "level": s["level"],
            "max_capacity": s["max_capacity"],
            "percent": s["percent"],
        }
        for s in snapshot.supplies
    ]

    return {
        "status_code": snapshot.status_code,
        "status_label": snapshot.status_label,
        "device_status_code": snapshot.device_status_code,
        "device_status_label": snapshot.device_status_label or "",
        "error_state_raw": snapshot.error_state_raw,
        "error_flags": [dict(flag) for flag in snapshot.error_flags],
        "alerts": alerts,
        "supplies": supplies,
        "attention": snapshot.attention,
    }
