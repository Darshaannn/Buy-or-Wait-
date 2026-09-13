"""Pydantic schemas for the Buy or Wait portfolio FastAPI application."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PaymentOptionInput(BaseModel):
    payment_option_id: str
    payment_method: str = "installments"
    financing_fee: Decimal = Decimal("0.00")
    total_payable_amount: Decimal
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int] = 30
    payment_amount: Decimal


class CommitmentInput(BaseModel):
    name: str
    amount: Decimal
    frequency: str = "monthly"  # monthly, daily, weekly
    day_of_month: Optional[int] = 1
    cadence_days: Optional[int] = None
    category: str = "other"  # rent, utilities, groceries, transport, subscription, loan, dining
    direction: str = "debit"
    flexibility: str = "fixed"  # fixed, reducible, stoppable, reducible_or_stoppable
    minimum_allowed_amount: Optional[Decimal] = None
    currency: str = "INR"


class PurchaseInput(BaseModel):
    amount: Decimal
    currency: str = "INR"
    category: str = "general"
    desired_date: date
    request_date: Optional[date] = None
    allows_partial_payment: bool = True
    description: Optional[str] = "Desired purchase"


class FinancialProfileInput(BaseModel):
    available_balance: Decimal
    minimum_balance_to_protect: Decimal
    home_currency: str = "INR"
    monthly_income: Optional[Decimal] = None
    income_day_of_month: Optional[int] = 1
    income_currency: Optional[str] = "INR"
    payment_methods_accepted: List[str] = Field(default_factory=lambda: ["full_payment", "partial_payment", "installments"])
    max_installment_months: Optional[int] = 6
    protected_categories: List[str] = Field(default_factory=list)
    reducible_categories: List[str] = Field(default_factory=list)
    stoppable_categories: List[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    purchase: PurchaseInput
    profile: FinancialProfileInput
    commitments: List[CommitmentInput] = Field(default_factory=list)
    payment_options: List[PaymentOptionInput] = Field(default_factory=list)
    evidence_text: Optional[str] = None


class PaymentPlanItem(BaseModel):
    date: str
    amount: Decimal


class SpendingChangeItem(BaseModel):
    stream_id: str
    category: str
    name: str
    action: str  # stop, reduce_to
    current_amount: Decimal
    new_amount: Optional[Decimal] = None
    description: str


class ForecastDayPoint(BaseModel):
    date: str
    balance: Decimal
    net_flow: Decimal
    min_safe_threshold: Decimal
    income_occurred: bool = False
    payment_occurred: bool = False
    payment_amount: Optional[Decimal] = None


class DecisionResponse(BaseModel):
    status: str  # safe_now, affordable_later, affordable_with_plan, not_affordable
    headline: str  # "SAFE TO BUY NOW", "BETTER TO WAIT", "USE A PAYMENT PLAN", "NOT SAFE YET"
    amount_safe_today: Decimal
    recommended_method: str  # full_payment, wait, partial_payment, installments, not_recommended
    payment_plan: List[PaymentPlanItem] = Field(default_factory=list)
    earliest_full_payment_date: Optional[str] = None
    spending_changes: List[SpendingChangeItem] = Field(default_factory=list)
    decision_explanation: str
    key_reasons: List[str] = Field(default_factory=list)
    minimum_projected_balance: Decimal
    minimum_balance_required: Decimal
    projected_final_balance: Decimal
    forecast: List[ForecastDayPoint] = Field(default_factory=list)
    currency: str = "INR"


class ScenarioSummary(BaseModel):
    scenario_id: str
    title: str
    outcome: str
    tagline: str
    purchase_amount: Decimal
    currency: str
    available_balance: Decimal
    minimum_safety: Decimal


class ScenarioDetail(BaseModel):
    scenario_id: str
    title: str
    outcome: str
    tagline: str
    data: AnalyzeRequest
