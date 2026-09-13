"""Independent schedule/eligibility checks and a second cash-balance replay."""
from datetime import timedelta
from decimal import Decimal
from .models import Payment, SimulationResult
from .utils import add_months, money

def validate_plan(profile,request,forecast,plan,options,safe_today,earliest_full,fx):
    errors=[]; payments=plan.payments; changes=plan.spending_changes
    method='full_payment' if plan.method=='wait' else plan.method
    if method not in profile.payment_methods: errors.append('Payment preference rejects method')
    if not payments or any(p.amount<=0 or not p.amount.is_finite() or p.amount!=money(p.amount) for p in payments): errors.append('Invalid payment amounts')
    if payments!=sorted(payments,key=lambda p:p.date): errors.append('Payment dates not chronological')
    if any(p.date<request.request_date or p.date>min(request.desired_completion_date,forecast.horizon_end) for p in payments): errors.append('Payment outside allowed dates')
    if payments and (plan.start_date!=payments[0].date or plan.completion_date!=payments[-1].date): errors.append('Plan date metadata inconsistent')
    total=sum((p.amount for p in payments),Decimal(0))
    if total!=plan.total_payable: errors.append('Plan total does not reconcile')
    if plan.method=='installments':
        option=next((o for o in options if o.payment_option_id==plan.option_id),None)
        if not option or option.payment_method!='installments' or not option.payment_frequency_days or option.number_of_payments<1:
            errors.append('No valid supplied installment option')
        else:
            expected=[Payment(option.first_payment_date+timedelta(days=i*option.payment_frequency_days),option.payment_amount) for i in range(option.number_of_payments)]
            if payments!=expected or total!=option.total_payable_amount: errors.append('Installment schedule does not match supplied option')
            if option.financing_fee<0 or total!=request.requested_amount+option.financing_fee: errors.append('Installment fee does not reconcile')
        if profile.max_installment_months is None or (payments and payments[-1].date>add_months(request.request_date,profile.max_installment_months)):
            errors.append('Installment duration exceeds preference')
    elif plan.method=='partial_payment':
        if not request.allows_partial_payment or not 0<safe_today<request.requested_amount or not earliest_full:
            errors.append('Partial payment ineligible')
        elif payments!=[Payment(request.request_date,safe_today),Payment(earliest_full,request.requested_amount-safe_today)]:
            errors.append('Partial payment must follow exact two-payment contract')
    elif plan.method in {'full_payment','wait'}:
        if len(payments)!=1 or total!=request.requested_amount: errors.append('Single full payment required')
        if plan.method=='full_payment' and payments and payments[0].date!=request.request_date: errors.append('Full payment must be today')
        if plan.method=='wait' and payments and payments[0].date<=request.request_date: errors.append('Wait must start later')
    else: errors.append('Unknown recommendation method')
    if plan.method!='installments' and total!=request.requested_amount: errors.append('Request not paid in full')
    if len(changes)>3 or len({c.stream_id for c in changes})!=len(changes) or len({c.event_id for c in changes})!=len(changes): errors.append('Duplicate or excessive changes')
    for c in changes:
        s=forecast.stream_lookup.get(c.stream_id)
        if not s or c.event_id!=s.source_event_id or s.direction!='debit' or not forecast.stream_occurrences.get(c.stream_id):
            errors.append('Change references no future recurring debit'); continue
        if s.category in profile.protected: errors.append('Protected spending cannot change')
        if c.action=='stop':
            if s.category not in profile.stoppable_categories or s.flexibility not in {'stoppable','reducible_or_stoppable'} or c.new_amount is not None:
                errors.append('Stop is not permitted')
        elif c.action=='reduce_to':
            if (s.category not in profile.reducible_categories or s.flexibility not in {'reducible','reducible_or_stoppable'} or
                c.new_amount is None or not c.new_amount.is_finite() or s.minimum_allowed_amount is None or
                not s.minimum_allowed_amount<=c.new_amount<s.amount or c.new_amount!=money(c.new_amount)):
                errors.append('Reduction is not permitted or violates floor')
        else: errors.append('Unknown change action')
    if errors: raise ValueError('; '.join(errors))
    # Replay directly; deliberately does not call Forecaster.simulate.
    deltas=dict(forecast.daily_flows)
    for c in changes:
        s=forecast.stream_lookup[c.stream_id]
        for day,original_signed in forecast.stream_occurrences[c.stream_id]:
            target=Decimal(0) if c.action=='stop' else -fx.convert(c.new_amount,day,s.currency,profile.home_currency)
            deltas[day]=deltas.get(day,Decimal(0))+target-original_signed
    for p in payments: deltas[p.date]=deltas.get(p.date,Decimal(0))-p.amount
    bal=profile.current_available_balance; minimum=bal; minimum_date=request.request_date; violations=[]
    if bal<profile.minimum_balance_to_keep: violations.append((request.request_date,bal))
    day=forecast.request_date
    while day<=forecast.horizon_end:
        bal+=deltas.get(day,Decimal(0))
        if bal<minimum: minimum=bal; minimum_date=day
        if bal<profile.minimum_balance_to_keep: violations.append((day,bal))
        day+=timedelta(days=1)
    result=SimulationResult(not violations,minimum,minimum_date,bal,violations)
    if not result.safe: raise ValueError(f'Independent validation failed: minimum {minimum} on {minimum_date}')
    if plan.simulation and result!=plan.simulation: raise ValueError('Independent replay disagrees with planner simulation')
    return result
