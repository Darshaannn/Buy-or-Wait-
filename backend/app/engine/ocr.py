"""OCR parser module for image receipts and bills.
Provides pure Python regex parsing of text lines extracted from images.
Local Windows OCR invocation is made optional and gracefully degraded on non-Windows platforms.
"""
import re
from datetime import datetime
from .utils import D

OCR_VERSION = 'portable-labels-1'


def read_lines(path):
    """Optional platform OCR hook. On production/Linux servers, vision LLM (e.g. Gemini) handles images directly."""
    import os, subprocess, json
    from pathlib import Path
    if os.name != 'nt':
        return []
    ps1 = Path(__file__).with_name('windows_ocr.ps1')
    if not ps1.exists():
        return []
    try:
        proc = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(ps1), '-ImagePath', str(Path(path).resolve())],
            capture_output=True, text=True, encoding='utf-8', timeout=30
        )
        if proc.returncode != 0:
            return []
        words = json.loads(proc.stdout)
        rows = []
        for w in sorted(words, key=lambda w: w['y'] + w['h'] / 2):
            cy = w['y'] + w['h'] / 2
            if not rows or abs(cy - rows[-1][0]) > max(8, w['h'] * 0.5):
                rows.append((cy, []))
            rows[-1][1].append(w)
        return [' '.join(w['text'] for w in sorted(row, key=lambda w: w['x'])) for _, row in rows]
    except Exception:
        return []


def labelled_amount(line):
    spaced = re.search(r'(?<![\w.,])([1-9][0-9]?(?: [0-9oO]{2})+ [0-9oO]{3}(?:\.[0-9oO]{1,2})?|[1-9][0-9]{0,2}(?: [0-9oO]{3})+(?:\.[0-9oO]{1,2})?)\s*$', line)
    if spaced:
        line = line[:spaced.start()] + spaced.group(1).replace(' ', ',')
    match = re.search(r'(?<![\w.,])([0-9][0-9,oO]*(?:\.[0-9oO]{1,2})?)\s*$', line)
    if not match:
        return None
    raw = match.group(1).replace('o', '0').replace('O', '0')
    integer = raw.split('.')[0]
    if len(integer) > 1 and integer.startswith('0'):
        return None
    if ',' in integer and not (re.fullmatch(r'[1-9]\d{0,2}(?:,\d{3})+', integer) or re.fullmatch(r'[1-9]\d?(?:,\d{2})*,\d{3}', integer)):
        return None
    value = D(raw)
    return value if value > 0 else None


def parse_image_lines(lines, event, request_date):
    label = None
    value = None
    currency = event.currency
    patterns = [
        r'^net pay\b', r'^balance due\b', r'^amount payable\b', r'^total paid\b',
        r'^total amount received\b', r'^grand total\b', r'^net amount\b', r'^total\b',
        r'^item bill\b', r'^cash paid\b'
    ]
    for pattern in patterns:
        matches = [line for line in lines if re.search(pattern, line, re.I)]
        if len(matches) == 1:
            value = labelled_amount(matches[0])
            label = pattern
            cm = re.search(r'\b(INR|IDR|EUR|USD|ZAR)\b', matches[0], re.I)
            if cm:
                currency = cm.group(1).upper()
            if value is not None:
                break

    if label == r'^cash paid\b':
        change_lines = [line for line in lines if re.search(r'^change\b', line, re.I)]
        if change_lines:
            change = labelled_amount(change_lines[0]) if len(change_lines) == 1 else None
            if change is None or value is None or change >= value:
                return None
            value -= change
            label = 'cash tendered less returned change'

    for i, line in enumerate(lines[:-1]):
        if re.fullmatch(r'amount due after', line.strip(), re.I):
            m = re.fullmatch(r'(\d{2}-[A-Za-z]{3}-\d{4})\s+([\d,.]+)', lines[i + 1])
            if m and (event.settlement_date or request_date) > datetime.strptime(m[1], '%d-%b-%Y').date():
                value = D(m[2])
                label = 'dated overdue balance'
                break

    if value is None or value < 0:
        return None
    return {
        'event_patches': [{'related_event_id': event.event_id, 'amount': str(value), 'currency': currency, 'reason': f'Local OCR: {label}'}],
        'virtual_events': [], 'disable_categories': [], 'notes': []
    }
