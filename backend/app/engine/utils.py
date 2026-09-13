import calendar
import csv
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')

def D(value):
    if value is None or value == '':
        return None
    result=Decimal(str(value).replace(',', ''))
    if not result.is_finite():
        raise ValueError('Money must be finite')
    return result

def money(value):
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)

def parse_date(value):
    if not value: return None
    if isinstance(value, date): return value
    return date.fromisoformat(str(value)[:10])

def parse_bool(value):
    if isinstance(value, bool): return value
    if str(value).lower() not in {'true','false'}: raise ValueError('Invalid boolean')
    return str(value).lower()=='true'

def add_months(day, months):
    idx=day.year*12+day.month-1+months
    y,m=divmod(idx,12); m+=1
    return date(y,m,min(day.day,calendar.monthrange(y,m)[1]))

def compact_decimal(value):
    return format(value, 'f').rstrip('0').rstrip('.') if '.' in format(value,'f') else str(value)

def plan_decimal(value):
    return str(int(value)) if value==value.to_integral_value() else format(value,'.2f')

def option_numeric_id(value):
    match=re.search(r'(\d+)$', value or '')
    return int(match.group(1)) if match else 0

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows)

def hash_json(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()

def json_safe(obj):
    if isinstance(obj,dict): return {str(k):json_safe(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)): return [json_safe(v) for v in obj]
    if isinstance(obj,set): return sorted(map(str,obj))
    return obj
