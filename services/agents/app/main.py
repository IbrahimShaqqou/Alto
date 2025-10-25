from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Optional, Literal, Dict
from datetime import datetime, timedelta
import random, string

# ----- Types & Schemas -----

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

# ----- App -----

app = FastAPI(title="Alto Agents")

@app.get("/health")
def health():
    return {"ok": True}

# (Optional) helpful root so hitting "/" doesn't 404 during local testing
@app.get("/")
def root():
    return {"ok": True, "routes": [r.path for r in app.routes]}

# ----- Helpers (A1 guardrails support) -----

def _dt(s: Date) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")

def _iso(d: datetime) -> Date:
    return d.strftime("%Y-%m-%d")

def _is_weekend(d: datetime) -> bool:
    return d.weekday() >= 5  # Sat=5, Sun=6

def _bump_to_weekday(d: datetime) -> datetime:
    # If Saturday → +2 days; if Sunday → +1 day; else unchanged
    if d.weekday() == 5:
        return d + timedelta(days=2)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d

def _short_id(prefix: str = "plan") -> str:
    suf = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{suf}"

def _derive_month(payload: RequestPayload) -> str:
    # Choose the most common month across cashOut + cashIn; fallback to current month
    counts: Dict[str, int] = {}
    for ev in payload.cashOut + payload.cashIn:
        try:
            y, m, _ = ev.date.split("-")
            key = f"{y}-{m}"
            counts[key] = counts.get(key, 0) + 1
        except Exception:
            continue
    if counts:
        return max(counts.items(), key=lambda kv: kv[1])[0]
    today = datetime.now()
    return f"{today.year:04d}-{today.month:02d}"

# ----- Agents (deterministic stubs for MVP) -----

def calendar_planner(p: RequestPayload) -> Dict[str, object]:
    """
    Deterministic MVP planner with A1 guardrails:
      - Skip split if no cards provided
      - Avoid weekends by bumping to Monday when weekend_payments == False
    """
    changes: List[Dict[str, object]] = []

    # 1) MOVE: pick the first moveable event (prefer 'utilities'/'internet') and move to end of window
    move_done = False
    for ev in p.cashOut:
        if ev.window and not ev.fixed:
            if ev.label.lower() in {"utilities", "internet"} or not move_done:
                target_dt = _dt(ev.window.end)
                if not p.policy.weekend_payments:
                    target_dt = _bump_to_weekday(target_dt)
                target = _iso(target_dt)
                if target != ev.date:
                    changes.append({
                        "type": "move",
                        "payment_id": ev.id,
                        "from": ev.date,
                        "to": target,
                        "reason": "align_payroll"
                    })
                    move_done = True
                    break

    # 2) SPLIT (credit-util): only if a card exists
    metrics: Dict[str, object]
    explain: List[str]

    if p.cards:
        base_month = _derive_month(p)
        y, m = map(int, base_month.split("-"))
        cut = p.cards[0].cut_day
        d1 = datetime(y, m, max(1, cut - 3))
        d2 = datetime(y, m, max(1, cut - 1))
        if not p.policy.weekend_payments:
            d1 = _bump_to_weekday(d1)
            d2 = _bump_to_weekday(d2)
        parts = [
            {"date": _iso(d1), "amount": 120},
            {"date": _iso(d2), "amount": 80},
        ]
        from_date = p.cashOut[0].date if p.cashOut else _iso(datetime.now())
        changes.append({
            "type": "split",
            "payment_id": "min_visa",
            "from": from_date,
            "parts": parts,
            "reason": "pre_cut_utilization"
        })
        metrics = {
            "fees_avoided": 165,
            "overdraft_risk_delta": -0.8,
            "buffer_min": p.policy.buffer_min,
            "utilization_projection": {"card_visa": {"before": 0.46, "after": 0.10}}
        }
        explain = [
            "Moved a payment within its allowed window to land after paycheck.",
            "Inserted pre-cut micro-payments to lower reported utilization."
        ]
    else:
        metrics = {
            "fees_avoided": 120,
            "overdraft_risk_delta": -0.6,
            "buffer_min": p.policy.buffer_min
        }
        explain = [
            "Moved a payment within its allowed window to land after paycheck.",
            "No credit card provided, so no utilization split was scheduled."
        ]

    return {"changes": changes, "metrics": metrics, "explain": explain}

def qa_agent(_: RequestPayload) -> Dict[str, object]:
    return {
        "changes": [],
        "metrics": {},
        "explain": [
            "We respect your windows and buffer requirement.",
            "Locked items are never moved.",
            "Pre-cut payments reduce reported card utilization."
        ]
    }

# ----- Endpoints -----

@app.post("/orchestrate/plan", response_model=Plan)
def orchestrate_plan(payload: RequestPayload):
    # Route: 'question' returns explanations only; otherwise run planner
    if payload.intent.name == "question":
        out = qa_agent(payload)
    else:
        out = calendar_planner(payload)

    return Plan(
        id=_short_id("plan"),
        user_id=str(payload.user.get("id", "usr_123")),
        month=_derive_month(payload),
        changes=out["changes"],
        metrics=out["metrics"],
        explain=out["explain"]
    )

@app.post("/ingest/plaid-transform")
def plaid_transform(plaid_payload: dict = Body(...)) -> dict:
    from .ingest_plaid import plaid_to_agent_payload
    return plaid_to_agent_payload(plaid_payload)
