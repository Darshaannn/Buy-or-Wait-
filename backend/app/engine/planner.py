from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from itertools import combinations, product

from .forecast import Forecaster
from .models import CandidatePlan, Forecast, Payment, PaymentOption, Profile, Request, SpendingChange
from .utils import option_numeric_id, plan_decimal, compact_decimal, add_months, money
from copy import deepcopy

ZERO = Decimal('0')


class Planner:
    def __init__(self, forecaster: Forecaster):
        self.forecaster = forecaster

    @staticmethod
    def _installment_payments(o: PaymentOption) -> list[Payment]:
        if o.payment_method != 'installments' or not o.payment_frequency_days or o.payment_frequency_days<1 or o.number_of_payments<1 or o.payment_amount<=0:
            return []
        return [Payment(o.first_payment_date + timedelta(days=o.payment_frequency_days*i), o.payment_amount)
                for i in range(o.number_of_payments)]

    def _base_candidates(self, profile: Profile, req: Request, options: list[PaymentOption], safe_today: Decimal,
                         earliest_full, changes: list[SpendingChange]) -> list[CandidatePlan]:
        out = []
        # Full payment today / wait use the request amount. We still require full_payment to be an accepted method.
        if 'full_payment' in profile.payment_methods:
            out.append(CandidatePlan('full_payment', [Payment(req.request_date, req.requested_amount)], req.requested_amount,
                                     req.request_date, req.request_date, spending_changes=list(changes)))
            if changes:
                # Spending changes can make a full payment safe before the independent
                # no-change earliest-full date (sample 06 demonstrates the distinction).
                d = req.request_date + timedelta(days=1)
                last = min(req.desired_completion_date, req.request_date + timedelta(days=90))
                while d <= last:
                    out.append(CandidatePlan('wait', [Payment(d, req.requested_amount)], req.requested_amount,
                                             d, d, spending_changes=list(changes)))
                    d += timedelta(days=1)
            elif earliest_full and earliest_full > req.request_date and earliest_full <= req.desired_completion_date:
                out.append(CandidatePlan('wait', [Payment(earliest_full, req.requested_amount)], req.requested_amount,
                                         earliest_full, earliest_full, spending_changes=list(changes)))

        if (req.allows_partial_payment and 'partial_payment' in profile.payment_methods and
                safe_today > ZERO and safe_today < req.requested_amount and earliest_full and
                earliest_full <= req.desired_completion_date):
            # Exact problem contract: 2 payments; second is requested_amount - amount_safe_to_pay.
            out.append(CandidatePlan('partial_payment',
                                     [Payment(req.request_date, safe_today), Payment(earliest_full, req.requested_amount-safe_today)],
                                     req.requested_amount, earliest_full, req.request_date, spending_changes=list(changes)))

        if 'installments' in profile.payment_methods:
            for o in options:
                if o.payment_method != 'installments':
                    continue
                if profile.max_installment_months is None:
                    continue
                pays = self._installment_payments(o)
                if not pays:
                    continue
                completion = pays[-1].date
                if (pays[0].date<req.request_date or completion>add_months(req.request_date,profile.max_installment_months) or
                    o.financing_fee<0 or o.total_payable_amount!=req.requested_amount+o.financing_fee or
                    sum(p.amount for p in pays)!=o.total_payable_amount):
                    continue
                if completion > req.desired_completion_date:
                    continue
                out.append(CandidatePlan('installments', pays, o.total_payable_amount, completion,
                                         pays[0].date, option_id=o.payment_option_id, spending_changes=list(changes)))
        return out

    @staticmethod
    def eligible_changes(profile: Profile, forecast: Forecast) -> list[SpendingChange]:
        actions = []
        for sid, s in forecast.stream_lookup.items():
            if s.direction != 'debit' or s.category in profile.protected:
                continue
            if not forecast.stream_occurrences.get(sid):
                continue
            if s.category in profile.stoppable_categories and s.flexibility in {'stoppable','reducible_or_stoppable'}:
                actions.append(SpendingChange('stop', s.source_event_id, sid))
            if (s.category in profile.reducible_categories and s.flexibility in {'reducible','reducible_or_stoppable'} and
                    s.minimum_allowed_amount is not None and s.minimum_allowed_amount < s.amount):
                actions.append(SpendingChange('reduce_to', s.source_event_id, sid, s.minimum_allowed_amount))
        return actions

    def change_sets(self, profile: Profile, forecast: Forecast):
        actions = self.eligible_changes(profile, forecast)
        # Generate at most one action per stream, max 3 streams. Empty set is first.
        yield []
        by_stream = {}
        for a in actions:
            by_stream.setdefault(a.stream_id, []).append(a)
        streams = sorted(by_stream)
        for n in range(1, min(3, len(streams))+1):
            for selected in combinations(streams, n):
                for choices in product(*(by_stream[s] for s in selected)):
                    yield list(choices)

    @staticmethod
    def _change_burden(forecast: Forecast, changes: list[SpendingChange]) -> Decimal:
        burden = ZERO
        for c in changes:
            s = forecast.stream_lookup.get(c.stream_id)
            if not s or not s.amount:
                continue
            for _d, signed in forecast.stream_occurrences.get(c.stream_id, []):
                original = abs(signed)
                if c.action == 'stop':
                    burden += original
                elif c.action == 'reduce_to' and c.new_amount is not None:
                    burden += original * (Decimal('1') - c.new_amount/s.amount)
        return burden

    @staticmethod
    def _rank_key(plan: CandidatePlan, forecast: Forecast):
        # Exact challenge tie-breakers first. Change burden only breaks otherwise-equivalent changed plans.
        return (
            1 if plan.spending_changes else 0,
            plan.total_payable,
            plan.start_date,
            len(plan.payments),
            option_numeric_id(plan.option_id) if plan.option_id else 0,
            len(plan.spending_changes),
            Planner._change_burden(forecast, plan.spending_changes),
            '|'.join(f'{c.event_id}:{c.action}' for c in plan.spending_changes),
        )

    def choose(self, profile: Profile, req: Request, forecast: Forecast, options: list[PaymentOption],
               safe_today: Decimal, earliest_full) -> CandidatePlan | None:
        safe_plans = []
        # Important: amount_safe_to_pay / earliest date are defined BEFORE spending changes, so partial always uses base safe_today.
        for changes in self.change_sets(profile, forecast):
            # Optimization: if we already have any safe no-change plan, changed plans can never beat it.
            if changes and any(not p.spending_changes for p in safe_plans):
                break
            for p in self._base_candidates(profile, req, options, safe_today, earliest_full, changes):
                if p.completion_date > req.desired_completion_date:
                    continue
                if p.completion_date > forecast.horizon_end:
                    continue
                sim = self.forecaster.simulate(profile, forecast, p.payments, p.spending_changes)
                p.simulation = sim
                if sim.safe:
                    if p.spending_changes:
                        p.spending_changes=self._minimal_changes(profile,forecast,p.payments,p.spending_changes)
                        p.simulation=self.forecaster.simulate(profile,forecast,p.payments,p.spending_changes)
                    safe_plans.append(p)
        return min(safe_plans, key=lambda p:self._rank_key(p, forecast)) if safe_plans else None

    def _minimal_changes(self, profile, forecast, payments, changes):
        changes=deepcopy(changes)
        # Remove unnecessary interventions, then find the highest safe cent value
        # for each reduction. Enumerating subsets also explores alternative choices.
        for c in list(changes):
            without=[x for x in changes if x is not c]
            if self.forecaster.simulate(profile,forecast,payments,without).safe:
                changes=without; continue
            if c.action!='reduce_to': continue
            lo=int(c.new_amount*100); hi=int(forecast.stream_lookup[c.stream_id].amount*100)
            while lo<hi:
                mid=(lo+hi+1)//2; c.new_amount=Decimal(mid)/100
                if self.forecaster.simulate(profile,forecast,payments,changes).safe: lo=mid
                else: hi=mid-1
            c.new_amount=Decimal(lo)/100
        return changes
