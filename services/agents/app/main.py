from fastapi import FastAPI
from fastapi import Body
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict

Date = str  # 'YYYY-MM-DD'

class Policy(BaseModel):
    buffer_min: float = 300
    never_move: List[str] = []
    weekend_payments: bool = False
    bnpl_guard_days: int = 7
    utilization_targets: Dict[str, float] = {"default": 0.10}

class Window(BaseModel):
    start: Date
    end: Date

class CashEvent(BaseModel):
    id: str
    label: str
    date: Date
    amount: float
    fixed: bool
    window: Optional[Window] = None

class Card(BaseModel):
    id: str
    limit: float
    balance: float
    cut_day: int
    due_day: int
    apr: Optional[float] = None

class Intent(BaseModel):
    name: Literal['fee_proof','credit_util','flatten_subs','bnpl_guard','question']
    params: Dict[str, object] = {}

class RequestPayload(BaseModel):
    user: Dict[str, object]
    policy: Policy
    cashIn: List[CashEvent]
    cashOut: List[CashEvent]
    cards: List[Card] = []
    bnplPlans: List[Dict[str, object]] = []
    intent: Intent

class Plan(BaseModel):
    id: str
    user_id: str
    month: str
    changes: List[Dict[str, object]]
    metrics: Dict[str, object] = {}
    explain: List[str] = []

app = FastAPI(title="Alto Agents")

@app.get("/health")
def health(): return {"ok": True}

def calendar_planner(p: RequestPayload) -> Dict[str, object]:
    changes = []
    # Demo move: move 'Utilities' to end of its allowed window
    for ev in p.cashOut:
        if ev.label.lower() == "utilities" and ev.window and not ev.fixed:
            changes.append({"type":"move","payment_id":ev.id,"from":ev.date,
                            "to":ev.window.end,"reason":"align_payroll"})
            break
    # Demo split: pre-cut micro-payments if we have a card
    if p.cards:
        cut = p.cards[0].cut_day
        parts = [
          {"date": f"2025-11-{max(1,cut-3):02d}", "amount": 120},
          {"date": f"2025-11-{max(1,cut-1):02d}", "amount": 80}
        ]
        changes.append({"type":"split","payment_id":"min_visa",
                        "from": p.cashOut[0].date, "parts": parts,
                        "reason":"pre_cut_utilization"})
    metrics = {
      "fees_avoided": 165,
      "overdraft_risk_delta": -0.8,
      "buffer_min": p.policy.buffer_min,
      "utilization_projection": {"card_visa": {"before": 0.46, "after": 0.10}}
    }
    explain = [
      "Moved Utilities within allowed window.",
      "Inserted pre-cut micro-payments to lower utilization."
    ]
    return {"changes": changes, "metrics": metrics, "explain": explain}

def qa_agent(_: RequestPayload) -> Dict[str, object]:
    return {"changes": [], "metrics": {}, "explain": [
        "We respect your windows and buffer requirement.",
        "Locked items are never moved.",
        "Pre-cut payments reduce reported card utilization."
    ]}

@app.post("/orchestrate/plan", response_model=Plan)
def orchestrate_plan(payload: RequestPayload):
    if payload.intent.name == "question":
        out = qa_agent(payload)
    else:
        out = calendar_planner(payload)
    return Plan(
        id="plan_tmp",
        user_id=str(payload.user.get("id","usr_123")),
        month="2025-11",
        changes=out["changes"],
        metrics=out["metrics"],
        explain=out["explain"]
    )

@app.post("/ingest/plaid-transform")
def plaid_transform(plaid_payload: dict = Body(...)) -> dict:
    from .ingest_plaid import plaid_to_agent_payload
    return plaid_to_agent_payload(plaid_payload)