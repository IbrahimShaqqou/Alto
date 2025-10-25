from typing import Dict, List, Tuple
from .main import CashEvent, Window, Policy  # reuse models

SUB_MERCHANTS = {"Spotify","Netflix","Apple"}
def _is_income(tx): return tx.get("personal_finance_category",{}).get("primary") == "INCOME"
def _is_rent(tx): return tx.get("personal_finance_category",{}).get("detailed") == "TRANSFER_OUT_RENT" or "rent" in tx["name"].lower()
def _is_util(tx): return tx.get("personal_finance_category",{}).get("primary") == "UTILITIES"
def _is_card_payment(tx): return tx.get("personal_finance_category",{}).get("detailed") == "TRANSFER_OUT_CREDIT_CARD_PAYMENT"
def _is_subscription(tx):
    pfc = tx.get("personal_finance_category",{})
    if pfc.get("detailed","").endswith("SUBSCRIPTION"): return True
    m = (tx.get("merchant_name") or tx.get("name") or "").split()[0]
    return m in SUB_MERCHANTS

def _window(date:str, days_before:int, days_after:int) -> Window:
    # store as Date strings; planner can do math
    from datetime import datetime, timedelta
    d = datetime.strptime(date, "%Y-%m-%d")
    s = (d - timedelta(days=days_before)).strftime("%Y-%m-%d")
    e = (d + timedelta(days=days_after)).strftime("%Y-%m-%d")
    return Window(start=s, end=e)

def plaid_to_agent_payload(plaid: Dict) -> Dict:
    txs: List[Dict] = plaid.get("added", [])
    cash_in: List[CashEvent] = []
    cash_out: List[CashEvent] = []
    uid = "usr_demo"

    # Income
    for t in txs:
        if _is_income(t):
            cash_in.append(CashEvent(
                id=t["transaction_id"],
                label=t.get("merchant_name") or t["name"],
                date=t["date"],
                amount=float(t["amount"]),
                fixed=True,
                window=None
            ))

    # Bills / subs / rent / payments
    for t in txs:
        name = t.get("merchant_name") or t["name"]
        if _is_rent(t):
            cash_out.append(CashEvent(
                id=t["transaction_id"], label="Rent", date=t["date"],
                amount=float(t["amount"]), fixed=True, window=None
            ))
        elif _is_util(t):
            cash_out.append(CashEvent(
                id=t["transaction_id"], label=name if "Internet" not in name else "Internet",
                date=t["date"], amount=float(t["amount"]),
                fixed=False, window=_window(t["date"], 5, 5)
            ))
        elif _is_subscription(t):
            cash_out.append(CashEvent(
                id=t["transaction_id"], label="Subscription: " + name.split()[0],
                date=t["date"], amount=float(t["amount"]),
                fixed=False, window=_window(t["date"], 3, 7)
            ))
        elif _is_card_payment(t):
            cash_out.append(CashEvent(
                id=t["transaction_id"], label="Card Payment",
                date=t["date"], amount=float(t["amount"]),
                fixed=False, window=_window(t["date"], 3, 3)
            ))
        else:
            # ignore groceries, gas, restaurants for scheduling MVP
            continue

    policy = Policy(
        buffer_min=300,
        never_move=["Rent"],
        weekend_payments=False,
        bnpl_guard_days=7,
        utilization_targets={"default":0.10}
    )

    # Compose minimal agent payload (cards empty for now)
    payload = {
        "user": {"id": uid, "tz": "America/New_York", "currency":"USD"},
        "policy": policy.model_dump(),
        "cashIn": [c.model_dump() for c in cash_in],
        "cashOut": [c.model_dump() for c in cash_out],
        "cards": [],
        "bnplPlans": [],
        "intent": {"name":"fee_proof","params":{"days":30,"lock":["Rent"]}}
    }
    return payload
