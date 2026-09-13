"""Scenario adapter for the Buy or Wait deterministic financial engine.

Bridges between JSON API requests (or synthetic scenarios) and the deterministic
Forecaster, Planner, and Validator components.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Tuple, List, Optional
import calendar

from .engine.models import (
    Request, Profile, Event, Stream, PaymentOption, CandidatePlan, Forecast,
    SimulationResult, SpendingChange, Payment, Decision
)
from .engine.forecast import Forecaster
from .engine.planner import Planner
from .engine.validator import validate_plan
from .engine.fx import FXTable
from .engine.utils import D, money, plan_decimal
from .schemas import (
    AnalyzeRequest, DecisionResponse, PaymentPlanItem, SpendingChangeItem,
    ForecastDayPoint
)

ZERO = Decimal("0")


class ScenarioEngine:
    """Executes deterministic 90-day cash flow simulation, plan search, and validation for an AnalyzeRequest."""

    def __init__(self):
        # Empty FX table defaults to 1.0 for same-currency operations
        self.fx = FXTable()
        self.forecaster = Forecaster(self.fx)
        self.planner = Planner(self.forecaster)

    def analyze(self, req: AnalyzeRequest) -> DecisionResponse:
        today = req.purchase.request_date or date.today()
        desired_date = req.purchase.desired_date
        if desired_date < today:
            desired_date = today

        # 1. Build Internal Profile
        profile = Profile(
            user_id="portfolio_user",
            home_currency=req.profile.home_currency.upper(),
            current_available_balance=req.profile.available_balance,
            minimum_balance_to_keep=req.profile.minimum_balance_to_protect,
            financial_priorities=set(),
            protected=set(c.lower() for c in req.profile.protected_categories),
            reducible_categories=set(c.lower() for c in req.profile.reducible_categories),
            stoppable_categories=set(c.lower() for c in req.profile.stoppable_categories),
            payment_methods=set(req.profile.payment_methods_accepted),
            max_installment_months=req.profile.max_installment_months,
        )

        # 2. Build Internal Request
        request = Request(
            request_id="req_portfolio",
            user_id="portfolio_user",
            request_date=today,
            request_type="purchase",
            requested_amount=req.purchase.amount,
            desired_completion_date=desired_date,
            allows_partial_payment=req.purchase.allows_partial_payment,
            request_text=req.purchase.description or "",
        )

        # 3. Build Historical & Future Streams from Commitments & Monthly Income
        # We synthesize known regular streams directly into the Forecast
        horizon_end = today + timedelta(days=90)
        forecast = Forecast(
            request_date=today,
            horizon_end=horizon_end,
            daily_flows={},
            stream_occurrences={},
            stream_lookup={},
            warnings=[],
            home_currency=profile.home_currency,
        )

        # Monthly Income stream
        if req.profile.monthly_income and req.profile.monthly_income > ZERO:
            inc_day = req.profile.income_day_of_month or 1
            inc_stream_id = "stream_salary"
            inc_stream = Stream(
                stream_id=inc_stream_id,
                category="salary",
                direction="credit",
                flexibility="fixed",
                event_type="salary",
                source_event_id="evt_salary",
                amount=req.profile.monthly_income,
                currency=profile.home_currency,
                last_date=today - timedelta(days=20),
                monthly_day=inc_day,
                description="Monthly Primary Income",
            )
            forecast.stream_lookup[inc_stream_id] = inc_stream
            occ = []
            cur_d = today
            # Generate forward monthly income dates
            while cur_d <= horizon_end:
                y, m = cur_d.year, cur_d.month
                max_day = calendar.monthrange(y, m)[1]
                target_d = date(y, m, min(inc_day, max_day))
                if target_d >= today and target_d <= horizon_end:
                    if target_d not in [d for d, _ in occ]:
                        amt = req.profile.monthly_income
                        forecast.daily_flows[target_d] = forecast.daily_flows.get(target_d, ZERO) + amt
                        occ.append((target_d, amt))
                # advance month
                if m == 12:
                    cur_d = date(y + 1, 1, 1)
                else:
                    cur_d = date(y, m + 1, 1)
            forecast.stream_occurrences[inc_stream_id] = occ

        # Commitment streams
        for i, c in enumerate(req.commitments, 1):
            sid = f"stream_commit_{i}"
            c_cat = c.category.lower()
            c_flex = c.flexibility.lower()
            if c_flex not in {'fixed', 'reducible', 'stoppable', 'reducible_or_stoppable'}:
                c_flex = 'fixed'

            stream = Stream(
                stream_id=sid,
                category=c_cat,
                direction="debit",
                flexibility=c_flex,
                event_type="commitment",
                source_event_id=f"evt_commit_{i}",
                amount=c.amount,
                currency=c.currency.upper(),
                last_date=today - timedelta(days=15),
                monthly_day=c.day_of_month if c.frequency == "monthly" else None,
                cadence_days=c.cadence_days or (7 if c.frequency == "weekly" else (1 if c.frequency == "daily" else None)),
                minimum_allowed_amount=c.minimum_allowed_amount,
                description=c.name,
            )
            forecast.stream_lookup[sid] = stream
            occ = []

            # Populate dates
            if c.frequency == "monthly" and c.day_of_month:
                cur_d = today
                while cur_d <= horizon_end:
                    y, m = cur_d.year, cur_d.month
                    max_day = calendar.monthrange(y, m)[1]
                    target_d = date(y, m, min(c.day_of_month, max_day))
                    if target_d >= today and target_d <= horizon_end:
                        if target_d not in [d for d, _ in occ]:
                            debit_signed = -c.amount
                            forecast.daily_flows[target_d] = forecast.daily_flows.get(target_d, ZERO) + debit_signed
                            occ.append((target_d, debit_signed))
                    if m == 12:
                        cur_d = date(y + 1, 1, 1)
                    else:
                        cur_d = date(y, m + 1, 1)
            else:
                cadence = stream.cadence_days or 30
                d = today + timedelta(days=cadence // 2)
                while d <= horizon_end:
                    debit_signed = -c.amount
                    forecast.daily_flows[d] = forecast.daily_flows.get(d, ZERO) + debit_signed
                    occ.append((d, debit_signed))
                    d += timedelta(days=cadence)

            forecast.stream_occurrences[sid] = occ

        # 4. Build Payment Options
        options: List[PaymentOption] = []
        for opt in req.payment_options:
            options.append(
                PaymentOption(
                    payment_option_id=opt.payment_option_id,
                    request_id=request.request_id,
                    payment_method=opt.payment_method,
                    financing_fee=opt.financing_fee,
                    total_payable_amount=opt.total_payable_amount,
                    number_of_payments=opt.number_of_payments,
                    first_payment_date=opt.first_payment_date,
                    payment_frequency_days=opt.payment_frequency_days,
                    payment_amount=opt.payment_amount,
                )
            )

        # 5. Core Deterministic Engine Execution
        safe_today = self.forecaster.amount_safe_today(profile, request, forecast)
        earliest_full = self.forecaster.earliest_full_date(profile, request, forecast)
        plan = self.planner.choose(profile, request, forecast, options, safe_today, earliest_full)

        # 6. Validate Plan if found
        if plan:
            validate_plan(profile, request, forecast, plan, options, safe_today, earliest_full, self.fx)

        # 7. Generate Daily 90-Day Forecast Points for Charting
        chart_points = self._generate_forecast_series(profile, forecast, plan)

        # 8. Shape Decision Response
        return self._format_response(profile, request, safe_today, earliest_full, plan, chart_points, forecast)

    def _generate_forecast_series(
        self, profile: Profile, forecast: Forecast, plan: Optional[CandidatePlan]
    ) -> List[ForecastDayPoint]:
        adjusted = self.forecaster.adjusted_flows(forecast, plan.spending_changes if plan else [])
        pay_map = {}
        if plan:
            for p in plan.payments:
                pay_map[p.date] = pay_map.get(p.date, ZERO) + p.amount

        bal = profile.current_available_balance
        d = forecast.request_date
        points = []

        while d <= forecast.horizon_end:
            flow = adjusted.get(d, ZERO)
            pay = pay_map.get(d, ZERO)
            bal += flow
            bal -= pay
            points.append(
                ForecastDayPoint(
                    date=d.isoformat(),
                    balance=bal,
                    net_flow=flow,
                    min_safe_threshold=profile.minimum_balance_to_keep,
                    income_occurred=(flow > ZERO),
                    payment_occurred=(pay > ZERO),
                    payment_amount=pay if pay > ZERO else None,
                )
            )
            d += timedelta(days=1)
        return points

    def _format_response(
        self,
        profile: Profile,
        request: Request,
        safe_today: Decimal,
        earliest_full: Optional[date],
        plan: Optional[CandidatePlan],
        chart_points: List[ForecastDayPoint],
        forecast: Forecast,
    ) -> DecisionResponse:
        min_proj = min(p.balance for p in chart_points) if chart_points else profile.current_available_balance
        final_bal = chart_points[-1].balance if chart_points else profile.current_available_balance
        cur = profile.home_currency

        if not plan:
            status = "not_affordable"
            headline = "NOT SAFE YET"
            rec_method = "not_recommended"
            explanation = (
                f"No eligible payment structure completes payment by {request.desired_completion_date} "
                f"while protecting {cur} {plan_decimal(profile.minimum_balance_to_keep)}. "
                f"Safe amount today without overdraft risk: {cur} {plan_decimal(safe_today)}."
            )
            key_reasons = [
                f"Making this purchase would breach your {cur} {plan_decimal(profile.minimum_balance_to_keep)} emergency floor.",
                f"Safe spending headroom today is only {cur} {plan_decimal(safe_today)}.",
                f"Consider waiting until additional cash reserves accumulate or reducing discretionary expenses.",
            ]
            spending_items = []
            payment_items = []
            earliest_str = earliest_full.isoformat() if earliest_full else None
        else:
            if plan.spending_changes or plan.method in {'partial_payment', 'installments'}:
                status = "affordable_with_plan"
                headline = "USE A PAYMENT PLAN" if plan.method in {'partial_payment', 'installments'} else "AFFORDABLE WITH BUDGET TWEAKS"
            elif plan.method == 'wait':
                status = "affordable_later"
                headline = "BETTER TO WAIT"
            else:
                status = "safe_now"
                headline = "SAFE TO BUY NOW"

            rec_method = plan.method
            earliest_str = earliest_full.isoformat() if earliest_full else None

            # Payment items
            payment_items = [PaymentPlanItem(date=p.date.isoformat(), amount=p.amount) for p in plan.payments]

            # Spending changes
            spending_items = []
            for c in plan.spending_changes:
                st = forecast.stream_lookup.get(c.stream_id)
                readable_name = st.description if st and st.description else c.event_id
                cat = st.category if st else "other"
                orig_amt = st.amount if st else Decimal("0.00")
                action_text = (
                    f"Pause {readable_name} (save {cur} {plan_decimal(orig_amt)})"
                    if c.action == "stop"
                    else f"Reduce {readable_name} from {cur} {plan_decimal(orig_amt)} to {cur} {plan_decimal(c.new_amount)}"
                )
                spending_items.append(
                    SpendingChangeItem(
                        stream_id=c.stream_id,
                        category=cat,
                        name=readable_name,
                        action=c.action,
                        current_amount=orig_amt,
                        new_amount=c.new_amount,
                        description=action_text,
                    )
                )

            # Decision explanation
            explanation = (
                f"Pay {cur} {plan_decimal(plan.total_payable)} using {plan.method.replace('_', ' ')}. "
                f"Projected minimum balance is {cur} {plan_decimal(min_proj)}, maintaining your "
                f"{cur} {plan_decimal(profile.minimum_balance_to_keep)} safety buffer throughout 90 days."
            )

            # Key reasons (derived deterministically)
            key_reasons = []
            key_reasons.append(
                f"Safety floor of {cur} {plan_decimal(profile.minimum_balance_to_keep)} remains protected (lowest point: {cur} {plan_decimal(min_proj)})."
            )
            if plan.method == "full_payment":
                key_reasons.append("Sufficient cash headroom exists today to complete full payment immediately.")
            elif plan.method == "wait":
                key_reasons.append(f"Waiting until {plan.start_date.strftime('%d %b %Y')} allows scheduled cash inflows to arrive first.")
            elif plan.method == "partial_payment":
                key_reasons.append(f"Pay {cur} {plan_decimal(safe_today)} safely today; remainder follows on {earliest_full.strftime('%d %b %Y') if earliest_full else 'later date'}.")
            elif plan.method == "installments":
                key_reasons.append(f"Spreading into {len(plan.payments)} payments keeps monthly balance safely above minimum threshold.")

            if plan.spending_changes:
                key_reasons.append(f"{len(plan.spending_changes)} discretionary budget adjustment(s) required to maintain safety buffer.")
            else:
                key_reasons.append("No recurring spending cuts or lifestyle compromises required.")

        return DecisionResponse(
            status=status,
            headline=headline,
            amount_safe_today=safe_today,
            recommended_method=rec_method,
            payment_plan=payment_items,
            earliest_full_payment_date=earliest_str,
            spending_changes=spending_items,
            decision_explanation=explanation,
            key_reasons=key_reasons,
            minimum_projected_balance=min_proj,
            minimum_balance_required=profile.minimum_balance_to_keep,
            projected_final_balance=final_bal,
            forecast=chart_points,
            currency=cur,
        )
