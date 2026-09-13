import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Clock,
  CreditCard,
  AlertTriangle,
  Sparkles,
  CheckCircle,
  TrendingDown,
  RefreshCw,
} from 'lucide-react';
import { fetchScenarios, fetchScenarioDetail, analyzePurchase } from './api';
import type { ScenarioSummary, AnalyzeRequest, DecisionResponse } from './types';
import { CashFlowChart } from './CashFlowChart';

export const App: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('scenario_01_safe_now');
  const [formData, setFormData] = useState<AnalyzeRequest | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Initial load: fetch scenarios and select the first one
  useEffect(() => {
    async function init() {
      try {
        setLoading(true);
        const list = await fetchScenarios();
        setScenarios(list);
        if (list.length > 0) {
          const firstId = list[0].scenario_id;
          setSelectedScenarioId(firstId);
          const detail = await fetchScenarioDetail(firstId);
          setFormData(detail.data);
          // Run analysis immediately for recruiter instant 15-sec demo
          const result = await analyzePurchase(detail.data);
          setDecision(result);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to initialize application');
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Handler when user picks an example scenario
  const handleSelectScenario = async (scenarioId: string) => {
    try {
      setSelectedScenarioId(scenarioId);
      setAnalyzing(true);
      setError(null);
      const detail = await fetchScenarioDetail(scenarioId);
      setFormData(detail.data);
      const result = await analyzePurchase(detail.data);
      setDecision(result);
    } catch (err: any) {
      setError(err.message || 'Failed to load scenario');
    } finally {
      setAnalyzing(false);
    }
  };

  // Handler when user clicks "Analyze Financial Feasibility"
  const handleAnalyzeCustom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData) return;
    try {
      setAnalyzing(true);
      setError(null);
      const result = await analyzePurchase(formData);
      setDecision(result);
    } catch (err: any) {
      setError(err.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const getStatusBadge = (outcome: string) => {
    switch (outcome) {
      case 'safe_now':
        return <span className="sc-badge badge-safe">Safe Now</span>;
      case 'affordable_later':
        return <span className="sc-badge badge-wait">Wait / Inflow</span>;
      case 'affordable_with_plan':
        return <span className="sc-badge badge-plan">Plan / Budget</span>;
      default:
        return <span className="sc-badge badge-danger">Not Safe</span>;
    }
  };

  return (
    <div className="app-container">
      {/* Top Nav */}
      <header className="top-nav">
        <div className="brand-area">
          <div>
            <div className="brand-title">Buy or Wait?</div>
            <div className="brand-tagline">Know what you can afford before you spend.</div>
          </div>
        </div>
        <div className="nav-links">
          <a
            href="https://github.com/Darshaannn/Buy-or-Wait-"
            target="_blank"
            rel="noopener noreferrer"
            className="nav-btn"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
            </svg>
            GitHub
          </a>
        </div>
      </header>

      {/* Hero Header */}
      <section className="hero-section">
        <h1 className="hero-headline">Should you buy it now or wait?</h1>
        <p className="hero-subtitle">
          See how a purchase could affect your next 90 days before you commit.
        </p>
      </section>

      {/* Try an Example Scenario Cards */}
      <section className="scenario-selector-wrap">
        <div className="selector-header">
          <span className="selector-title">Try an example scenario (Instant Recruiter Demo)</span>
          {analyzing && (
            <span style={{ fontSize: 12, color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={12} className="spin" /> Simulating 90 days...
            </span>
          )}
        </div>
        <div className="scenarios-grid">
          {scenarios.map((sc) => {
            // Recruiter friendly concise labels
            const shortTitles: Record<string, string> = {
              scenario_01_safe_now: 'Freelancer Laptop',
              scenario_02_affordable_later: 'Home Audio Upgrade',
              scenario_03_installments: 'Office Setup',
              scenario_04_partial_payment: 'Certification Exam',
              scenario_05_spending_reduction: 'Fitness Bike',
              scenario_06_not_affordable: 'Luxury Vacation',
            };
            const displayTitle = shortTitles[sc.scenario_id] || sc.title;

            return (
              <button
                key={sc.scenario_id}
                onClick={() => handleSelectScenario(sc.scenario_id)}
                className={`scenario-card ${selectedScenarioId === sc.scenario_id ? 'active' : ''}`}
              >
                <div className="sc-name">{displayTitle}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {sc.currency} {Number(sc.purchase_amount).toLocaleString()}
                </div>
                {getStatusBadge(sc.outcome)}
              </button>
            );
          })}
        </div>
      </section>

      {error && (
        <div style={{ padding: 16, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, color: '#b91c1c', marginBottom: 24 }}>
          <strong>Error: </strong> {error}
        </div>
      )}

      {/* Workspace Grid */}
      <div className="workspace-grid">
        {/* Left: Financial Input Form */}
        <div className="form-panel">
          <div className="panel-title">
            <span>Configure Scenario</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 400 }}>Customizable Inputs</span>
          </div>

          {formData && (
            <form onSubmit={handleAnalyzeCustom}>
              {/* Purchase Details */}
              <div className="section-label">1. Desired Purchase</div>
              <div className="form-group">
                <label className="form-label">Purchase Amount ({formData.purchase.currency})</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.purchase.amount}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      purchase: { ...formData.purchase, amount: e.target.value },
                    })
                  }
                  required
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.purchase.category}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        purchase: { ...formData.purchase, category: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Desired Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={formData.purchase.desired_date}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        purchase: { ...formData.purchase, desired_date: e.target.value },
                      })
                    }
                    required
                  />
                </div>
              </div>

              <div className="section-divider" />

              {/* Financial Profile */}
              <div className="section-label">2. Current Finances</div>
              <div className="form-group">
                <label className="form-label">Available Bank Balance</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.profile.available_balance}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      profile: { ...formData.profile, available_balance: e.target.value },
                    })
                  }
                  required
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Safety Floor to Protect</label>
                  <input
                    type="number"
                    className="form-input"
                    value={formData.profile.minimum_balance_to_protect}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        profile: { ...formData.profile, minimum_balance_to_protect: e.target.value },
                      })
                    }
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Monthly Income</label>
                  <input
                    type="number"
                    className="form-input"
                    value={formData.profile.monthly_income || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        profile: { ...formData.profile, monthly_income: e.target.value },
                      })
                    }
                  />
                </div>
              </div>

              <div className="section-divider" />

              {/* Commitments Overview */}
              <div className="section-label">3. Monthly Commitments ({formData.commitments.length})</div>
              <div>
                {formData.commitments.map((c, i) => (
                  <div key={i} className="commitment-item">
                    <span className="commit-name">{c.name}</span>
                    <span className="commit-amt">
                      {c.currency} {Number(c.amount).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>

              <button type="submit" className="analyze-btn" disabled={analyzing}>
                {analyzing ? 'Evaluating Cash Flow...' : 'Re-Analyze Scenario'}
              </button>
            </form>
          )}
        </div>

        {/* Right: Decision and 90-Day Results */}
        <div className="results-panel">
          {decision && (
            <>
              {/* Decision Hero */}
              <div className={`decision-hero ${decision.status}`}>
                <div className={`decision-status-tag status-${decision.status}`}>
                  {decision.status === 'safe_now' && <ShieldCheck size={14} />}
                  {decision.status === 'affordable_later' && <Clock size={14} />}
                  {decision.status === 'affordable_with_plan' && <CreditCard size={14} />}
                  {decision.status === 'not_affordable' && <AlertTriangle size={14} />}
                  {decision.status.replace(/_/g, ' ')}
                </div>
                <h2 className="decision-headline">{decision.headline}</h2>
                <p className="decision-subheading">
                  {decision.status === 'safe_now' && (
                    <>
                      You can make this purchase today without crossing your protected savings buffer of{' '}
                      <strong>{decision.currency} {Number(decision.minimum_balance_required).toLocaleString()}</strong>.
                    </>
                  )}
                  {decision.status === 'affordable_later' && (
                    <>
                      Waiting until{' '}
                      <strong>
                        {decision.earliest_full_payment_date
                          ? new Date(decision.earliest_full_payment_date).toLocaleDateString('en-US', {
                              day: 'numeric',
                              month: 'short',
                            })
                          : 'your next income arrives'}
                      </strong>{' '}
                      keeps your 90-day cash flow above your safety threshold.
                    </>
                  )}
                  {decision.status === 'affordable_with_plan' && (
                    <>
                      Splitting this purchase reduces short-term pressure on your available balance while protecting your buffer.
                    </>
                  )}
                  {decision.status === 'not_affordable' && (
                    <>
                      This purchase would push your projected balance below your protected minimum of{' '}
                      <strong>{decision.currency} {Number(decision.minimum_balance_required).toLocaleString()}</strong>.
                    </>
                  )}
                </p>
              </div>

              {/* 4 KPI Cards */}
              <div className="kpi-grid">
                <div className="kpi-card">
                  <div className="kpi-label">Safe Today</div>
                  <div className="kpi-value">
                    {decision.currency} {Number(decision.amount_safe_today).toLocaleString()}
                  </div>
                  <div className="kpi-sub">Available without buffer risk</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-label">Recommended Method</div>
                  <div className="kpi-value" style={{ fontSize: 18, textTransform: 'capitalize' }}>
                    {decision.recommended_method.replace(/_/g, ' ')}
                  </div>
                  <div className="kpi-sub">Optimal cost & timing</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-label">Earliest Full Payment</div>
                  <div className="kpi-value" style={{ fontSize: 20 }}>
                    {decision.earliest_full_payment_date
                      ? new Date(decision.earliest_full_payment_date).toLocaleDateString('en-US', {
                          day: 'numeric',
                          month: 'short',
                        })
                      : 'N/A'}
                  </div>
                  <div className="kpi-sub">Earliest 100% capacity date</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-label">Safety Floor Protected</div>
                  <div className="kpi-value">
                    {decision.currency} {Number(decision.minimum_balance_required).toLocaleString()}
                  </div>
                  <div className="kpi-sub">
                    Lowest point: {decision.currency} {Number(decision.minimum_projected_balance).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* 90-Day Cash Flow Visualization */}
              <div className="chart-card">
                <div className="card-title-row">
                  <div>
                    <div className="card-title">90-Day Cash-Flow Projection</div>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                      Simulated daily bank balance vs. minimum required safety threshold
                    </div>
                  </div>
                  <div className="chart-legend">
                    <div>
                      <span className="legend-dot" style={{ background: '#2563eb' }} />
                      Projected Balance
                    </div>
                    <div>
                      <span className="legend-dot" style={{ background: '#ef4444' }} />
                      Safety Floor
                    </div>
                  </div>
                </div>
                <CashFlowChart
                  data={decision.forecast}
                  minBuffer={Number(decision.minimum_balance_required)}
                  currency={decision.currency}
                />
              </div>

              {/* Payment Timeline (if plan has payments) */}
              {decision.payment_plan && decision.payment_plan.length > 0 && (
                <div className="timeline-card">
                  <div className="card-title" style={{ marginBottom: 12 }}>
                    Payment Plan Schedule ({decision.payment_plan.length} installment{decision.payment_plan.length > 1 ? 's' : ''})
                  </div>
                  <div className="timeline-track">
                    {decision.payment_plan.map((p, idx) => (
                      <div key={idx} className="timeline-node">
                        <div className="node-date">
                          Payment #{idx + 1} &bull;{' '}
                          {new Date(p.date).toLocaleDateString('en-US', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                          })}
                        </div>
                        <div className="node-amount">
                          {decision.currency} {Number(p.amount).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Spending Changes Card (if required) */}
              <div className="spending-card">
                <div className="card-title" style={{ marginBottom: 12 }}>
                  Budget Adjustments Required
                </div>
                {decision.spending_changes && decision.spending_changes.length > 0 ? (
                  <div>
                    {decision.spending_changes.map((c, idx) => (
                      <div key={idx} className="change-item">
                        <div>
                          <div className="change-title">{c.name}</div>
                          <div className="change-desc">{c.description}</div>
                        </div>
                        <TrendingDown size={18} color="#854d0e" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#047857', fontSize: 14 }}>
                    <CheckCircle size={18} />
                    <span>No spending cuts required. Your regular budget remains completely untouched.</span>
                  </div>
                )}
              </div>

              {/* Why this recommendation */}
              <div className="explanation-card">
                <div className="card-title">Why this recommendation?</div>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8 }}>
                  {decision.decision_explanation}
                </p>
                <ul className="reasons-list">
                  {decision.key_reasons.map((reason, idx) => (
                    <li key={idx} className="reason-item">
                      <div className="reason-bullet" />
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* AI Evidence Feature Demo */}
              <div className="ai-evidence-card">
                <div className="ai-pill">
                  <Sparkles size={12} /> AI Evidence Intelligence
                </div>
                <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>
                  Unstructured Fact Extraction vs. Deterministic Decision Engine
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
                  In the complete product architecture, AI (vision / LLM) parses unstructured receipts,
                  salary notifications, and email threads to extract confirmed monetary facts into structured
                  events. <strong>LLM-generated evidence is strictly isolated from deterministic affordability logic</strong>,
                  preventing model hallucinations from directly affecting financial recommendations.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
