# RESUME & INTERVIEW BRIEF — BUY OR WAIT?

## 1-Line Project Pitch
> An AI-assisted financial decision engine that uses vision LLMs for unstructured evidence extraction while enforcing deterministic Python cash-flow simulation to protect user savings buffers.

---

## 3 Resume Bullets

* **Engineered a 90-day cash-flow simulation engine in Python & FastAPI**, evaluating forward account balances against emergency safety floors to generate verified optimal payment plans (`full`, `wait`, `installments`, `partial`).
* **Architected an AI-isolation pattern where vision/LLM models extract structured financial evidence** while deterministic simulation and validation control affordability decisions, isolating mathematical calculations from LLM hallucination risk.
* **Built a responsive fintech dashboard in React, TypeScript, and Recharts**, visualizing 90-day balance trajectories, payment schedules, and automated budget adjustments across 6 synthetic financial scenarios.

---

## 60-Second Interview Story (Elevator Pitch)

### 1. The Problem
Checking an account balance before making a large purchase is dangerously misleading: it completely ignores pending debits, upcoming rent, loan EMIs, and the emergency cash buffer someone needs for unforeseen crises.

### 2. The Architecture
We built **Buy or Wait?** with a clean decoupled architecture:
1. **Frontend**: React + TypeScript providing a calm, executive fintech dashboard with 90-day cash-flow forecasting charts.
2. **Backend**: FastAPI orchestrating a multi-stage deterministic pipeline: stream recurrence detection, 90-day balance simulation, candidate plan search, and an independent validator.
3. **AI Layer**: Confined strictly to interpreting unstructured receipts and messages.

### 3. Hardest Technical Challenge
Balancing user payment flexibility against strict safety floors. If a user cannot pay today, we explore whether waiting for their next payday, splitting into installments, or making targeted discretionary budget cuts (like pausing a subscription or trimming dining out) allows safe completion without ever breaching their emergency reserve.

### 4. Key Design Decision
**Deterministic Financial Core**: Financial decisions can never be delegated to an LLM. By isolating the AI to evidence parsing and keeping the financial simulation strictly mathematical in Python, we achieved reproducible, verifiable decisions without risking fabricated numbers.

### 5. The Result
An end-to-end full-stack portfolio product with 67 passing unit & integration tests, clean REST API documentation, and sub-50ms deterministic decision latency.
