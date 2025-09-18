import csv
import re
from typing import Tuple, Optional


import os

BASE_DIR = os.path.dirname(__file__)
INPUT = os.path.join(BASE_DIR, "printer_inventory_condensed_for_import_FINAL.csv")
OUTPUT = os.path.join(BASE_DIR, "printer_inventory_condensed_for_import_FIXED.csv")
REPORT = os.path.join(BASE_DIR, "printer_inventory_ip_report.txt")


def is_valid_ipv4(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        for p in parts:
            if p == "":
                return False
            if not p.isdigit():
                return False
            v = int(p)
            if v < 0 or v > 255:
                return False
            # Disallow leading plus/minus or extraneous zeros with non-digit chars already filtered
        return True
    except Exception:
        return False


def simple_normalize_ip(raw: str) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""

    # Remove enclosing quotes and common trailing punctuation
    s = s.strip(" \t\r\n,;\"")

    # Drop common suffixes like CIDR or port if present
    # e.g., 10.1.2.3/24 or 10.1.2.3:9100
    if "/" in s:
        s = s.split("/", 1)[0]
    if ":" in s:
        # If looks like port after colon, take left side
        left, right = s.split(":", 1)
        if right.isdigit():
            s = left

    # Replace common letter/digit confusions (only if safe characters)
    # O/o -> 0, l/I -> 1
    trans = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"})
    s = s.translate(trans)

    # Remove stray spaces around dots (e.g., '10 . 1 .2 .3')
    s = re.sub(r"\s*\.\s*", ".", s)

    # Collapse duplicate dots at ends (e.g., '10.1.1.5.')
    s = s.strip('.')
    # Collapse multiple consecutive dots to a single dot ONLY if it keeps 4 parts
    while ".." in s:
        trial = s.replace("..", ".")
        parts = trial.split(".")
        if len(parts) <= 4:
            s = trial
        else:
            # More than 4 parts means collapsing may not help; break to avoid overfitting
            break

    return s


def try_fix_ip(raw: str) -> Tuple[str, Optional[str]]:
    """
    Returns (fixed_value, reason_or_None).
    If value is unchanged and valid, reason is None.
    If value changed and is valid, reason is description of fix applied.
    If cannot make valid, returns original normalized value and reason explaining failure.
    """
    original = str(raw or "").strip()
    normalized = simple_normalize_ip(original)

    if not normalized:
        # Empty remains empty; treat as unfixable only if original had something non-empty
        if original:
            return original, "Unclear IP after cleanup"
        return normalized, None

    if is_valid_ipv4(normalized):
        if normalized == original:
            return normalized, None
        return normalized, "Normalized formatting"

    # If still invalid, attempt a conservative cleanup: remove any non [0-9.] chars
    stripped = re.sub(r"[^0-9.]", "", normalized)
    stripped = stripped.strip('.')
    # Re-collapse multiple dots
    while ".." in stripped:
        stripped = stripped.replace("..", ".")

    if is_valid_ipv4(stripped):
        return stripped, "Removed non-numeric characters"

    # If there are fewer than 4 parts, do not guess missing octets
    parts = stripped.split(".") if stripped else []
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        # Check if any octet is out of range; we won't guess corrections
        return original, "Octet out of range; manual review"

    # As a final simple rule, try extracting an IPv4-like token from the original/raw text
    ip_candidates = re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", original)
    if ip_candidates:
        # Prefer the first candidate that validates
        for cand in ip_candidates:
            if is_valid_ipv4(cand):
                return cand, "Extracted IPv4 from surrounding text"

    return original, "Unfixable with simple rules"


def main() -> None:
    fixed = 0
    unchanged_valid = 0
    empty = 0
    unfixable = 0
    changes = []
    problems = []

    with open(INPUT, newline='', encoding='utf-8') as infile, \
         open(OUTPUT, 'w', newline='', encoding='utf-8') as outfile, \
         open(REPORT, 'w', encoding='utf-8') as rep:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames or []
        if 'ip_address' not in fieldnames:
            raise SystemExit('ip_address column not found in input CSV')
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        rownum = 1  # header is line 1; data starts at 2
        for row in reader:
            rownum += 1
            ip_raw = row.get('ip_address', '')
            fixed_ip, reason = try_fix_ip(ip_raw)

            id_fields = {
                'line': rownum,
                'campus_label': row.get('campus_label', ''),
                'asset_tag': row.get('asset_tag', ''),
                'serial_number': row.get('serial_number', ''),
            }

            if fixed_ip != (ip_raw or "").strip():
                if reason and is_valid_ipv4(fixed_ip):
                    fixed += 1
                    changes.append((id_fields, ip_raw, fixed_ip, reason))
                elif reason and not is_valid_ipv4(fixed_ip):
                    # Didn't end up valid; leave original value unchanged in output
                    unfixable += 1
                    problems.append((id_fields, ip_raw, reason))
                    fixed_ip = ip_raw
            else:
                # unchanged
                if not fixed_ip:
                    empty += 1
                elif is_valid_ipv4(fixed_ip):
                    unchanged_valid += 1
                else:
                    unfixable += 1
                    problems.append((id_fields, ip_raw, "Invalid and unchanged"))

            row['ip_address'] = fixed_ip
            writer.writerow(row)

        # Write report
        rep.write("IP address normalization report\n")
        rep.write(f"Source file: {INPUT}\n")
        rep.write(f"Output file: {OUTPUT}\n\n")
        rep.write(f"Unchanged valid: {unchanged_valid}\n")
        rep.write(f"Fixed: {fixed}\n")
        rep.write(f"Empty: {empty}\n")
        rep.write(f"Unfixable: {unfixable}\n\n")

        if changes:
            rep.write("Fixed entries:\n")
            for meta, old, new, why in changes:
                rep.write(
                    f"  line {meta['line']} | campus_label={meta['campus_label']} | asset_tag={meta['asset_tag']} | serial={meta['serial_number']}\n"
                )
                rep.write(f"    {old!r} -> {new!r}  ({why})\n")
            rep.write("\n")

        if problems:
            rep.write("Unfixable entries (manual review needed):\n")
            for meta, old, why in problems:
                rep.write(
                    f"  line {meta['line']} | campus_label={meta['campus_label']} | asset_tag={meta['asset_tag']} | serial={meta['serial_number']}\n"
                )
                rep.write(f"    {old!r}  ->  (no change)  Reason: {why}\n")


if __name__ == "__main__":
    main()
