import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from .models import Stream

def infer_streams(events, request_date, strategy='latest'):
    groups=defaultdict(list)
    for e in events:
        if e.status!='settled' or e.amount is None or not e.settlement_date or e.settlement_date>request_date: continue
        if e.event_type not in {'expense','income','salary','subscription','debt_payment'}: continue
        text=e.description.lower()
        if e.direction=='credit' and (e.category!='salary' or any(w in text for w in ['commission','bonus','arrears','prorated','final employer','seasonal','temporary assignment','peak-season','payout','app earnings','freelance','invoice','contract payment','project payment','retainer','reimbursement'])): continue
        # Everyday spending can have changing merchants but a stable category cadence.
        # One-off image receipts remain separate from the regular basket observations.
        group_description='' if e.category in {'groceries','transport','dining'} and e.evidence_source=='ledger' else text.strip()
        groups[(group_description,e.category,e.direction,e.currency,e.flexibility,str(e.minimum_allowed_amount))].append(e)
    streams=[]
    for key, xs in sorted(groups.items()):
        xs=sorted(xs,key=lambda e:(e.settlement_date,e.event_id))
        if len(xs)<3: continue
        gaps=[(b.settlement_date-a.settlement_date).days for a,b in zip(xs,xs[1:])]
        last=xs[-1]; days=[e.settlement_date.day for e in xs]
        monthly=all(27<=g<=40 for g in gaps) and (max(days)-min(days)<=3 or last.direction=='credit')
        cadence=None if monthly else int(median(gaps))
        if not monthly and (cadence<=0 or any(abs(g-cadence)>2 for g in gaps)): continue
        if (request_date-last.settlement_date).days > (45 if monthly else cadence*2): continue
        amount=last.amount
        month_day=last.settlement_date.day
        if monthly and all(e.settlement_date.day==calendar.monthrange(e.settlement_date.year,e.settlement_date.month)[1] for e in xs): month_day=31
        if strategy=='mean': amount=sum(e.amount for e in xs)/len(xs)
        if strategy=='median3': amount=median([e.amount for e in xs[-3:]])
        streams.append(Stream(last.event_id,last.category,last.direction,last.flexibility,last.event_type,
                              last.event_id,amount,last.currency,last.settlement_date,cadence,
                              month_day if monthly else None,last.minimum_allowed_amount,last.description))
    return streams

def stream_dates(stream, start, end):
    if stream.monthly_day:
        idx=stream.last_date.year*12+stream.last_date.month
        while True:
            y,m=divmod(idx,12); m+=1
            d=date(y,m,min(stream.monthly_day,calendar.monthrange(y,m)[1]))
            if d>end: return
            if d>=start: yield d
            idx+=1
    elif stream.cadence_days:
        d=stream.last_date+timedelta(days=stream.cadence_days)
        while d<=end:
            if d>=start: yield d
            d+=timedelta(days=stream.cadence_days)
