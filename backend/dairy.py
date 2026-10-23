"""Deterministic dairy operations calculations and dashboard projections."""

from collections import defaultdict
from datetime import date, timedelta

from .inventory import MOVEMENT_SIGNS, available_quantity, movement_delta

FORMULA_VERSION = "dairy-operations-v1"


def liters(quantity: float, unit: str) -> float:
    unit = unit.lower().strip()
    if unit in {"liter", "liters", "l"}:
        return float(quantity)
    if unit in {"gallon", "gallons", "gal"}:
        return float(quantity) * 3.785411784
    raise ValueError(f"Unsupported dairy volume unit: {unit}")


def gallons(quantity: float, unit: str = "liter") -> float:
    return liters(quantity, unit) / 3.785411784


def calculate_thi(temperature_f: float | None, relative_humidity_pct: float | None) -> float | None:
    """NOAA-style THI approximation using outdoor air values; not a barn sensor."""
    if temperature_f is None or relative_humidity_pct is None:
        return None
    humidity = float(relative_humidity_pct)
    if not 0 <= humidity <= 100:
        raise ValueError("Relative humidity must be between 0 and 100 percent")
    celsius = (float(temperature_f) - 32) * 5 / 9
    return round((1.8 * celsius + 32) - ((0.55 - 0.0055 * humidity) * (1.8 * celsius - 26.8)), 1)


def classify_thi(value: float | None) -> str:
    if value is None:
        return "INSUFFICIENT_DATA"
    if value < 68:
        return "NORMAL"
    if value < 72:
        return "MONITOR"
    if value < 80:
        return "MODERATE_RISK"
    return "HIGH_RISK"


def _animal_category(row: dict) -> str:
    category = row.get("herd_category")
    if category:
        return category
    return {"MILKING": "LACTATING_COW", "DRY": "DRY_COW"}.get(row.get("production_status"), "OTHER")


def _lot_state(conn, lot_id: str) -> dict:
    lot = conn.execute("SELECT * FROM inventory_lots WHERE lot_id=?", (lot_id,)).fetchone()
    if not lot:
        return {}
    movements = conn.execute("SELECT movement_type,quantity FROM inventory_movements WHERE lot_id=?", (lot_id,)).fetchall()
    on_hand = round(sum(movement_delta(r["movement_type"], r["quantity"]) for r in movements), 6)
    reserved = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM inventory_reservations WHERE lot_id=? AND status='ACTIVE'", (lot_id,)).fetchone()[0]
    return {**dict(lot), "on_hand": max(0, on_hand), "reserved": float(reserved), "available": available_quantity(on_hand, float(reserved))}


def _weather_summary(weather: dict | None) -> dict:
    if not weather or weather.get("data_status") not in {"LIVE_FORECAST", "CACHED"}:
        return {"data_status": "UNAVAILABLE", "thi": None, "thi_status": "INSUFFICIENT_DATA", "source": None, "forecast_risk_periods": []}
    current = weather.get("current") or {}
    thi = calculate_thi(current.get("temperature_f"), current.get("relative_humidity_pct"))
    periods = []
    for hour in weather.get("hourly") or []:
        value = calculate_thi(hour.get("temperature_f"), hour.get("humidity_pct"))
        if value is not None and value >= 68:
            periods.append({"timestamp": hour.get("start"), "thi": value, "status": classify_thi(value), "temperature_f": hour.get("temperature_f"), "humidity_pct": hour.get("humidity_pct")})
    return {"data_status": weather.get("data_status"), "temperature_f": current.get("temperature_f"), "relative_humidity_pct": current.get("relative_humidity_pct"), "forecast_high_f": max((x.get("temperature_max_f") for x in weather.get("forecast") or [] if x.get("temperature_max_f") is not None), default=None), "forecast_low_f": min((x.get("temperature_min_f") for x in weather.get("forecast") or [] if x.get("temperature_min_f") is not None), default=None), "thi": thi, "thi_status": classify_thi(thi), "forecast_risk_periods": periods[:24], "alerts": weather.get("alerts", []), "source": weather.get("provider"), "source_timestamp": weather.get("last_successful_refresh") or weather.get("retrieved_at"), "note": "THI uses outdoor provider/model values and must not be interpreted as an indoor barn measurement."}


def dairy_dashboard(conn, *, as_of_date: date | None = None, weather: dict | None = None, weather_risks: list[dict] | None = None) -> dict:
    selected = as_of_date or date.today()
    start = selected - timedelta(days=29)
    animal_rows = [dict(r) for r in conn.execute("SELECT * FROM dairy_animals WHERE archived=0 ORDER BY name").fetchall()]
    counts = defaultdict(int)
    for animal in animal_rows:
        counts[_animal_category(animal)] += 1
    record_rows = [dict(r) for r in conn.execute("SELECT * FROM dairy_production_records WHERE production_date BETWEEN ? AND ? ORDER BY production_date", (start.isoformat(), selected.isoformat())).fetchall()]
    daily = defaultdict(float)
    monthly = defaultdict(float)
    by_animal = defaultdict(float)
    saleable = 0.0
    for row in record_rows:
        amount = liters(row["quantity"], row["unit"])
        daily[row["production_date"]] += amount
        monthly[row["production_date"][:7]] += amount
        if row.get("animal_id"):
            by_animal[row["animal_id"]] += amount
        saleable += liters(row.get("saleable_quantity") or 0, row["unit"])
    daily_rows = [{"date": key, "liters": round(value, 2), "source_type": "SYNTHETIC" if any(r["production_date"] == key and r["source_type"] == "SYNTHETIC" for r in record_rows) else "OWNER_ENTERED"} for key, value in sorted(daily.items())]
    animal_lookup = {a["animal_id"]: a for a in animal_rows}
    cow_rows = [{"animal_id": aid, "name": animal_lookup.get(aid, {}).get("name") or aid, "liters": round(value, 2), "source_type": "CALCULATED"} for aid, value in sorted(by_animal.items(), key=lambda item: item[1], reverse=True)]
    month_rows = [{"month": key, "liters": round(value, 2)} for key, value in sorted(monthly.items())]
    lactating_ids = {a["animal_id"] for a in animal_rows if _animal_category(a) == "LACTATING_COW"}
    today_liters = round(daily.get(selected.isoformat(), 0), 2)
    seven_day = round(sum(daily[key] for key in daily if key >= (selected - timedelta(days=6)).isoformat()), 2)
    month_liters = round(sum(daily.values()), 2)
    actual_lactating = len(lactating_ids)
    expenses = conn.execute("""SELECT category,COALESCE(SUM(amount),0) amount FROM financial_transactions
        WHERE transaction_type='EXPENSE' AND classification='ACTUAL' AND transaction_date BETWEEN ? AND ?
        AND (dairy_id IS NOT NULL OR category IN ('Feed','Veterinary expenses','Bedding','Dairy labor','Utilities','Packaging','Storage','Transportation')) GROUP BY category""", (start.isoformat(), selected.isoformat())).fetchall()
    cost_breakdown = [{"category": r["category"], "amount": round(float(r["amount"]), 2)} for r in expenses]
    dairy_cost = round(sum(item["amount"] for item in cost_breakdown), 2)
    feed_cost = round(next((item["amount"] for item in cost_breakdown if item["category"] == "Feed"), 0), 2)
    revenue = float(conn.execute("""SELECT COALESCE(SUM(amount),0) FROM financial_transactions WHERE transaction_type='REVENUE'
        AND classification='ACTUAL' AND product_id IN (SELECT product_id FROM products WHERE category='DAIRY') AND transaction_date BETWEEN ? AND ?""", (start.isoformat(), selected.isoformat())).fetchone()[0])
    lots = []
    for row in conn.execute("SELECT lot_id FROM inventory_lots WHERE lot_type='DAIRY'").fetchall():
        state = _lot_state(conn, row["lot_id"])
        if state:
            lots.append(state)
    raw = round(sum(x["available"] for x in lots if x["product_id"] == "product-milk" and x["quantity_unit"] in {"liter", "liters"}), 2)
    finished = round(sum(x["available"] for x in lots if x["product_id"] != "product-milk"), 2)
    approaching = [{"lot_id": x["lot_id"], "product_id": x["product_id"], "sell_by_date": x["sell_by_date"], "available": x["available"]} for x in lots if x.get("sell_by_date") and x["available"] > 0 and 0 <= (date.fromisoformat(x["sell_by_date"]) - selected).days <= 2]
    open_tasks = conn.execute("SELECT COUNT(*) FROM dairy_tasks WHERE status NOT IN ('COMPLETED','DISMISSED')").fetchone()[0]
    cost_per_gallon = round(dairy_cost / max(0.0001, gallons(month_liters)), 2)
    gross_profit = round(revenue - dairy_cost, 2)
    return {"as_of_date": selected.isoformat(), "formula_version": FORMULA_VERSION, "data_status": "SYNTHETIC", "record_status": "Actual recorded production through selected date; seeded records are SYNTHETIC.", "herd": {"total": len(animal_rows), "active_milking": counts["LACTATING_COW"], "dry_cows": counts["DRY_COW"], "heifers": counts["PREGNANT_HEIFER"] + counts["NONPREGNANT_HEIFER"], "calves": counts["CALF"], "composition": dict(counts)}, "production": {"today_liters": today_liters, "seven_day_liters": seven_day, "monthly_liters": month_liters, "average_per_lactating_cow_liters": round(today_liters / max(1, actual_lactating), 2), "saleable_recorded_liters": round(saleable, 2), "daily": daily_rows, "by_animal": cow_rows, "by_month": month_rows}, "finance": {"feed_cost_period": feed_cost, "feed_cost_per_lactating_cow_day": round(feed_cost / max(1, actual_lactating * 30), 2), "total_dairy_cost_period": dairy_cost, "cost_per_gallon_saleable_milk": cost_per_gallon, "revenue_period": round(revenue, 2), "gross_profit": gross_profit, "gross_margin_pct": round(gross_profit / revenue * 100, 2) if revenue else None, "break_even_price_per_gallon": cost_per_gallon, "breakdown": cost_breakdown, "source_note": "Calculated from recorded financial transactions; no revenue is recognized merely because milk was produced."}, "inventory": {"raw_milk_liters_available": raw, "finished_dairy_quantity_available": finished, "approaching_expiration": approaching, "lots": lots}, "tasks": {"active_count": open_tasks}, "weather": {**_weather_summary(weather), "herd_risk_count": len(weather_risks or []), "risks": (weather_risks or [])[:10]}, "animals": animal_rows}
