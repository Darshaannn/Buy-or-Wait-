"""Strict boundary between untrusted extraction and financial arithmetic."""
from .utils import D, parse_date

SCHEMA_VERSION='4'
STATUS={'settled','scheduled','pending','cancelled','failed','unrealized'}
CURRENCIES={'INR','IDR','USD','EUR','ZAR'}
PATCH={'related_event_id','amount','currency','settlement_date','status','direction','category','reason'}
VIRTUAL={'source_id','direction','category','amount','currency','settlement_date','status','recurrence_days','monthly','one_cycle','effective_until','replaces_category','reason'}
DISABLE={'category','effective_date','reason'}
KEYS={'event_patches':PATCH,'virtual_events':VIRTUAL,'disable_categories':DISABLE,'notes':None}

class EvidenceUnavailable(ValueError):
    pass

def validate_evidence(data,event_ids=None,source_ids=None):
    if type(data)!=dict or set(data)!=set(KEYS): raise ValueError('Invalid evidence object fields')
    for section,allowed in KEYS.items():
        if type(data[section])!=list: raise ValueError('Evidence sections must be arrays')
        for item in data[section]:
            if section=='notes':
                if type(item)!=str: raise ValueError('Notes must be strings')
                continue
            if type(item)!=dict or set(item)-allowed: raise ValueError('Unsupported evidence fields')
            required={'event_patches':{'related_event_id','reason'},'virtual_events':{'source_id','direction','category','amount','currency','settlement_date','status','monthly','reason'},'disable_categories':{'category','effective_date','reason'}}[section]
            if not required<=set(item): raise ValueError('Missing required evidence fields')
            for k,v in item.items():
                if v is None: continue
                if k=='amount':
                    if isinstance(v,bool) or not isinstance(v,(str,int,float)) or D(v)<0: raise ValueError('Invalid evidence amount')
                elif k in {'settlement_date','effective_until','effective_date'}:
                    if type(v)!=str or len(v)!=10: raise ValueError('Evidence dates must be ISO dates')
                    parse_date(v)
                elif k in {'monthly','one_cycle'}:
                    if type(v)!=bool: raise ValueError(f'{k} must be boolean')
                elif k=='recurrence_days':
                    if type(v)!=int or not 1<=v<=366: raise ValueError('Invalid recurrence interval')
                elif type(v)!=str: raise ValueError(f'{k} must be a string')
            if item.get('currency') and item['currency'] not in CURRENCIES: raise ValueError('Unsupported currency')
            if item.get('status') and item['status'] not in STATUS: raise ValueError('Unsupported cash state')
            if item.get('direction') and item['direction'] not in {'debit','credit','non_cash'}: raise ValueError('Unsupported direction')
            if section=='event_patches' and event_ids is not None and item['related_event_id'] not in event_ids: raise ValueError('Evidence references an unrelated event')
            if section=='virtual_events':
                if item['amount'] is None or item['settlement_date'] is None: raise ValueError('Incomplete future fact')
                if item.get('monthly') and item.get('recurrence_days'): raise ValueError('Conflicting recurrence')
                if source_ids is not None and not any(item['source_id']==s or item['source_id'].startswith(s+'-') for s in source_ids): raise ValueError('Unknown evidence source')
    return data

def json_schema():
    fields={}
    for section,keys in KEYS.items():
        if keys is None:
            fields[section]={'type':'array','items':{'type':'string'}}; continue
        props={}
        for k in sorted(keys):
            if k in {'monthly','one_cycle'}: props[k]={'type':'boolean'}
            elif k=='recurrence_days': props[k]={'type':['integer','null'],'minimum':1,'maximum':366}
            else: props[k]={'type':['string','null']}
        fields[section]={'type':'array','items':{'type':'object','properties':props,'required':sorted(keys),'additionalProperties':False}}
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
