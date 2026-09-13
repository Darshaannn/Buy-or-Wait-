from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Decimal
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str = ''

@dataclass
class Profile:
    user_id: str
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: set = field(default_factory=set)
    protected: set = field(default_factory=set)
    reducible_categories: set = field(default_factory=set)
    stoppable_categories: set = field(default_factory=set)
    payment_methods: set = field(default_factory=lambda:{'full_payment'})
    max_installment_months: int | None = None

@dataclass
class Event:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Decimal | None
    currency: str
    event_date: date
    settlement_date: date
    status: str
    linked_event_id: str = ''
    flexibility: str = 'fixed'
    minimum_allowed_amount: Decimal | None = None
    evidence_source: str = 'ledger'

@dataclass
class Stream:
    stream_id: str
    category: str
    direction: str
    flexibility: str
    event_type: str
    source_event_id: str
    amount: Decimal
    currency: str
    last_date: date
    cadence_days: int | None = None
    monthly_day: int | None = None
    minimum_allowed_amount: Decimal | None = None
    description: str = ''

@dataclass
class Payment:
    date: date
    amount: Decimal

@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: Decimal
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: int | None
    financing_fee: Decimal
    total_payable_amount: Decimal

@dataclass
class SpendingChange:
    action: str
    event_id: str
    stream_id: str
    new_amount: Decimal | None = None

@dataclass
class Forecast:
    request_date: date
    horizon_end: date
    daily_flows: dict = field(default_factory=dict)
    stream_lookup: dict = field(default_factory=dict)
    stream_occurrences: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    home_currency: str = ''

@dataclass
class SimulationResult:
    safe: bool
    minimum_projected_balance: Decimal
    minimum_balance_date: date
    final_balance: Decimal
    violations: list = field(default_factory=list)

@dataclass
class CandidatePlan:
    method: str
    payments: list[Payment]
    total_payable: Decimal
    completion_date: date
    start_date: date
    option_id: str = ''
    spending_changes: list[SpendingChange] = field(default_factory=list)
    simulation: SimulationResult | None = None

@dataclass
class Decision:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str
