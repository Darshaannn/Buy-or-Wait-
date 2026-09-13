export interface PaymentOptionInput {
  payment_option_id: string;
  payment_method: string;
  financing_fee: string;
  total_payable_amount: string;
  number_of_payments: number;
  first_payment_date: string;
  payment_frequency_days?: number;
  payment_amount: string;
}

export interface CommitmentInput {
  name: string;
  amount: string;
  frequency: string;
  day_of_month?: number;
  cadence_days?: number;
  category: string;
  direction: string;
  flexibility: string;
  minimum_allowed_amount?: string;
  currency: string;
}

export interface PurchaseInput {
  amount: string;
  currency: string;
  category: string;
  desired_date: string;
  request_date?: string;
  allows_partial_payment: boolean;
  description?: string;
}

export interface FinancialProfileInput {
  available_balance: string;
  minimum_balance_to_protect: string;
  home_currency: string;
  monthly_income?: string;
  income_day_of_month?: number;
  payment_methods_accepted: string[];
  max_installment_months?: number;
  protected_categories: string[];
  reducible_categories: string[];
  stoppable_categories: string[];
}

export interface AnalyzeRequest {
  purchase: PurchaseInput;
  profile: FinancialProfileInput;
  commitments: CommitmentInput[];
  payment_options: PaymentOptionInput[];
  evidence_text?: string;
}

export interface PaymentPlanItem {
  date: string;
  amount: number | string;
}

export interface SpendingChangeItem {
  stream_id: string;
  category: string;
  name: string;
  action: string;
  current_amount: number | string;
  new_amount?: number | string;
  description: string;
}

export interface ForecastDayPoint {
  date: string;
  balance: number;
  net_flow: number;
  min_safe_threshold: number;
  income_occurred: boolean;
  payment_occurred: boolean;
  payment_amount?: number;
}

export interface DecisionResponse {
  status: 'safe_now' | 'affordable_later' | 'affordable_with_plan' | 'not_affordable';
  headline: string;
  amount_safe_today: number | string;
  recommended_method: string;
  payment_plan: PaymentPlanItem[];
  earliest_full_payment_date?: string;
  spending_changes: SpendingChangeItem[];
  decision_explanation: string;
  key_reasons: string[];
  minimum_projected_balance: number | string;
  minimum_balance_required: number | string;
  projected_final_balance: number | string;
  forecast: ForecastDayPoint[];
  currency: string;
}

export interface ScenarioSummary {
  scenario_id: string;
  title: string;
  outcome: string;
  tagline: string;
  purchase_amount: string;
  currency: string;
  available_balance: string;
  minimum_safety: string;
}
