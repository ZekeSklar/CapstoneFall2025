import csv
import re
from pathlib import Path

# Input and output file paths (under repo-level data/)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT = str(DATA_DIR / 'printer_inventory_condensed_for_import_FINAL2.csv')
OUTPUT = str(DATA_DIR / 'printer_inventory_condensed_for_import_FINAL.csv')

def normalize_mac(mac):
    if not mac or mac.strip().lower() in [
        'unknown', 'unknown-macaddress', 'not yet known', '00:00:00:00:00:00', '00-00-00-00-00-00', '00.00.00.00.00.00', '00:21:b7:c1:04:69', 'unknown,', 'unknown\n', 'unknown\r\n']:
        return '00:00:00:00:00:00'
    # Remove all non-hex chars, then format as colon-separated, lowercase
    mac_clean = re.sub(r'[^0-9a-fA-F]', '', mac)
    if len(mac_clean) == 12:
        return ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2)).lower()
    return '00:00:00:00:00:00'

def flatten_comment(comment):
    if not comment:
        return ''
    # Replace newlines and excessive whitespace with ' | '
    return re.sub(r'\s*\n+\s*', ' | ', comment).replace('"', "'").strip()

def clean_unknown(val, placeholder=''):
    if val is None:
        return placeholder
    value = str(val).strip()
    if not value:
        return placeholder
    if value.lower() in [
        'unknown', 'unknown-macaddress', 'unknown-ipaddress', 'unknown-serial', 'unknown-asset', 'unknown-label',
        'not yet known', 'n/a', 'na', 'none', 'null', 'tbd', 'tba', 'pending', 'unk', 'unk.', 'unknown,', 'unknown\n', 'unknown\r\n'
    ]:
        return placeholder
    return value


def main():
    with open(INPUT, newline='', encoding='utf-8') as infile, open(OUTPUT, 'w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            # Clean MAC address
            row['mac_address'] = normalize_mac(row.get('mac_address', ''))
            # Flatten comments
            row['comments'] = flatten_comment(row.get('comments', ''))
            # Clean unknowns in ip_address and serial_number
            row['ip_address'] = clean_unknown(row.get('ip_address', ''), '0.0.0.0')
            row['serial_number'] = clean_unknown(row.get('serial_number', ''), 'UNKNOWN-SERIAL')
            # Insert generic values for campus_label and asset_tag if missing/unknown
            row['campus_label'] = row.get('campus_label', '').strip()
            if not row['campus_label'] or row['campus_label'].lower() in [
                'unknown', 'n/a', 'na', 'none', 'null', 'tbd', 'tba', 'pending', 'unk', 'unk.', 'generic-label', 'unknown,', 'unknown\n', 'unknown\r\n']:
                row['campus_label'] = 'UNKNOWN-LABEL'
            row['asset_tag'] = row.get('asset_tag', '').strip()
            if not row['asset_tag'] or row['asset_tag'].lower() in [
                'unknown', 'n/a', 'na', 'none', 'null', 'tbd', 'tba', 'pending', 'unk', 'unk.', 'generic-asset', 'unknown,', 'unknown\n', 'unknown\r\n']:
                row['asset_tag'] = 'UNKNOWN-ASSET'
            writer.writerow(row)

if __name__ == '__main__':
    main()
