"""Deterministic inventory and spoilage calculations.

This module contains no LLM logic. Database mutations are performed by the
API inside SQLite transactions; these functions make the accounting rules
explicit and independently testable.
"""

from datetime import date

MOVEMENT_SIGNS = {
    "RECEIPT": 1,
    "ADJUSTMENT": 1,
    "SALE": -1,
    "SPOILAGE": -1,
    "DISPOSAL": -1,
    "DONATION": -1,
    "TRANSFER_OUT": -1,
    "TRANSFER_IN": 1,
    "PROCESSING_INPUT": -1,
}
FORMULA_VERSION = "inventory-v1"


def positive_quantity(quantity: float) -> float:
    value = float(quantity)
    if value <= 0:
        raise ValueError("Quantity must be greater than zero")
    return value


def available_quantity(on_hand: float, reserved: float) -> float:
    available = round(float(on_hand) - float(reserved), 6)
    if available < -1e-6:
        raise ValueError("Reserved quantity cannot exceed physical on-hand quantity")
    return max(0.0, available)


def movement_delta(movement_type: str, quantity: float) -> float:
    positive_quantity(quantity)
    try:
        return MOVEMENT_SIGNS[movement_type] * float(quantity)
    except KeyError as exc:
        raise ValueError(f"Unsupported movement type: {movement_type}") from exc


def spoilage_assessment(*, quantity_on_hand: float, reserved_quantity: float,
                        sell_by: str | None, as_of: date, shelf_life_days: int | None,
                        approved_price: float | None, rescue_window_days: int = 2,
                        discount_rate: float = 0.20) -> dict:
    if quantity_on_hand < 0 or reserved_quantity < 0:
        raise ValueError("Inventory quantities cannot be negative")
    if not 0 <= discount_rate < 1:
        raise ValueError("Discount rate must be between zero and one")
    if not sell_by:
        return {"risk": "UNKNOWN", "days_to_expiry": None, "at_risk_quantity": 0.0,
                "predicted_waste": 0.0, "rescue_quantity": 0.0,
                "gross_sales_value_at_risk": 0.0, "recoverable_sales_scenario": None,
                "assumption": "No sell-by date is recorded; no age-based risk is inferred."}
    expiry = date.fromisoformat(sell_by)
    days = (expiry - as_of).days
    available = available_quantity(quantity_on_hand, reserved_quantity)
    if days < 0:
        risk = "EXPIRED"
    elif days <= rescue_window_days:
        risk = "HIGH"
    elif shelf_life_days and days <= max(1, round(shelf_life_days * 0.35)):
        risk = "MODERATE"
    else:
        risk = "LOW"
    at_risk = available if risk in {"HIGH", "EXPIRED"} else 0.0
    price = float(approved_price or 0)
    predicted = round(at_risk * (0.25 if risk == "HIGH" else 0.75 if risk == "EXPIRED" else 0), 6)
    recoverable = None if risk == "EXPIRED" else round(at_risk * price * (1 - discount_rate), 2)
    return {"risk": risk, "days_to_expiry": days, "at_risk_quantity": at_risk,
            "predicted_waste": predicted, "rescue_quantity": max(0.0, at_risk - predicted),
            "gross_sales_value_at_risk": round(at_risk * price, 2),
            "recoverable_sales_scenario": recoverable,
            "assumption": "Age-based demonstration rule; not a food-safety or scientific spoilage prediction."}
