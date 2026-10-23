"""Deterministic crop/weather suitability calculations.

This module deliberately keeps agronomic comparisons outside the language model.
Requirements are editable farm records and are labeled as configurable
demonstration assumptions until the owner replaces them with a cited source.
"""

from calendar import month_name
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


TIMEZONE = "America/New_York"
SEASONS = ((12, "Winter"), (3, "Spring"), (6, "Summer"), (9, "Autumn"))


def _season(local_date: date) -> str:
    for start_month, name in reversed(SEASONS):
        if local_date.month >= start_month:
            return name
    return "Winter"


def _window_label(start: str | None, end: str | None) -> str:
    if not start or not end:
        return "Not configured"
    return f"{start} to {end}"


def _window_contains(value: date, start: str | None, end: str | None) -> bool | None:
    if not start or not end:
        return None
    try:
        start_month, start_day = (int(x) for x in start.split("-"))
        end_month, end_day = (int(x) for x in end.split("-"))
        start_date = date(value.year, start_month, start_day)
        end_date = date(value.year, end_month, end_day)
        if end_date < start_date:
            return value >= start_date or value <= end_date
        return start_date <= value <= end_date
    except (TypeError, ValueError):
        return None


def _stage(as_of: date, planting: str | None, harvest: str | None, maturity_days: int | None) -> str:
    if not planting or not harvest:
        return "UNKNOWN"
    try:
        planted = date.fromisoformat(planting)
        harvested = date.fromisoformat(harvest)
    except ValueError:
        return "UNKNOWN"
    if as_of < planted:
        return "SEED"
    if as_of >= harvested:
        return "HARVEST_READY" if as_of <= harvested + timedelta(days=7) else "PAST_HARVEST"
    elapsed = (as_of - planted).days
    fraction = elapsed / max(1, maturity_days or (harvested - planted).days)
    if fraction < 0.15:
        return "SPROUT"
    if fraction < 0.75:
        return "GROWING"
    return "MATURE"


def _forecast_bounds(weather: dict) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    periods = weather.get("forecast") or []
    if not periods:
        return None, None, None, None, None
    mins = [p.get("temperature_min_f") for p in periods if p.get("temperature_min_f") is not None]
    maxes = [p.get("temperature_max_f", p.get("temperature_f")) for p in periods if p.get("temperature_max_f", p.get("temperature_f")) is not None]
    rain = [p.get("precip_probability_pct") for p in periods if p.get("precip_probability_pct") is not None]
    rainfall = [p.get("rainfall_in") for p in periods if p.get("rainfall_in") is not None]
    return (min(mins) if mins else None, max(maxes) if maxes else None, max(rain) if rain else None, sum(rainfall) if rainfall else None, max((h.get("wind_speed_mph") or 0 for h in weather.get("hourly") or []), default=None))


def _status_and_risk(crop: dict, weather: dict) -> tuple[str, str, str]:
    minimum, maximum, rain_probability, rainfall, wind = _forecast_bounds(weather)
    if minimum is None and maximum is None:
        return "INSUFFICIENT_DATA", "Forecast values are unavailable", "No weather-based action can be calculated."
    frost = crop.get("frost_tolerance_f")
    heat = crop.get("heat_sensitivity_f")
    risks: list[tuple[int, str, str]] = []
    if frost is not None and minimum is not None and minimum <= float(frost):
        severity = "Critical" if minimum < float(frost) - 5 else "At Risk"
        risks.append((4 if severity == "Critical" else 3, "Frost risk", f"Forecast low {minimum:.0f}°F is at or below the configured {float(frost):.0f}°F threshold."))
    if heat is not None and maximum is not None and maximum >= float(heat):
        severity = "Critical" if maximum > float(heat) + 10 else "At Risk"
        risks.append((4 if severity == "Critical" else 3, "Heat risk", f"Forecast high {maximum:.0f}°F reaches the configured {float(heat):.0f}°F threshold."))
    if rain_probability is not None and rain_probability >= 70:
        risks.append((2, "Heavy-rain monitor", f"Seven-day precipitation probability reaches {rain_probability:.0f}%; inspect drainage and harvest access."))
    if rainfall is not None and rainfall >= 2:
        risks.append((2, "Rainfall monitor", f"Forecast rainfall totals {rainfall:.1f} inches across the seven-day window."))
    if wind is not None and wind >= 30:
        risks.append((3, "Wind risk", f"Hourly forecast wind reaches {wind:.0f} mph; inspect trellises and structures."))
    if risks:
        priority, label, explanation = max(risks, key=lambda item: item[0])
        return ("Critical" if priority == 4 else "At Risk" if priority == 3 else "Monitor"), label, explanation
    current = (weather.get("current") or {}).get("temperature_f")
    if current is not None and crop.get("preferred_temperature_min_f") is not None and current < float(crop["preferred_temperature_min_f"]):
        return "Monitor", "Cool conditions", f"Current outdoor air is {current:.0f}°F, below the configured preferred minimum."
    if current is not None and crop.get("preferred_temperature_max_f") is not None and current > float(crop["preferred_temperature_max_f"]):
        return "Monitor", "Warm conditions", f"Current outdoor air is {current:.0f}°F, above the configured preferred maximum."
    return "Favorable", "No configured seven-day threshold triggered", "Continue routine observation; this is not a yield or disease prediction."


def build_crop_intelligence(conn, weather: dict, *, now: datetime | None = None) -> dict:
    """Return all crop rows and their assigned plots against one weather snapshot."""
    local_now = (now or datetime.now(ZoneInfo(TIMEZONE))).astimezone(ZoneInfo(TIMEZONE))
    local_date = local_now.date()
    farm = conn.execute("SELECT timezone FROM farms LIMIT 1").fetchone()
    timezone_name = (farm["timezone"] if farm and farm["timezone"] else TIMEZONE)
    current = weather.get("current") or weather.get("observation") or {}
    minimum, maximum, _, _, _ = _forecast_bounds(weather)
    crops = conn.execute("SELECT * FROM crops ORDER BY name").fetchall()
    assignments = conn.execute("""SELECT p.crop_id, p.planting_date, p.expected_harvest_date,
        a.asset_id, a.name, a.asset_type
        FROM production_plans p JOIN assets a ON a.asset_id=p.asset_id
        WHERE p.farm_id=(SELECT farm_id FROM farms LIMIT 1) AND a.asset_type='PLOT'""").fetchall()
    by_crop: dict[str, list[dict]] = {}
    for row in assignments:
        by_crop.setdefault(row["crop_id"], []).append(dict(row))
    upcoming: list[dict] = []
    results: list[dict] = []
    for row in crops:
        crop = dict(row)
        plots = by_crop.get(crop["crop_id"], [])
        stages = [_stage(local_date, p.get("planting_date"), p.get("expected_harvest_date"), crop.get("maturity_days")) for p in plots]
        stage = stages[0] if stages else "UNASSIGNED"
        status, major_risk, explanation = _status_and_risk(crop, weather)
        planting = _window_label(crop.get("planting_window_start"), crop.get("planting_window_end"))
        harvest = _window_label(crop.get("harvest_window_start"), crop.get("harvest_window_end"))
        window_state = _window_contains(local_date, crop.get("planting_window_start"), crop.get("harvest_window_end"))
        if window_state is False and status == "Favorable":
            status, major_risk, explanation = "Monitor", "Outside typical crop window", "The calendar date is outside the configured combined planting/harvest window."
        action = explanation
        if "Frost" in major_risk:
            action = "Review frost protection for the affected outdoor plots before the forecast low."
        elif "Heat" in major_risk:
            action = "Review irrigation, shade, and ventilation; the forecast is not an on-farm stress measurement."
        elif "rain" in major_risk.lower():
            action = "Inspect drainage and review harvest or field-access timing with the owner."
        elif "Wind" in major_risk:
            action = "Inspect trellises and greenhouse coverings before the forecast wind."
        for p in plots:
            if p.get("expected_harvest_date"):
                upcoming.append({"crop_id": crop["crop_id"], "crop_name": crop["name"], "plot_name": p["name"], "date": p["expected_harvest_date"], "kind": "harvest"})
        results.append({
            "crop_id": crop["crop_id"], "crop_name": crop["name"], "status": status, "stage": stage,
            "assigned_plots": [{"asset_id": p["asset_id"], "name": p["name"], "production_context": "greenhouse" if p["asset_type"] == "GREENHOUSE" else "outdoor"} for p in plots],
            "major_risk": major_risk, "risk_explanation": explanation,
            "current_comparison": f"{current.get('temperature_f')}°F outdoor air; forecast {minimum}°F–{maximum}°F over seven days" if current.get("temperature_f") is not None and minimum is not None else "Weather comparison unavailable",
            "current_temperature_f": current.get("temperature_f"), "forecast_min_f": minimum, "forecast_max_f": maximum,
            "preferred_temperature_f": f"{crop.get('preferred_temperature_min_f') or 'N/A'}–{crop.get('preferred_temperature_max_f') or 'N/A'}",
            "preferred_temperature_min_f": crop.get("preferred_temperature_min_f"), "preferred_temperature_max_f": crop.get("preferred_temperature_max_f"),
            "frost_threshold_f": crop.get("frost_tolerance_f"), "heat_threshold_f": crop.get("heat_sensitivity_f"),
            "preferred_humidity_pct": None, "soil_temperature_requirement_f": None, "water_requirement_in_week": crop.get("water_requirement_in_week"),
            "planting_window": planting, "harvest_window": harvest, "window_state": "within" if window_state is True else "outside" if window_state is False else "not configured",
            "expected_maturity_date": plots[0].get("expected_harvest_date") if plots else None, "recommended_action": action,
            "requirements_source": crop.get("agronomic_source") or "Configurable demonstration assumption",
            "weather_source": weather.get("provider", "Open-Meteo"), "data_status": weather.get("data_status", "UNAVAILABLE"),
            "production_context": "greenhouse" if any(p["asset_type"] == "GREENHOUSE" for p in plots) else "outdoor" if plots else "unassigned",
        })
    upcoming.sort(key=lambda item: item["date"])
    metrics = weather.get("agricultural_metrics") or {"soil_temperature_6cm_f": None, "soil_moisture_0_to_1cm": None, "evapotranspiration_mm": None, "sunshine_duration_seconds": None, "source": "Unavailable"}
    return {"data_status": weather.get("data_status", "UNAVAILABLE"), "seasonal_overview": {"current_season": _season(local_date), "local_date": local_date.isoformat(), "month_name": month_name[local_date.month], "timezone": timezone_name, "growing_context": "Connecticut typical growing-season context is illustrative; short-term forecast values are provider data.", "upcoming_windows": upcoming[:12]}, "crops": results, "agricultural_metrics": metrics, "weather": weather}
