"""FastAPI application for Buy or Wait financial decision engine."""
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AnalyzeRequest, DecisionResponse, ScenarioSummary, ScenarioDetail
)
from .scenario_engine import ScenarioEngine

app = FastAPI(
    title="Buy or Wait? — AI-Assisted Financial Decision Engine",
    description="Deterministic 90-day cash flow simulation, minimum balance protection, and optimal payment plan search.",
    version="1.0.0",
)

# CORS configuration: configurable via FRONTEND_ORIGIN environment variable
frontend_origin = os.getenv("FRONTEND_ORIGIN")
origins = [origin.strip() for origin in frontend_origin.split(",")] if frontend_origin else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global validation error handler: consistent structured JSON without raw stack traces
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        errors.append(f"{loc}: {err.get('msg', 'invalid input')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "INVALID_INPUT",
            "message": "; ".join(errors) if errors else "Invalid request data format",
        },
    )

ENGINE = ScenarioEngine()
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_PATH = DATA_DIR / "demo_scenarios.json"


def load_scenarios() -> List[dict]:
    if not SCENARIOS_PATH.exists():
        return []
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "buy-or-wait-api",
        "version": "1.0.0",
    }


@app.get("/api/scenarios", response_model=List[ScenarioSummary])
def list_scenarios():
    raw = load_scenarios()
    summaries = []
    for s in raw:
        data = s["data"]
        summaries.append(
            ScenarioSummary(
                scenario_id=s["scenario_id"],
                title=s["title"],
                outcome=s["outcome"],
                tagline=s["tagline"],
                purchase_amount=data["purchase"]["amount"],
                currency=data["purchase"]["currency"],
                available_balance=data["profile"]["available_balance"],
                minimum_safety=data["profile"]["minimum_balance_to_protect"],
            )
        )
    return summaries


@app.get("/api/scenarios/{scenario_id}", response_model=ScenarioDetail)
def get_scenario(scenario_id: str):
    raw = load_scenarios()
    for s in raw:
        if s["scenario_id"] == scenario_id:
            return ScenarioDetail(
                scenario_id=s["scenario_id"],
                title=s["title"],
                outcome=s["outcome"],
                tagline=s["tagline"],
                data=AnalyzeRequest(**s["data"]),
            )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "NOT_FOUND", "message": f"Scenario '{scenario_id}' not found"}
    )


@app.post("/api/analyze", response_model=DecisionResponse)
def analyze_purchase(req: AnalyzeRequest):
    try:
        decision = ENGINE.analyze(req)
        return decision
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "INVALID_INPUT", "message": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "ANALYSIS_ERROR", "message": "Failed to complete 90-day simulation."},
        )
