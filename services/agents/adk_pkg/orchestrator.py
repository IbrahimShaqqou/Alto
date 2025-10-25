import os
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from services.agents.app.main import RequestPayload  # type: ignore
from .openrouter_client import openrouter_chat, OpenRouterError

def _use_adk() -> bool:
    return os.getenv("USE_ADK", "false").lower() in {"1","true","yes","on"}

def _provider() -> str:
    return os.getenv("EXPLAIN_PROVIDER", "native").lower()

def _summarize_for_llm(p: "RequestPayload") -> str:
    # Make a compact, safe summary for the LLM (no PII; derived state only)
    cash_in = [f"{c.label} {c.date} ${c.amount:.2f}" for c in p.cashIn[:6]]
    cash_out = [f"{c.label} {c.date} ${c.amount:.2f}{' (fixed)' if c.fixed else ''}" for c in p.cashOut[:10]]
    policy = p.policy.model_dump()
    lines: List[str] = []
    lines.append("User state (truncated):")
    if cash_in:  lines.append("  Income: " + "; ".join(cash_in))
    if cash_out: lines.append("  Outgo:  " + "; ".join(cash_out))
    lines.append(f"Policy: buffer_min={policy.get('buffer_min')} weekend_payments={policy.get('weekend_payments')}")
    return "\n".join(lines)

def _native_calendar_planner(payload: "RequestPayload") -> Dict[str, Any]:
    from services.agents.app import main as app_main

    return app_main.calendar_planner(payload)


def _native_qa_agent(payload: "RequestPayload") -> Dict[str, Any]:
    from services.agents.app import main as app_main

    return app_main.qa_agent(payload)


def _llm_explain(payload: "RequestPayload") -> Dict[str, Any]:
    """
    Explain via OpenRouter if configured; otherwise fall back to qa_agent.
    Returns {'explain': [..]} shape.
    """
    if _provider() != "openrouter":
        return _native_qa_agent(payload)

    try:
        summary = _summarize_for_llm(payload)
        prompt_system = (
            "You are Alto's financial plan explainer. "
            "Answer in 1–3 short bullets, concrete and non-fluffy. "
            "Never output PII or any secrets. Avoid generic advice—stick to the specific schedule effects."
        )
        prompt_user = (
            f"{summary}\n\nTask: Explain the proposed plan in 1–3 bullets for a judge. "
            f"Focus on scheduling moves, pre-cut micro-payments, fees avoided, and buffer policy."
        )
        text = openrouter_chat(
            messages=[{"role":"system","content": prompt_system},
                      {"role":"user","content": prompt_user}]
        )
        # Normalize into our shape
        bullets = [b.strip("-• ").strip() for b in text.split("\n") if b.strip()]
        if not bullets:
            bullets = ["Plan computed. No model explanation provided."]
        return {"explain": bullets[:3]}
    except OpenRouterError:
        # Graceful fallback if API key invalid/rate-limited/etc.
        return _native_qa_agent(payload)

def orchestrate(payload: "RequestPayload") -> Dict[str, Any]:
    """
    ADK-style orchestrator: planner is deterministic; explanations may use OpenRouter.
    Returns the same dict your native path returns: {'changes':[], 'metrics':{}, 'explain':[]}
    """
    intent = payload.intent.name
    if not _use_adk():
        # Fully native
        if intent == "question":
            return _native_qa_agent(payload)
        return _native_calendar_planner(payload)

    # "ADK on": Route by intent; planning stays deterministic; explanation may use LLM
    if intent == "question":
        return _llm_explain(payload)
    # For planning intents, compute plan then optionally add LLM rationale
    out = _native_calendar_planner(payload)
    if _provider() == "openrouter":
        llm = _llm_explain(payload)
        # Merge explainers (LLM wins but preserve deterministic if empty)
        if llm.get("explain"):
            out["explain"] = llm["explain"]
    return out
