# Utility Scripts

Run these from the repository root (they read and write files under `data/`).

- clean_printer_csv.py
  - Normalizes MAC addresses, flattens multi-line comments, and replaces unknowns with safe placeholders.
  - IO:
    - Input: `data/printer_inventory_condensed_for_import_FINAL2.csv`
    - Output: `data/printer_inventory_condensed_for_import_FINAL.csv`

- fix_ips_in_csv.py
  - Cleans and normalizes IPv4 addresses with conservative rules and writes a human-readable report.
  - IO:
    - Input: `data/printer_inventory_condensed_for_import_FINAL.csv`
    - Output: `data/printer_inventory_condensed_for_import_FIXED.csv`
    - Report: `data/printer_inventory_ip_report.txt`

- _snmp_walk.py
  - Minimal asyncio SNMP walker for debugging (requires `pysnmp`).
  - Edit IP/community/OID at the bottom before running.

- _fix_snmp.py
  - Experimental/unsafe helper used during development.
  - Not intended for production; do not run as part of normal workflows.

Examples

```
python scripts/clean_printer_csv.py
python scripts/fix_ips_in_csv.py
```

