from calendar import monthrange
from datetime import datetime, timedelta
from typing import Dict, List

from .main import CashEvent, Window, Policy  # reuse models

SUB_MERCHANTS = {"Spotify", "Netflix", "Apple"}
UTILITY_INTERNET_KEYWORDS = ("internet", "wifi", "broadband", "fiber")


def _is_income(tx):
    return tx.get("personal_finance_category", {}).get("primary") == "INCOME"


def _is_rent(tx):
    return tx.get("personal_finance_category", {}).get("detailed") == "TRANSFER_OUT_RENT" or "rent" in tx["name"].lower()


def _is_util(tx):
    return tx.get("personal_finance_category", {}).get("primary") == "UTILITIES"


def _is_card_payment(tx):
    return tx.get("personal_finance_category", {}).get("detailed") == "TRANSFER_OUT_CREDIT_CARD_PAYMENT"


def _is_subscription(tx):
    pfc = tx.get("personal_finance_category", {})
    if pfc.get("detailed", "").endswith("SUBSCRIPTION"):
        return True
    merchant = (tx.get("merchant_name") or tx.get("name") or "").split()
    head = merchant[0] if merchant else ""
    return head in SUB_MERCHANTS


def _window(date: str, days_before: int, days_after: int) -> Window:
    """Return a window clamped to the month of the source date."""
    current = datetime.strptime(date, "%Y-%m-%d")
    start = current - timedelta(days=days_before)
    end = current + timedelta(days=days_after)
    first_of_month = current.replace(day=1)
    last_of_month = current.replace(day=monthrange(current.year, current.month)[1])
    if start < first_of_month:
        start = first_of_month
    if end > last_of_month:
        end = last_of_month
    return Window(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))


def _normalize_name(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        return cleaned
    if cleaned.isupper() or cleaned.islower():
        return cleaned.title()
    return cleaned


def _normalize_utility_label(raw: str) -> str:
    base = _normalize_name(raw)
    lowered = base.lower()
    for keyword in UTILITY_INTERNET_KEYWORDS:
        if keyword in lowered:
            return "Internet"
    return "Utilities"


def _normalize_subscription_label(raw: str) -> str:
    base = _normalize_name(raw)
    if not base:
        return "Subscription"
    token = base.split()[0]
    return f"Subscription: {token.title()}"


def plaid_to_agent_payload(plaid: Dict) -> Dict:
    txs: List[Dict] = plaid.get("added", [])
    cash_in: List[CashEvent] = []
    cash_out: List[CashEvent] = []
    uid = "usr_demo"
    handled_ids = set()

    # Income
    for t in txs:
        tid = t.get("transaction_id")
        if not tid or tid in handled_ids:
            continue
        amount = float(t.get("amount") or 0)
        if amount <= 0:
            continue
        if _is_income(t):
            cash_in.append(
                CashEvent(
                    id=tid,
                    label=_normalize_name(t.get("merchant_name") or t["name"]),
                    date=t["date"],
                    amount=amount,
                    fixed=True,
                    window=None,
                )
            )
            handled_ids.add(tid)

    # Bills / subs / rent / payments
    for t in txs:
        tid = t.get("transaction_id")
        if not tid or tid in handled_ids:
            continue
        amount = float(t.get("amount") or 0)
        if amount <= 0:
            continue

        raw_name = t.get("name") or t.get("merchant_name") or ""
        merchant_name = t.get("merchant_name") or raw_name
        if _is_rent(t):
            cash_out.append(
                CashEvent(
                    id=tid,
                    label="Rent",
                    date=t["date"],
                    amount=amount,
                    fixed=True,
                    window=None,
                )
            )
        elif _is_util(t):
            cash_out.append(
                CashEvent(
                    id=tid,
                    label=_normalize_utility_label(raw_name),
                    date=t["date"],
                    amount=amount,
                    fixed=False,
                    window=_window(t["date"], 5, 5),
                )
            )
        elif _is_subscription(t):
            cash_out.append(
                CashEvent(
                    id=tid,
                    label=_normalize_subscription_label(merchant_name),
                    date=t["date"],
                    amount=amount,
                    fixed=False,
                    window=_window(t["date"], 3, 7),
                )
            )
        elif _is_card_payment(t):
            cash_out.append(
                CashEvent(
                    id=tid,
                    label="Card Payment",
                    date=t["date"],
                    amount=amount,
                    fixed=False,
                    window=_window(t["date"], 3, 3),
                )
            )
        else:
            # ignore groceries, gas, restaurants for scheduling MVP
            continue
        handled_ids.add(tid)

    policy = Policy(
        buffer_min=300,
        never_move=["Rent"],
        weekend_payments=False,
        bnpl_guard_days=7,
        utilization_targets={"default": 0.10},
    )

    # Compose minimal agent payload (cards empty for now)
    payload = {
        "user": {"id": uid, "tz": "America/New_York", "currency": "USD"},
        "policy": policy.model_dump(),
        "cashIn": [c.model_dump() for c in cash_in],
        "cashOut": [c.model_dump() for c in cash_out],
        "cards": [],
        "bnplPlans": [],
        "intent": {"name": "fee_proof", "params": {"days": 30, "lock": ["Rent"]}},
    }
    return payload
