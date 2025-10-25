# Alto — JSON Contracts (Agents)

## Request: POST /orchestrate/plan
{
  "user": { "id": "usr_123", "tz": "America/New_York", "currency": "USD" },
  "policy": { "buffer_min": 300, "never_move": ["Rent"], "weekend_payments": false,
              "bnpl_guard_days": 7, "utilization_targets": { "default": 0.10 } },
  "cashIn": [ { "id": "inc_1", "label": "Paycheck", "date": "2025-11-08", "amount": 1900, "fixed": true } ],
  "cashOut": [
    { "id": "pay_rent", "label": "Rent", "date": "2025-12-01", "amount": 1400, "fixed": true, "window": null },
    { "id": "pay_util", "label": "Utilities", "date": "2025-11-12", "amount": 120, "fixed": false,
      "window": { "start": "2025-11-10", "end": "2025-11-20" } }
  ],
  "cards": [ { "id": "card_visa", "limit": 5000, "balance": 860, "cut_day": 28, "due_day": 21 } ],
  "bnplPlans": [],
  "intent": { "name": "fee_proof", "params": { "days": 30, "lock": ["Rent"] } }
}

## Response: Plan
{
  "plan": {
    "id": "plan_tmp",
    "user_id": "usr_123",
    "month": "2025-11",
    "changes": [
      { "type": "move", "payment_id": "pay_util", "from": "2025-11-12", "to": "2025-11-20", "reason": "align_payroll" },
      { "type": "split", "payment_id": "min_visa", "from": "2025-11-12",
        "parts": [ { "date": "2025-11-25", "amount": 120 }, { "date": "2025-11-27", "amount": 80 } ],
        "reason": "pre_cut_utilization" }
    ],
    "metrics": { "fees_avoided": 165, "overdraft_risk_delta": -0.8, "buffer_min": 300,
      "utilization_projection": { "card_visa": { "before": 0.46, "after": 0.10 } } },
    "explain": [ "Moved Utilities within allowed window.", "Inserted pre-cut micro-payments to lower utilization." ]
  }
}
