"""Deterministic buyer matching and wholesale offer calculations."""

from datetime import date

FORMULA_VERSION = "sales-v1"


def match_score(*, preference_match: bool, category_match: bool, quantity: float,
                minimum_order: float, available: float, price: float,
                min_price: float | None, max_price: float | None,
                delivery_date: date, sell_by_date: str | None,
                suppressed: bool = False) -> dict:
    if suppressed:
        return {"eligible": False, "score": 0, "explanation": "Contact is suppressed or opted out."}
    reasons = []
    if not preference_match:
        return {"eligible": False, "score": 0, "explanation": "Product is not in the buyer's recorded preferences."}
    if quantity < minimum_order:
        return {"eligible": False, "score": 0, "explanation": "Requested quantity is below the buyer's recorded minimum order."}
    if available < quantity:
        return {"eligible": False, "score": 0, "explanation": "Physical available inventory is insufficient."}
    score = 40
    reasons.append("recorded product preference")
    if category_match:
        score += 15; reasons.append("compatible buyer category")
    if min_price is None or price >= min_price:
        score += 15; reasons.append("price meets recorded floor")
    else:
        return {"eligible": False, "score": 0, "explanation": "Approved price is below the buyer's recorded price range."}
    if max_price is None or price <= max_price:
        score += 10; reasons.append("price is within recorded range")
    if sell_by_date:
        days = (date.fromisoformat(sell_by_date) - delivery_date).days
        if days >= 0:
            score += 20; reasons.append("delivery fits recorded sell-by date")
        else:
            return {"eligible": False, "score": 0, "explanation": "Proposed delivery is after the lot sell-by date."}
    return {"eligible": True, "score": min(100, score), "explanation": "Matched on " + ", ".join(reasons) + ". Potential opportunity only; demand is not confirmed."}


def offer_total(lines: list[dict]) -> float:
    if not lines:
        raise ValueError("An offer requires at least one line")
    total = 0.0
    for line in lines:
        quantity = float(line["quantity"]); unit_price = float(line["unit_price"])
        if quantity <= 0 or unit_price < 0:
            raise ValueError("Offer quantities must be positive and prices cannot be negative")
        total += quantity * unit_price
    return round(total, 2)


def draft_email(*, farm_name: str, farm_location: str, buyer_name: str,
                contact_name: str | None, lines: list[dict], delivery_date: str,
                postal_address: str | None = None) -> dict:
    greeting = f"Hello {contact_name}," if contact_name else f"Hello {buyer_name} team,"
    items = "\n".join(f"- {x['quantity']:g} {x['unit']} {x['product_name']} at ${x['unit_price']:.2f}/{x['unit']}" for x in lines)
    total = offer_total(lines)
    footer = postal_address or "Farm postal address: NOT CONFIGURED"
    body = f"{greeting}\n\n{farm_name} in {farm_location} has the following wholesale availability for {delivery_date}:\n\n{items}\n\nProposed total: ${total:,.2f}. This is a nonbinding offer subject to owner confirmation and inventory availability.\n\nPlease reply if you would like to discuss quantities or delivery details.\n\nBest,\n{farm_name}\n{footer}\nCommercial message — reply to opt out of future outreach."
    return {"subject": f"Wholesale availability from {farm_name} — {delivery_date}", "body": body, "classification": "DETERMINISTIC_TEMPLATE", "sent": False}
