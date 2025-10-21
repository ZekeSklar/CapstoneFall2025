from __future__ import annotations

from typing import Any, Iterable, Tuple


def letters_to_number(letters: str) -> int:
    """Convert row letters (A..Z, AA..) to 1-based number (A=1, Z=26, AA=27).

    Returns 0 if input is empty or invalid.
    """
    if not letters:
        return 0
    total = 0
    for ch in letters.strip().upper():
        if 'A' <= ch <= 'Z':
            total = total * 26 + (ord(ch) - ord('A') + 1)
        else:
            return 0
    return total


def parse_shelf_code(code: str) -> Tuple[str, int]:
    """Parse a shelf code like 'A-3', 'B12', or 'AA 7' into (row_letters, column).

    - Row portion is the leading letters.
    - Column portion is the trailing number.
    Returns ("", 0) if parsing fails.
    """
    if not code:
        return "", 0
    raw = code.strip().replace(" ", "").replace("_", "-")
    # Normalize delimiter to '-'
    if '-' in raw:
        left, _, right = raw.partition('-')
        row = ''.join(ch for ch in left if ch.isalpha()).upper()
        try:
            col = int(''.join(ch for ch in right if ch.isdigit()))
        except ValueError:
            col = 0
        return row, col
    # No dash: consume leading letters then trailing digits
    row_chars = []
    col_chars = []
    i = 0
    while i < len(raw) and raw[i].isalpha():
        row_chars.append(raw[i])
        i += 1
    while i < len(raw) and raw[i].isdigit():
        col_chars.append(raw[i])
        i += 1
    row = ''.join(row_chars).upper()
    try:
        col = int(''.join(col_chars)) if col_chars else 0
    except ValueError:
        col = 0
    return row, col


def shelf_sort_key(obj: Any) -> tuple[int, int, str]:
    """Return a sort key (row_number, column, name) for items with shelf info.

    Supports objects/dicts with:
    - attributes `shelf_row`, `shelf_column`, and optionally `name`
    - or a `shelf_code`/`location` string like 'B-12'.
    """
    row: str = ""
    col: int = 0
    name: str = ""

    # Dict-like access
    if isinstance(obj, dict):
        row = (obj.get('shelf_row') or '').strip().upper() if obj.get('shelf_row') else ''
        col_val = obj.get('shelf_column')
        if isinstance(col_val, int):
            col = col_val
        elif isinstance(col_val, str) and col_val.isdigit():
            col = int(col_val)
        code = obj.get('shelf_code') or obj.get('location')
        if (not row or not col) and isinstance(code, str):
            r, c = parse_shelf_code(code)
            row = row or r
            col = col or c
        name = obj.get('name') or ''
    else:
        # Attribute access
        row = getattr(obj, 'shelf_row', '') or ''
        if isinstance(row, str):
            row = row.strip().upper()
        col_val = getattr(obj, 'shelf_column', 0)
        if isinstance(col_val, int):
            col = col_val
        elif isinstance(col_val, str) and col_val.isdigit():
            col = int(col_val)
        else:
            col = 0
        code = getattr(obj, 'shelf_code', None) or getattr(obj, 'location', None)
        if (not row or not col) and isinstance(code, str):
            r, c = parse_shelf_code(code)
            row = row or r
            col = col or c
        name = getattr(obj, 'name', '') or ''

    return (letters_to_number(row), int(col or 0), str(name))


def sort_by_shelf(items: Iterable[Any]) -> list[Any]:
    """Return a new list sorted by shelf (row letters, then column number)."""
    return sorted(items, key=shelf_sort_key)

