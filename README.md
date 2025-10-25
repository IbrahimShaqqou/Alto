# Alto

Alto is a chat-driven planner that **re-times** income, bills, subscriptions, and payments on a calendar to reduce overdrafts/fees and improve credit utilization.  
This repo currently includes the **Agents Service** (FastAPI) that returns a deterministic **Plan** you can animate in the UI.

## What’s here (MVP)
- **Agents Service** (`services/agents`):
  - `POST /orchestrate/plan` – takes user state + intent → returns a **Plan** `{changes[], metrics{}, explain[]}`.
  - `POST /ingest/plaid-transform` – converts Plaid `transactions/sync` JSON → our agent payload (cashIn/cashOut/policy).
  - `GET /health` – health check.

> UI/DB work is intentionally barebones and can be built by teammates against these contracts.

---

## Quick start (local)

```bash
# From repo root
python -m venv .venv && source .venv/bin/activate
pip install -r services/agents/requirements.txt

# Run
uvicorn services.agents.app.main:app --host 0.0.0.0 --port 8080 --reload
