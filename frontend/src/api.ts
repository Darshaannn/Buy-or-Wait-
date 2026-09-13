import type { AnalyzeRequest, DecisionResponse, ScenarioSummary } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) throw new Error('API Health check failed');
  return res.json();
}

export async function fetchScenarios(): Promise<ScenarioSummary[]> {
  const res = await fetch(`${API_BASE_URL}/api/scenarios`);
  if (!res.ok) throw new Error('Failed to load scenarios');
  return res.json();
}

export async function fetchScenarioDetail(scenarioId: string): Promise<{ scenario_id: string; title: string; data: AnalyzeRequest }> {
  const res = await fetch(`${API_BASE_URL}/api/scenarios/${scenarioId}`);
  if (!res.ok) throw new Error(`Failed to load scenario ${scenarioId}`);
  return res.json();
}

export async function analyzePurchase(payload: AnalyzeRequest): Promise<DecisionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(err.message || err.detail || 'Analysis failed');
  }
  return res.json();
}
