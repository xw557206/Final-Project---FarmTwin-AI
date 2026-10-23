"""Deterministic poultry and egg-operation calculations.

Egg quantities, conversions, inventory balances, and financial rollups are
owned here or by the shared inventory/finance tables. AI tools may explain
these results but do not create poultry facts.
"""

from collections import defaultdict
from datetime import date, timedelta

from .inventory import available_quantity, movement_delta

FORMULA_VERSION = "poultry-operations-v1"
PACKAGE_SPECS = {
    "SINGLE": ("product-eggs-loose", 1, "egg"),
    "HALF_DOZEN": ("product-eggs-half-dozen", 6, "half-dozen"),
    "DOZEN": ("product-eggs-dozen", 12, "dozen"),
    "CASE": ("product-eggs-case", 180, "case"),
}


def laying_rate(eggs: int | float, laying_hens: int, days: int = 1) -> float | None:
    if laying_hens <= 0 or days <= 0:
        return None
    return round(float(eggs) / (laying_hens * days), 4)


def package_spec(package_type: str) -> dict:
    try:
        product_id, eggs_per_package, unit = PACKAGE_SPECS[package_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported egg package type: {package_type}") from exc
    return {"product_id": product_id, "eggs_per_package": eggs_per_package, "unit": unit}


def _lot_state(conn, lot_id: str) -> dict:
    lot = conn.execute("SELECT l.*,p.name product_name,p.category product_category FROM inventory_lots l JOIN products p ON p.product_id=l.product_id WHERE l.lot_id=?", (lot_id,)).fetchone()
    if not lot:
        raise ValueError("Egg inventory lot not found")
    movements = conn.execute("SELECT * FROM inventory_movements WHERE lot_id=? ORDER BY movement_at", (lot_id,)).fetchall()
    reservations = conn.execute("SELECT * FROM inventory_reservations WHERE lot_id=? AND status='ACTIVE'", (lot_id,)).fetchall()
    on_hand = round(sum(movement_delta(row["movement_type"], row["quantity"]) for row in movements), 6)
    reserved = round(sum(row["quantity"] for row in reservations), 6)
    if on_hand < -1e-6:
        raise ValueError("Egg inventory ledger has negative on-hand quantity")
    result = dict(lot)
    result.update({"on_hand": max(0.0, on_hand), "reserved": reserved, "available": available_quantity(on_hand, reserved),
                   "movements": [dict(row) for row in movements], "reservations": [dict(row) for row in reservations]})
    return result


def weather_risks(weather: dict | None) -> list[dict]:
    if not weather or weather.get("data_status") not in {"LIVE_FORECAST", "CACHED"}:
        return [{"status": "INSUFFICIENT_DATA", "severity": "INFO", "condition": "WEATHER_UNAVAILABLE",
                 "recommended_action": "No live or cached outdoor weather is available; inspect recorded coop conditions manually."}]
    current = weather.get("current") or {}
    temperature = current.get("temperature_f")
    humidity = current.get("relative_humidity_pct")
    wind = current.get("wind_speed_mph")
    risks = []
    if temperature is not None and temperature >= 85:
        risks.append({"status": "AT_RISK", "severity": "HIGH", "condition": "HEAT", "value": temperature,
                      "threshold": "85°F outdoor heat-monitoring threshold", "recommended_action": "Check shade, ventilation, and drinking-water access; outdoor weather is not indoor coop temperature."})
    if temperature is not None and temperature <= 32:
        risks.append({"status": "MONITOR", "severity": "MEDIUM", "condition": "COLD", "value": temperature,
                      "threshold": "32°F outdoor cold-monitoring threshold", "recommended_action": "Inspect draft protection and unfrozen water; do not infer bird health from outdoor temperature."})
    if wind is not None and wind >= 25:
        risks.append({"status": "AT_RISK", "severity": "HIGH", "condition": "WIND", "value": wind,
                      "threshold": "25 mph fence/structure inspection threshold", "recommended_action": "Inspect run fencing, roof, and loose materials after the wind event."})
    if humidity is not None and humidity >= 85:
        risks.append({"status": "MONITOR", "severity": "MEDIUM", "condition": "HUMIDITY", "value": humidity,
                      "threshold": "85% outdoor humidity monitoring threshold", "recommended_action": "Check coop ventilation and bedding; no disease or indoor humidity conclusion is made."})
    for alert in weather.get("alerts") or []:
        risks.append({"status": "AT_RISK", "severity": alert.get("severity", "UNKNOWN"), "condition": "NWS_ALERT",
                      "value": alert.get("event"), "threshold": "Official NWS active alert", "recommended_action": "Inspect the shelter and follow the official alert guidance before moving the flock."})
    return risks


def poultry_overview(conn, *, as_of_date: date | None = None, weather: dict | None = None) -> dict:
    selected = as_of_date or date.today()
    start = selected - timedelta(days=29)
    flocks = [dict(row) for row in conn.execute("SELECT * FROM poultry_flocks ORDER BY name").fetchall()]
    hens = sum(row["hens_count"] for row in flocks if row["production_status"] == "LAYING")
    roosters = sum(row["roosters_count"] for row in flocks)
    chicks = sum(row["chicks_count"] for row in flocks)
    collections = [dict(row) for row in conn.execute("""SELECT c.*,f.name flock_name,f.breed FROM poultry_egg_collections c JOIN poultry_flocks f ON f.flock_id=c.flock_id
        WHERE c.collection_date BETWEEN ? AND ? ORDER BY c.collection_date""", (start.isoformat(), selected.isoformat())).fetchall()]
    daily = defaultdict(int)
    by_flock = defaultdict(int)
    for row in collections:
        daily[row["collection_date"]] += row["eggs_collected"]
        by_flock[row["flock_id"]] += row["eggs_collected"]
    today_total = sum(row["eggs_collected"] for row in collections if row["collection_date"] == selected.isoformat())
    seven_start = selected - timedelta(days=6)
    seven_total = sum(row["eggs_collected"] for row in collections if row["collection_date"] >= seven_start.isoformat())
    month_total = sum(row["eggs_collected"] for row in collections if row["collection_date"][:7] == selected.isoformat()[:7])
    accepted = sum(row["accepted_for_grading"] for row in collections)
    rejected = sum(row["broken_eggs"] + row["dirty_rejected"] for row in collections)
    laying = laying_rate(today_total, hens)
    baseline = round(sum(row["hens_count"] * row["expected_laying_rate"] for row in flocks if row["production_status"] == "LAYING"), 2)
    lots = []
    for row in conn.execute("SELECT lot_id FROM inventory_lots l JOIN products p ON p.product_id=l.product_id WHERE p.category='POULTRY'").fetchall():
        lots.append(_lot_state(conn, row["lot_id"]))
    egg_inventory = {"available_eggs": round(sum(item["available"] for item in lots if item["quantity_unit"] == "egg"), 2),
                     "available_packages": round(sum(item["available"] for item in lots if item["quantity_unit"] != "egg"), 2), "lots": lots}
    costs = conn.execute("""SELECT category,COALESCE(SUM(amount),0) amount FROM financial_transactions
        WHERE farm_id=(SELECT farm_id FROM farms LIMIT 1) AND transaction_type='EXPENSE' AND classification='ACTUAL'
        AND category LIKE 'Poultry%' AND transaction_date BETWEEN ? AND ? GROUP BY category""", (start.isoformat(), selected.isoformat())).fetchall()
    revenue = conn.execute("""SELECT COALESCE(SUM(amount),0) FROM financial_transactions WHERE transaction_type='REVENUE'
        AND product_id IN ('product-eggs-loose','product-eggs-half-dozen','product-eggs-dozen','product-eggs-case') AND classification='ACTUAL'
        AND transaction_date BETWEEN ? AND ?""", (start.isoformat(), selected.isoformat())).fetchone()[0]
    total_cost = round(sum(float(row["amount"]) for row in costs), 2)
    gross_profit = round(float(revenue) - total_cost, 2)
    feed_stock = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM poultry_feed_inventory").fetchone()[0]
    estimated_daily_feed = max(0.01, hens * 0.45)
    task_rows = [dict(row) for row in conn.execute("SELECT * FROM poultry_tasks WHERE status NOT IN ('COMPLETED','DISMISSED') ORDER BY due_date,priority").fetchall()]
    risks = weather_risks(weather)
    return {"as_of_date": selected.isoformat(), "formula_version": FORMULA_VERSION, "data_status": "SYNTHETIC", "record_status": "Recorded collections and synthetic demo assumptions; projections are labeled separately.",
            "flock": {"total_hens": hens, "total_roosters": roosters, "total_chicks": chicks, "flock_count": len(flocks), "flocks": flocks},
            "production": {"today_eggs": today_total, "seven_day_eggs": seven_total, "monthly_eggs": month_total, "accepted_eggs": accepted, "rejected_eggs": rejected,
                            "laying_rate": laying, "expected_today_eggs": baseline, "variance_from_baseline": round(today_total - baseline, 2),
                            "daily": [{"date": key, "eggs": value, "source_type": "SYNTHETIC"} for key, value in sorted(daily.items())],
                            "by_flock": [{"flock_id": row["flock_id"], "name": row["name"], "eggs": by_flock.get(row["flock_id"], 0)} for row in flocks]},
            "inventory": egg_inventory,
            "finance": {"cost_breakdown": [dict(row) for row in costs], "total_cost": total_cost, "revenue": round(float(revenue), 2), "gross_profit": gross_profit,
                         "gross_margin_pct": round(gross_profit / float(revenue) * 100, 2) if revenue else None,
                         "cost_per_saleable_egg": round(total_cost / max(1, accepted), 2), "cost_per_dozen": round(total_cost / max(1, accepted) * 12, 2),
                         "break_even_price_per_dozen": round(total_cost / max(1, accepted) * 12, 2), "source_note": "Poultry categories only; synthetic costs are not an audited farm cost study."},
            "feed": {"inventory_quantity": round(float(feed_stock), 2), "unit": "lb", "estimated_daily_feed_lb": round(estimated_daily_feed, 2), "estimated_days_supply": round(float(feed_stock) / estimated_daily_feed, 1), "assumption": "0.45 lb per laying hen per day is an illustrative planning assumption, not a guaranteed ration."},
            "tasks": {"active_count": len(task_rows), "items": task_rows}, "weather": {"data_status": (weather or {}).get("data_status", "UNAVAILABLE"), "temperature_f": ((weather or {}).get("current") or {}).get("temperature_f"), "relative_humidity_pct": ((weather or {}).get("current") or {}).get("relative_humidity_pct"), "wind_speed_mph": ((weather or {}).get("current") or {}).get("wind_speed_mph"), "source": (weather or {}).get("provider"), "source_timestamp": (weather or {}).get("retrieved_at"), "risks": risks},
            "assumptions": ["Flock and egg records are synthetic demonstration data.", "Eggs per hen uses collected eggs divided by laying hens for the stated day or period.", "No egg grade or regulatory compliance is certified without recorded inspection."]}
