from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Iterable
from collections import Counter

from .fx import FXTable
from .models import Event, Forecast, Profile, Request, SpendingChange, Stream, Payment, SimulationResult
from .recurrence import infer_streams, stream_dates
from .utils import D, parse_date, money


ZERO = Decimal('0')

# Pending/uncertain credits specifically called out by the challenge should never be
# treated as available money until settled.
UNCERTAIN_CREDIT_WORDS = ('bonus','commission','refund','lottery','investment gain','capital gain','unrealized','pending payout')
GIG_INCOME_WORDS = ('gig','task marketplace','delivery platform','app earnings','freelance payout','quickcrew')


def apply_evidence(events: list[Event], evidence: dict, user_id: str, home_currency: str) -> tuple[list[Event], list[dict], list[dict]]:
    xs = deepcopy(events)
    by_id = {e.event_id:e for e in xs}
    for p in evidence.get('event_patches', []):
        e = by_id.get(str(p.get('related_event_id') or ''))
        if not e:
            continue
        if p.get('amount') is not None:
            e.amount = D(p['amount'])
        if p.get('currency'):
            e.currency = str(p['currency']).upper()
        if p.get('settlement_date'):
            e.settlement_date = parse_date(p['settlement_date'])
        if p.get('status'):
            e.status = str(p['status']).lower()
        if p.get('direction'):
            e.direction = str(p['direction']).lower()
        if p.get('category'):
            e.category = str(p['category']).lower()
        e.evidence_source = 'evidence_patch'

    virtuals = []
    dedup={}
    for v in evidence.get('virtual_events', []):
        key=(v.get('replaces_category') or v.get('source_id'),v.get('settlement_date'),v.get('direction'))
        dedup[key]=v
    for i, v in enumerate(dedup.values(), 1):
        if v.get('amount') is None or not v.get('settlement_date') or not v.get('direction'):
            continue
        virtuals.append(v)
        if v.get('replaces_category'):
            sd=parse_date(v['settlement_date'])
            xs=[e for e in xs if not (e.status=='scheduled' and e.category==v['replaces_category'] and
                 e.direction==v['direction'] and e.settlement_date and e.settlement_date>=sd)]
        ev=Event(
            event_id=f"evidence:{v.get('source_id') or i}", user_id=user_id, event_type='evidence',
            description=str(v.get('reason') or 'Evidence-derived confirmed financial fact'),
            category=str(v.get('category') or 'other').lower(), direction=str(v['direction']).lower(),
            amount=D(v['amount']), currency=str(v.get('currency') or home_currency).upper(),
            event_date=parse_date(v['settlement_date']), settlement_date=parse_date(v['settlement_date']),
            status=str(v.get('status') or 'scheduled').lower(), flexibility='fixed', evidence_source='message_or_image'
        )
        # The evidence is known at evaluation time even if settlement is future.
        ev.event_date=date.min
        xs.append(ev)
    return xs, virtuals, evidence.get('disable_categories', [])


def _effective_events(events: list[Event]) -> list[Event]:
    """Collapse linked lifecycle rows and leave only the latest terminal record.

    linked_event_id points to an earlier row in the same lifecycle. Any row that is
    referenced by a newer row is superseded, preventing pending->settled/cancelled
    chains from being counted twice. Exact unrelated transactions are preserved.
    """
    by_id={e.event_id:e for e in events}
    for e in events:
        seen=set(); current=e
        while current and current.linked_event_id:
            if current.event_id in seen: raise ValueError('Cycle in linked transaction lifecycle')
            seen.add(current.event_id); current=by_id.get(current.linked_event_id)
    superseded=set()
    for e in events:
        old=by_id.get(e.linked_event_id)
        if not old or e.event_date<old.event_date: continue
        if e.status=='cancelled' or (e.direction==old.direction and old.status in {'pending','scheduled','failed'} and e.status in {'settled','scheduled','cancelled'}):
            superseded.add(old.event_id)
    result=[]; seen=set()
    for e in events:
        if e.event_id in superseded: continue
        signature=(e.event_type,e.description,e.category,e.direction,e.amount,e.currency,e.event_date,e.settlement_date,e.status,e.flexibility,e.minimum_allowed_amount)
        if signature in seen: continue
        seen.add(signature); result.append(e)
    return result


class Forecaster:
    def __init__(self, fx: FXTable):
        self.fx = fx

    def _home(self, amount: Decimal, when: date, currency: str, home: str) -> Decimal:
        return self.fx.convert(amount, when, currency or home, home)

    @staticmethod
    def _is_countable_explicit(e: Event, request_date: date, horizon_end: date) -> bool:
        if e.amount is None or not e.settlement_date or e.settlement_date > horizon_end:
            return False
        if e.direction == 'debit':
            return e.status in {'pending','scheduled'} or (e.status=='settled' and e.settlement_date>request_date)
        if e.direction == 'credit':
            if e.settlement_date < request_date or e.status not in {'scheduled','settled'} or (e.status=='settled' and e.settlement_date<=request_date):
                return False
            txt = (e.description + ' ' + e.category).lower()
            if e.evidence_source!='message_or_image' and any(w in txt for w in UNCERTAIN_CREDIT_WORDS):
                return False
            # Scheduled credits are treated as confirmed; pending credits are never counted.
            return True
        return False

    @staticmethod
    def _income_stream_allowed(s: Stream, history: list[Event]) -> bool:
        if s.direction != 'credit':
            return True
        if s.category != 'salary':
            return False
        # Only regular monthly salary/payroll is projected. Commission/bonus and gig
        # income streams remain excluded unless future evidence explicitly confirms them.
        if s.event_type in {'salary_uncertain_variable','salary_gig'}:
            return False
        return bool(s.monthly_day)

    def build(self, profile: Profile, request: Request, events: list[Event], virtuals: list[dict], disabled: list[dict]) -> Forecast:
        horizon_end = request.request_date + timedelta(days=90)
        f = Forecast(request.request_date, horizon_end)
        f.home_currency=profile.home_currency
        effective_events = _effective_events([e for e in events if e.event_date<=request.request_date or e.status in {'scheduled','pending'} or e.evidence_source=='message_or_image'])
        explicit_keys: set[tuple[date,str,str]] = set()
        explicit_by_key: dict[tuple[date,str,str], list[tuple[Event, Decimal]]] = {}

        # Explicit future obligations / confirmed credits have priority over inferred recurrence.
        # Suppress only exact semantic duplicates; distinct same-day transactions remain separate.
        seen_explicit: set[tuple] = set()
        for e in effective_events:
            if not self._is_countable_explicit(e, request.request_date, horizon_end):
                continue
            duplicate_key = (e.settlement_date, e.category.lower(), e.direction.lower(), str(e.amount),
                             (e.currency or profile.home_currency).upper(), ' '.join(e.description.lower().split()))
            if duplicate_key in seen_explicit:
                f.warnings.append(f'duplicate_ignored:{e.event_id}')
                continue
            seen_explicit.add(duplicate_key)
            try:
                amt = self._home(e.amount, e.settlement_date, e.currency, profile.home_currency)
            except ValueError as ex:
                raise ValueError(f'Cannot price event {e.event_id}: {ex}') from ex
            signed = amt if e.direction == 'credit' else -amt
            cash_date=max(e.settlement_date,request.request_date)
            f.daily_flows[cash_date] = f.daily_flows.get(cash_date, ZERO) + signed
            key=(cash_date, e.category, e.direction)
            explicit_keys.add(key)
            explicit_by_key.setdefault(key, []).append((e, signed))

        streams = infer_streams(effective_events, request.request_date)
        # An explicitly one-cycle payroll adjustment does not establish a new
        # permanent salary. Recover the repeated regular amount when history
        # supplies at least three identical base-pay observations.
        one_cycle_pay=any(v.get('category')=='salary' and v.get('one_cycle') is True for v in virtuals)
        if one_cycle_pay:
            for s in streams:
                if s.direction!='credit' or s.category!='salary': continue
                amounts=Counter(e.amount for e in effective_events if e.status=='settled' and e.amount is not None and
                                e.description==s.description and e.currency==s.currency and e.settlement_date<=request.request_date)
                if amounts:
                    regular,count=amounts.most_common(1)[0]
                    if count>=3 and list(amounts.values()).count(count)==1: s.amount=regular
        by_id={e.event_id:e for e in events}
        cancellations={}
        for e in events:
            if e.status!='cancelled': continue
            original=by_id.get(e.linked_event_id,e)
            cancellations[(original.category,original.direction,original.description.lower())]=e.settlement_date or e.event_date

        if not any(s.category=='salary' and s.direction=='credit' for s in streams):
            confirmed=[e for e in effective_events if e.status=='scheduled' and e.category=='salary' and
                       e.direction=='credit' and e.amount is not None and 'next confirmed salary' in e.description.lower()]
            for e in confirmed:
                streams.append(Stream('confirmed:'+e.event_id,e.category,e.direction,'fixed','evidence',e.event_id,
                                      e.amount,e.currency,e.settlement_date,monthly_day=e.settlement_date.day,description=e.description))

        # Evidence can explicitly replace a recurring category beginning on a date.
        replaces: dict[str, date] = {}
        synthetic_streams: list[Stream] = []
        for i, v in enumerate(virtuals, 1):
            rep = v.get('replaces_category')
            sd = parse_date(v.get('settlement_date')) if v.get('settlement_date') else None
            if rep and sd:
                old = replaces.get(str(rep).lower())
                if old is None or sd < old:
                    replaces[str(rep).lower()] = sd
            if sd and v.get('amount') is not None and (v.get('monthly') or v.get('recurrence_days')):
                amount = D(v['amount'])
                synthetic_streams.append(Stream(
                    stream_id=f"evidence_stream:{v.get('source_id') or i}", category=str(v.get('category') or rep or 'other').lower(),
                    direction=str(v.get('direction') or 'credit').lower(), flexibility='fixed', event_type='evidence',
                    source_event_id=f"evidence:{v.get('source_id') or i}", amount=amount,
                    currency=str(v.get('currency') or profile.home_currency).upper(),
                    cadence_days=int(v['recurrence_days']) if v.get('recurrence_days') else None,
                    monthly_day=sd.day if v.get('monthly') else None, last_date=sd,
                ))

        disabled_by_cat = {}
        for d in disabled:
            if d.get('category') and d.get('effective_date'):
                disabled_by_cat[str(d['category']).lower()] = parse_date(d['effective_date'])

        for s in streams + synthetic_streams:
            if not self._income_stream_allowed(s, effective_events) and not s.stream_id.startswith('evidence_stream:'):
                continue
            f.stream_lookup[s.stream_id] = s
            # Historical inferred streams predict the NEXT occurrence after the last settled event.
            # Evidence streams already added their first explicit event, so recurrence also starts after it.
            occurrences = []
            for d in stream_dates(s, request.request_date, horizon_end):
                cancelled_on=cancellations.get((s.category,s.direction,s.description.lower()))
                if cancelled_on and d>=cancelled_on: continue
                own=next((v for v in virtuals if s.source_event_id=='evidence:'+str(v.get('source_id'))),None)
                if own:
                    if own.get('effective_until') and d>parse_date(own['effective_until']): continue
                    if any(v.get('replaces_category')==s.category and parse_date(v['settlement_date'])>s.last_date and
                           d>=parse_date(v['settlement_date']) for v in virtuals): continue
                # stream_dates yields only future occurrences after last_date.
                if s.category in disabled_by_cat and d >= disabled_by_cat[s.category]:
                    continue
                if s.category in replaces and d >= replaces[s.category] and not s.stream_id.startswith('evidence_stream:'):
                    continue
                # An explicit future record on the same day/category/direction supersedes inference.
                # If it is the same flexible recurring stream, still register it as a
                # controllable occurrence so stop/reduce can adjust the already-booked flow.
                key=(d, s.category, s.direction)
                same=[(ee,signed) for ee,signed in explicit_by_key.get(key,[]) if
                      ee.description.lower()==s.description.lower() or ee.linked_event_id==s.source_event_id or
                      (s.direction=='credit' and (ee.evidence_source=='message_or_image' or 'next confirmed salary' in ee.description.lower()))]
                if same:
                    if s.direction == 'debit' and s.flexibility in {'stoppable','reducible','reducible_or_stoppable'}:
                        for ee, signed_explicit in same:
                            if ee.flexibility == s.flexibility:
                                occurrences.append((d, signed_explicit))
                    continue
                try:
                    amt_home = self._home(s.amount, d, s.currency, profile.home_currency)
                except ValueError as ex:
                    raise ValueError(f'Cannot price stream {s.source_event_id} on {d}: {ex}') from ex
                signed = amt_home if s.direction == 'credit' else -amt_home
                f.daily_flows[d] = f.daily_flows.get(d, ZERO) + signed
                occurrences.append((d, signed))
            f.stream_occurrences[s.stream_id] = occurrences

        return f

    def adjusted_flows(self, forecast: Forecast, changes: list[SpendingChange]) -> dict[date, Decimal]:
        flows = dict(forecast.daily_flows)
        by_stream = {c.stream_id:c for c in changes}
        for sid, c in by_stream.items():
            s = forecast.stream_lookup.get(sid)
            if not s or not s.amount:
                continue
            for d, signed in forecast.stream_occurrences.get(sid, []):
                if c.action == 'stop':
                    delta = -signed
                elif c.action == 'reduce_to' and c.new_amount is not None:
                    new_home=self._home(c.new_amount,d,s.currency,forecast.home_currency or s.currency)
                    delta = -new_home - signed
                else:
                    continue
                flows[d] = flows.get(d, ZERO) + delta
        return flows

    def simulate(self, profile: Profile, forecast: Forecast, payments: list[Payment] | None=None,
                 changes: list[SpendingChange] | None=None) -> SimulationResult:
        payments = payments or []
        if any(p.date<forecast.request_date or p.date>forecast.horizon_end or p.amount<0 or p.amount!=money(p.amount) for p in payments):
            raise ValueError('Payment outside forecast or invalid monetary amount')
        changes = changes or []
        flows = self.adjusted_flows(forecast, changes)
        pay_by_date = {}
        for p in payments:
            pay_by_date[p.date] = pay_by_date.get(p.date, ZERO) + p.amount
        bal = profile.current_available_balance
        min_bal = bal
        min_date = forecast.request_date
        violations=[]
        if bal<profile.minimum_balance_to_keep: violations.append((forecast.request_date,bal))
        d = forecast.request_date
        while d <= forecast.horizon_end:
            # Base financial events settle first on a date; recommended payment follows.
            bal += flows.get(d, ZERO)
            bal -= pay_by_date.get(d, ZERO)
            if bal<profile.minimum_balance_to_keep: violations.append((d,bal))
            if bal < min_bal:
                min_bal, min_date = bal, d
            d += timedelta(days=1)
        return SimulationResult(not violations, min_bal, min_date, bal, violations)

    def amount_safe_today(self, profile: Profile, request: Request, forecast: Forecast) -> Decimal:
        if profile.current_available_balance < profile.minimum_balance_to_keep: return ZERO
        bal=profile.current_available_balance; headroom=None
        d=forecast.request_date
        while d<=forecast.horizon_end:
            bal+=forecast.daily_flows.get(d,ZERO)
            margin=bal-profile.minimum_balance_to_keep
            headroom=margin if headroom is None else min(headroom,margin)
            d+=timedelta(days=1)
        return max(ZERO,min(request.requested_amount,headroom)).quantize(Decimal('0.01'),rounding=ROUND_DOWN)

    def earliest_full_date(self, profile: Profile, request: Request, forecast: Forecast) -> date | None:
        d = request.request_date
        while d <= forecast.horizon_end:
            sim = self.simulate(profile, forecast, [Payment(d, request.requested_amount)])
            if sim.safe:
                return d
            d += timedelta(days=1)
        return None
