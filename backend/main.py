from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
import json
import uuid
import re
import csv
import io
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .db import connect, seed_database
from .schemas import FarmUpdate, PlotUpdate, FinancialTransactionCreate, InvestmentAssumptions, PricingScenarioInput, PriceApproval, InventoryAction, InventoryLotCreate, ReservationCreate, AnimalCreate, AnimalUpdate, DairyProductionCreate, MilkCollectionCreate, DairyProcessingCreate, FeedPurchaseCreate, FeedUsageCreate, DairyTaskCreate, DairyTaskUpdate, DairyHealthCreate, MilkProductionCreate, BuyerCreate, OfferCreate, PipelineUpdate, OrderConfirm, AgentRunRequest, PoultryFlockCreate, PoultryFlockUpdate, EggCollectionCreate, EggPackagingCreate, PoultryFeedPurchaseCreate, PoultryFeedUsageCreate, PoultryTaskCreate, PoultryTaskUpdate, PoultryHealthCreate
from .inventory import FORMULA_VERSION as INVENTORY_FORMULA_VERSION, available_quantity, movement_delta, positive_quantity, spoilage_assessment
from .sales import FORMULA_VERSION as SALES_FORMULA_VERSION, draft_email, match_score, offer_total
from .agents import get_run, provider_status, run_agent, tool_registry
from .finance import FORMULA_VERSION, allocation, break_even_price, break_even_quantity, contribution_margin, depreciation, gross_profit, irr, money, npv, operating_profit, payback_period, production_cost, serialize, unit_cost
from .pricing import FORMULA_VERSION as PRICING_FORMULA_VERSION, adjusted_market_reference, gross_margin as pricing_gross_margin, normalize_market_price, recommend_price, simulate_price, target_margin_price
from .weather import WeatherUnavailable, fetch_open_meteo, fetch_nws, friendly_weather_error, unavailable_payload
from .crop_weather import build_crop_intelligence
from .dairy import dairy_dashboard, calculate_thi, liters
from .poultry import poultry_overview, package_spec, weather_risks as poultry_weather_risks, FORMULA_VERSION as POULTRY_FORMULA_VERSION


def row_dict(row): return dict(row) if row else None


def _farm():
    with connect() as c:
        row = c.execute("SELECT * FROM farms LIMIT 1").fetchone()
        if not row:
            raise HTTPException(404, "Farm not found")
        return row_dict(row)


WEATHER_CACHE_SECONDS = 15 * 60


def _weather_for_farm(force_refresh: bool = False) -> dict:
    farm = _farm()
    latitude, longitude = farm.get("latitude"), farm.get("longitude")
    if latitude is None or longitude is None:
        return unavailable_payload("Farm coordinates are not configured", latitude, longitude)
    with connect() as c:
        cached = c.execute("SELECT * FROM weather_snapshots WHERE farm_id=? AND data_status IN ('LIVE_FORECAST','CACHED') ORDER BY retrieved_at DESC LIMIT 1", (farm["farm_id"],)).fetchone()
    if cached and not force_refresh:
        try:
            payload = json.loads(cached["payload_json"])
            retrieved = datetime.fromisoformat(cached["retrieved_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - retrieved).total_seconds()
            # Older snapshots created before agricultural metrics were added
            # remain valid fallback data, but they must not indefinitely mask
            # the upgraded normalized response while still fresh.
            if age < WEATHER_CACHE_SECONDS and "agricultural_metrics" in payload:
                payload["weather_id"] = cached["weather_id"]
                payload["cache_age_seconds"] = round(max(0, age), 1)
                payload["source_data_status"] = payload.get("data_status", "LIVE_FORECAST")
                payload["data_status"] = "CACHED"
                return payload
        except (ValueError, TypeError, json.JSONDecodeError):
            cached = None
    try:
        # `fetch_nws` is retained as a compatibility seam for existing tests;
        # its implementation is now the Open-Meteo forecast + NWS-alert adapter.
        payload = fetch_nws(float(latitude), float(longitude), farm.get("timezone") or "America/New_York")
    except (WeatherUnavailable, TypeError, ValueError) as exc:
        if cached:
            payload = json.loads(cached["payload_json"])
            payload["data_status"] = "CACHED"
            payload["cache_age_seconds"] = round(max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(cached["retrieved_at"].replace("Z", "+00:00"))).total_seconds()), 1)
            payload["refresh_error"] = friendly_weather_error(exc)
            payload["weather_id"] = cached["weather_id"]
            return payload
        payload = unavailable_payload(friendly_weather_error(exc), float(latitude), float(longitude))
    payload["farm_id"] = farm["farm_id"]
    with connect() as c:
        weather_id = "weather-" + uuid.uuid4().hex[:12]
        c.execute("INSERT INTO weather_snapshots VALUES (?,?,?,?,?,?,?,?)", (weather_id, farm["farm_id"], payload.get("provider", "NWS"), payload.get("data_status", "UNAVAILABLE"), payload["retrieved_at"], payload.get("forecast_updated_at"), json.dumps(payload), json.dumps(payload.get("source_urls", {}))))
    payload["weather_id"] = weather_id
    return payload


def _float_wind(text: str | None) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else 0.0


def _risk_records(weather: dict) -> list[dict]:
    if weather.get("data_status") not in {"LIVE_FORECAST", "CACHED"}:
        return []
    with connect() as c:
        plots = c.execute("SELECT a.asset_id, a.name, p.expected_harvest_date, c.* FROM assets a JOIN production_plans p ON p.asset_id=a.asset_id JOIN crops c ON c.crop_id=p.crop_id WHERE a.asset_type='PLOT'").fetchall()
        dairy = c.execute("SELECT * FROM dairy_summary LIMIT 1").fetchone()
    records = []
    for period in weather.get("forecast", []):
        temp = float(period.get("temperature_f") or 0)
        temp_min = float(period.get("temperature_min_f") if period.get("temperature_min_f") is not None else temp)
        temp_max = float(period.get("temperature_max_f") if period.get("temperature_max_f") is not None else temp)
        rain_prob = float(period.get("precip_probability_pct") or 0)
        wind = float(period.get("wind_speed_mph") or _float_wind(period.get("wind_speed")))
        condition = (period.get("short_forecast") or "").lower()
        forecast_date = (period.get("start") or date.today().isoformat())[:10]
        for plot in plots:
            common = {"weather_id": weather.get("weather_id"), "farm_id": weather["farm_id"], "asset_id": plot["asset_id"], "crop_id": plot["crop_id"], "forecast_time": period.get("start") or forecast_date, "source_reference": weather.get("source_urls", {}).get("forecast", "NWS"), "forecast_timestamp": weather.get("forecast_updated_at") or weather.get("retrieved_at")}
            risks = []
            if temp_min <= float(plot["frost_tolerance_f"] or 32):
                risks.append(("FROST", temp_min, "HIGH", f"Forecast low {temp_min:.0f}F is at or below the configured frost threshold for {plot['name']}.", "Inspect frost-sensitive plants and consider approved row-cover or irrigation protection."))
            if temp_max >= float(plot["heat_sensitivity_f"] or 95): risks.append(("HEAT", temp_max, "HIGH", f"Forecast high {temp_max:.0f}°F reaches the configured heat-sensitivity threshold of {plot['heat_sensitivity_f']:.0f}°F.", "Inspect irrigation readiness and monitor heat-sensitive crop areas."))
            if rain_prob >= 70 or "heavy rain" in condition or "thunderstorm" in condition: risks.append(("HEAVY_RAIN", rain_prob, "MEDIUM", f"Precipitation probability is {rain_prob:.0f}% and the forecast says {period.get('short_forecast') or 'rain'}.", "Inspect drainage and consider an approved harvest or field-access adjustment."))
            if wind >= 30: risks.append(("WIND", wind, "MEDIUM", f"Forecast wind is {period.get('wind_speed')} and exceeds the 30 mph mission threshold.", "Secure greenhouse coverings and inspect trellises before the event."))
            harvest_date = plot["expected_harvest_date"]
            if harvest_date and forecast_date <= harvest_date <= (date.fromisoformat(forecast_date) + timedelta(days=3)).isoformat() and rain_prob >= 50:
                risks.append(("HARVEST_DISRUPTION", rain_prob, "MEDIUM", f"The planned harvest window is near a forecast with {rain_prob:.0f}% precipitation probability.", "Review harvest timing and field access with the owner."))
            if temp_max >= float(plot["preferred_temperature_max_f"] or 85) - 5 and rain_prob < 25: risks.append(("IRRIGATION", temp_max, "LOW", f"Warm, relatively dry conditions may increase irrigation attention for {plot['name']}.", "Check soil moisture and irrigation readiness; do not infer crop stress from weather alone."))
            for category, value, severity, explanation, action in risks:
                records.append({**common, "operation": plot["name"], "condition": category, "threshold": f"configured {category} threshold", "forecast_value": value, "severity": severity, "explanation": explanation, "recommended_action": action, "event_key": f"{forecast_date}:{category}:{plot['asset_id']}"})
        if dairy and temp_max >= 85:
            records.append({"weather_id": weather.get("weather_id"), "farm_id": weather["farm_id"], "asset_id": "facility-barn", "crop_id": None, "operation": "Dairy herd", "forecast_time": period.get("start") or forecast_date, "condition": "DAIRY_HEAT", "threshold": "85°F heat-monitoring threshold", "forecast_value": temp_max, "severity": "MEDIUM", "explanation": f"Forecast high {temp_max:.0f}°F meets the configured dairy heat-monitoring threshold.", "recommended_action": "Check shade, water access, ventilation, and owner-entered herd observations.", "source_reference": weather.get("source_urls", {}).get("forecast", "NWS"), "forecast_timestamp": weather.get("forecast_updated_at") or weather.get("retrieved_at"), "event_key": f"{forecast_date}:DAIRY_HEAT:facility-barn"})
    return records


def _store_risks_and_missions(weather: dict) -> list[dict]:
    risks = _risk_records(weather)
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        for risk in risks:
            risk_id = "risk-" + uuid.uuid5(uuid.NAMESPACE_URL, risk["event_key"]).hex[:12]
            c.execute("INSERT OR IGNORE INTO weather_risks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (risk_id, risk["weather_id"], risk["farm_id"], risk.get("asset_id"), risk.get("crop_id"), risk["operation"], risk["forecast_time"], risk["condition"], risk["threshold"], risk.get("forecast_value"), risk["severity"], risk["explanation"], risk["recommended_action"], risk["source_reference"], risk["forecast_timestamp"], risk["event_key"]))
            priority = "High" if risk["severity"] == "HIGH" else "Medium" if risk["severity"] == "MEDIUM" else "Low"
            title = {"FROST":"Protect frost-sensitive plants", "HEAT":"Monitor heat-sensitive crops", "HEAVY_RAIN":"Inspect fields before heavy rain", "WIND":"Secure structures and trellises", "IRRIGATION":"Check irrigation readiness", "HARVEST_DISRUPTION":"Review harvest timing", "DAIRY_HEAT":"Monitor dairy heat conditions"}.get(risk["condition"], "Review weather risk")
            deadline = (risk["forecast_time"][:10] if risk["forecast_time"] else date.today().isoformat())
            mission = ("mission-" + uuid.uuid5(uuid.NAMESPACE_URL, risk["event_key"]).hex[:12], risk["farm_id"], risk_id, risk["event_key"], title, risk["explanation"], risk.get("asset_id"), risk.get("crop_id"), risk["condition"], priority, deadline, risk["recommended_action"], risk["source_reference"], "Suggested", now, now, json.dumps({"created_from":"weather_risk","forecast_timestamp":risk["forecast_timestamp"]}))
            c.execute("INSERT OR IGNORE INTO farm_missions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", mission)
        return [row_dict(r) for r in c.execute("SELECT * FROM farm_missions WHERE farm_id=? ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, suggested_deadline", (weather["farm_id"],)).fetchall()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_database()
    yield


app = FastAPI(title="FarmTwin AI Foundation API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_origin_regex=r"http://(localhost|127\.0\.0\.1):517[0-9]$", allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health(): return {"status": "ok", "data_status": "SYNTHETIC"}


@app.get("/api/farm")
def get_farm():
    with connect() as c:
        farm = c.execute("SELECT * FROM farms LIMIT 1").fetchone()
        if not farm: raise HTTPException(404, "Farm not found")
        return row_dict(farm)


@app.put("/api/farm")
def update_farm(payload: FarmUpdate):
    with connect() as c:
        if payload.latitude is None or payload.longitude is None:
            c.execute("UPDATE farms SET name=?, location=?, updated_at=datetime('now') WHERE farm_id=(SELECT farm_id FROM farms LIMIT 1)", (payload.name, payload.location))
        else:
            c.execute("UPDATE farms SET name=?, location=?, latitude=?, longitude=?, timezone=?, updated_at=datetime('now') WHERE farm_id=(SELECT farm_id FROM farms LIMIT 1)", (payload.name, payload.location, payload.latitude, payload.longitude, payload.timezone or "America/New_York"))
        return row_dict(c.execute("SELECT * FROM farms LIMIT 1").fetchone())


@app.get("/api/plots")
def list_plots():
    with connect() as c:
        rows = c.execute("SELECT a.asset_id, a.name, a.acreage, a.svg_ref, a.status, c.name crop, p.* FROM assets a JOIN production_plans p ON p.asset_id=a.asset_id JOIN crops c ON c.crop_id=p.crop_id WHERE a.asset_type='PLOT' ORDER BY a.asset_id").fetchall()
        return [row_dict(r) for r in rows]


@app.get("/api/plots/{asset_id}")
def get_plot(asset_id: str):
    with connect() as c:
        row = c.execute("SELECT a.asset_id, a.name, a.acreage, a.svg_ref, a.status asset_status, c.name crop, p.* FROM assets a JOIN production_plans p ON p.asset_id=a.asset_id JOIN crops c ON c.crop_id=p.crop_id WHERE a.asset_id=?", (asset_id,)).fetchone()
        if not row: raise HTTPException(404, "Plot not found")
        return row_dict(row)


@app.put("/api/plots/{asset_id}")
def update_plot(asset_id: str, payload: PlotUpdate):
    with connect() as c:
        row = c.execute("SELECT p.plan_id, c.crop_id FROM production_plans p JOIN crops c ON c.crop_id=p.crop_id WHERE p.asset_id=?", (asset_id,)).fetchone()
        if not row: raise HTTPException(404, "Plot not found")
        if payload.expected_harvest_date < payload.planting_date: raise HTTPException(422, "Harvest date must be on or after planting date")
        crop = c.execute("SELECT crop_id FROM crops WHERE lower(name)=lower(?)", (payload.crop,)).fetchone()
        if not crop:
            crop_id = "crop-custom-" + asset_id
            c.execute("INSERT INTO crops (crop_id,name,variety,source_type) VALUES (?,?,?,?)", (crop_id, payload.crop, "Owner-entered", "OWNER_ENTERED"))
        else: crop_id = crop[0]
        c.execute("UPDATE assets SET name=?, acreage=? WHERE asset_id=?", (payload.name, payload.acreage, asset_id))
        c.execute("UPDATE production_plans SET crop_id=?, planting_date=?, expected_harvest_date=?, expected_yield=?, actual_yield=?, status=?, estimated_cost=?, expected_revenue=?, source_type='OWNER_ENTERED' WHERE plan_id=?", (crop_id, payload.planting_date.isoformat(), payload.expected_harvest_date.isoformat(), payload.expected_yield, payload.actual_yield, payload.status, payload.estimated_cost, payload.expected_revenue, row[0]))
        return get_plot(asset_id)


@app.get("/api/products")
def products():
    with connect() as c: return [row_dict(r) for r in c.execute("SELECT * FROM products ORDER BY name").fetchall()]


@app.get("/api/weather")
def weather(refresh: bool = False):
    return _weather_for_farm(force_refresh=refresh)


@app.get("/api/weather/risks")
def weather_risks(refresh: bool = False):
    payload = _weather_for_farm(force_refresh=refresh)
    return {"weather": payload, "risks": _risk_records(payload)}


@app.get("/api/weather/intelligence")
def weather_intelligence(refresh: bool = False):
    payload = _weather_for_farm(force_refresh=refresh)
    with connect() as c:
        result = build_crop_intelligence(c, payload)
    # Keep this endpoint useful when providers fail: the response still exposes
    # every crop and explicitly labels comparisons as insufficient/unavailable.
    return result


@app.get("/api/missions")
def missions(refresh: bool = False):
    payload = _weather_for_farm(force_refresh=refresh)
    return {"data_status": payload.get("data_status"), "missions": _store_risks_and_missions(payload)}


@app.put("/api/missions/{mission_id}")
def update_mission(mission_id: str, status: str):
    allowed = {"Suggested", "Approved", "In Progress", "Completed", "Dismissed"}
    if status not in allowed: raise HTTPException(422, f"Status must be one of {sorted(allowed)}")
    with connect() as c:
        result = c.execute("UPDATE farm_missions SET status=?, updated_at=? WHERE mission_id=?", (status, datetime.now(timezone.utc).isoformat(), mission_id))
        if result.rowcount == 0: raise HTTPException(404, "Mission not found")
        return row_dict(c.execute("SELECT * FROM farm_missions WHERE mission_id=?", (mission_id,)).fetchone())


@app.get("/api/crops")
def crops():
    with connect() as c: return [row_dict(r) for r in c.execute("SELECT * FROM crops ORDER BY name").fetchall()]


@app.put("/api/crops/{crop_id}")
def update_crop(crop_id: str, payload: dict):
    allowed = {"maturity_days", "minimum_temperature_f", "preferred_temperature_min_f", "preferred_temperature_max_f", "frost_tolerance_f", "heat_sensitivity_f", "water_requirement_in_week", "yield_per_acre", "planting_window_start", "planting_window_end", "harvest_window_start", "harvest_window_end", "production_status"}
    changes = {key: payload[key] for key in allowed if key in payload}
    if not changes: raise HTTPException(422, "No editable crop parameters supplied")
    for key, value in changes.items():
        if key.endswith("_days") and float(value) <= 0: raise HTTPException(422, "Maturity must be positive")
    with connect() as c:
        if not c.execute("SELECT 1 FROM crops WHERE crop_id=?", (crop_id,)).fetchone(): raise HTTPException(404, "Crop not found")
        c.execute(f"UPDATE crops SET {', '.join(f'{k}=?' for k in changes)}, source_type='OWNER_ENTERED' WHERE crop_id=?", (*changes.values(), crop_id))
        return row_dict(c.execute("SELECT * FROM crops WHERE crop_id=?", (crop_id,)).fetchone())


def _stage(as_of: date, planting: str | None, harvest: str | None, maturity: int | None) -> str:
    if not planting or not harvest: return "STAGE UNKNOWN"
    planted, harvested = date.fromisoformat(planting), date.fromisoformat(harvest)
    if as_of < planted: return "NOT PLANTED"
    if as_of > harvested + timedelta(days=7): return "PAST HARVEST WINDOW"
    if as_of >= harvested: return "HARVEST PERIOD"
    elapsed = max(0, (as_of - planted).days)
    fraction = elapsed / max(1, maturity or (harvested - planted).days)
    if fraction < .25: return "EARLY GROWTH"
    if fraction < .75: return "GROWING"
    return "APPROACHING HARVEST"


@app.get("/api/calendar")
def calendar(as_of_date: date | None = None):
    selected = as_of_date or date.today()
    with connect() as c:
        rows = c.execute("SELECT a.asset_id,a.name,a.acreage,c.crop_id,c.name crop,c.maturity_days,c.growth_stage,p.planting_date,p.expected_harvest_date,p.expected_yield,p.status FROM assets a JOIN production_plans p ON p.asset_id=a.asset_id JOIN crops c ON c.crop_id=p.crop_id WHERE a.asset_type='PLOT' ORDER BY p.expected_harvest_date").fetchall()
        return {"as_of_date": selected.isoformat(), "date_status": "RECORDED_CURRENT_DATE" if selected == date.today() else ("RECONSTRUCTED_PAST" if selected < date.today() else "PROJECTED_FUTURE"), "items": [{**row_dict(r), "stage": _stage(selected, r["planting_date"], r["expected_harvest_date"], r["maturity_days"])} for r in rows]}


@app.get("/api/dairy/weather")
def dairy_weather():
    payload = _weather_for_farm()
    risks = [r for r in _risk_records(payload) if r["condition"] == "DAIRY_HEAT"]
    current = payload.get("current") or {}
    try:
        thi = calculate_thi(current.get("temperature_f"), current.get("relative_humidity_pct"))
    except ValueError:
        thi = None
    return {"data_status": payload.get("data_status"), "temperature_f": current.get("temperature_f"), "relative_humidity_pct": current.get("relative_humidity_pct"), "thi": thi, "thi_formula": "NOAA-style outdoor THI approximation; not an indoor barn measurement", "risks": risks, "source": payload.get("provider"), "source_timestamp": payload.get("last_successful_refresh") or payload.get("retrieved_at"), "message": "Weather risk is an operational threshold signal, not an animal-health observation."}


def _pricing_row(product_id: str):
    with connect() as c:
        row = c.execute("SELECT pc.*, p.name product_name FROM pricing_configs pc LEFT JOIN products p ON p.product_id=pc.product_id WHERE pc.product_id=?", (product_id,)).fetchone()
        if not row: raise HTTPException(404, "Product pricing configuration not found")
        approved = c.execute("SELECT * FROM approved_prices WHERE product_id=? AND effective_start<=? AND (effective_end IS NULL OR effective_end>=?) ORDER BY effective_start DESC LIMIT 1", (product_id,date.today().isoformat(),date.today().isoformat())).fetchone()
        market = c.execute("SELECT * FROM market_observations WHERE product_id=? ORDER BY observation_date DESC LIMIT 1", (product_id,)).fetchone()
        seasons = [row_dict(r) for r in c.execute("SELECT * FROM seasonality_factors WHERE product_id=? ORDER BY month", (product_id,)).fetchall()]
        recent = c.execute("SELECT * FROM pricing_recommendations WHERE product_id=? ORDER BY created_at DESC LIMIT 1", (product_id,)).fetchone()
    result = row_dict(row); result["approved_record"] = row_dict(approved); result["market_observation"] = row_dict(market); result["seasonality"] = seasons; result["latest_recommendation"] = row_dict(recent); result["data_status"] = "SYNTHETIC"
    return result


@app.get("/api/pricing/products")
def pricing_products():
    with connect() as c: ids = [r[0] for r in c.execute("SELECT product_id FROM pricing_configs ORDER BY product_category, product_id").fetchall()]
    return [_pricing_row(pid) for pid in ids]


@app.get("/api/pricing/product/{product_id}")
def pricing_product(product_id: str): return _pricing_row(product_id)


@app.get("/api/pricing/market/{product_id}")
def pricing_market(product_id: str):
    with connect() as c: rows = [row_dict(r) for r in c.execute("SELECT * FROM market_observations WHERE product_id=? ORDER BY observation_date DESC", (product_id,)).fetchall()]
    return {"product_id":product_id,"observations":rows,"market_data_status":"SYNTHETIC_ONLY" if not any(r["classification"]=="OBSERVED" for r in rows) else "OBSERVED_AVAILABLE"}


@app.post("/api/pricing/recommend/{product_id}")
def pricing_recommend(product_id: str, payload: PricingScenarioInput):
    if payload.product_id != product_id: raise HTTPException(422, "Product ID mismatch")
    config = _pricing_row(product_id); market = config.get("market_observation")
    result = recommend_price(unit_cost=config["production_cost_per_unit"], target_margin=payload.target_margin, market_price=payload.market_reference if payload.market_reference is not None else (market["normalized_price"] if market else None), seasonality_factor=payload.seasonality_factor, supply_factor=payload.supply_factor, minimum_price=config["minimum_acceptable_price"], objective=payload.objective, inventory_age_days=payload.inventory_age_days, shelf_life_days=config.get("shelf_life_days"), weather_supply_factor=payload.weather_supply_factor, confidence=config.get("confidence","DEMO_ASSUMPTION"))
    now = datetime.now(timezone.utc).isoformat(); recommendation_id="recommendation-"+uuid.uuid4().hex[:12]
    with connect() as c:
        c.execute("INSERT INTO pricing_recommendations (recommendation_id,product_id,created_at,formula_version,inputs_json,cost_floor,target_margin_price,market_indicated_price,recommended_price,expected_gross_margin,conflict_warning,confidence,status,source_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (recommendation_id,product_id,now,PRICING_FORMULA_VERSION,json.dumps(payload.model_dump()),result["cost_floor"],result["target_margin_price"],result["market_indicated_price"],result["recommended_price"],result["expected_gross_margin_at_recommendation"],result["conflict_warning"],result["confidence"],"PROPOSED","CALCULATED"))
    result.update({"recommendation_id":recommendation_id,"product_id":product_id,"data_status":"CALCULATED","source_type":"CALCULATED"})
    return result


@app.post("/api/pricing/simulate")
def pricing_simulate(payload: PricingScenarioInput):
    config = _pricing_row(payload.product_id)
    result = simulate_price(price=payload.selling_price, unit_cost=config["production_cost_per_unit"], expected_volume=payload.expected_volume, sales_volume=payload.sales_volume, estimated_spoilage=payload.estimated_spoilage)
    result.update({"product_id":payload.product_id,"objective":payload.objective,"assumptions":payload.model_dump(),"data_status":"HYPOTHETICAL_SCENARIO"})
    return result


@app.post("/api/pricing/approve/{product_id}")
def approve_pricing(product_id: str, payload: PriceApproval, recommendation_id: str | None = None):
    config = _pricing_row(product_id); price = payload.price
    if price < config["minimum_acceptable_price"]: raise HTTPException(422, "Approved price cannot be below the configured minimum acceptable price")
    now = datetime.now(timezone.utc).isoformat(); approved_id="approved-"+uuid.uuid4().hex[:12]
    with connect() as c:
        old = c.execute("SELECT current_approved_price FROM pricing_configs WHERE product_id=?", (product_id,)).fetchone()[0]
        c.execute("UPDATE approved_prices SET effective_end=? WHERE product_id=? AND effective_end IS NULL", ((payload.effective_start-timedelta(days=1)).isoformat(),product_id))
        c.execute("INSERT INTO approved_prices VALUES (?,?,?,?,?,?,?,?,?,?)", (approved_id,product_id,price,payload.effective_start.isoformat(),payload.effective_end.isoformat() if payload.effective_end else None,payload.approved_by,recommendation_id,payload.reason,now,"OWNER_ENTERED"))
        c.execute("UPDATE pricing_configs SET current_approved_price=?,last_price_update=?,source_type='OWNER_ENTERED' WHERE product_id=?", (price,now,product_id))
        c.execute("INSERT INTO pricing_change_history VALUES (?,?,?,?,?,?,?,?,?)", ("change-"+uuid.uuid4().hex[:12],product_id,old,price,"APPROVED",payload.reason,approved_id,now,"OWNER_ENTERED"))
    return _pricing_row(product_id)


@app.get("/api/pricing/history/{product_id}")
def pricing_history(product_id: str):
    with connect() as c:
        return {"product_id":product_id,"approved_prices":[row_dict(r) for r in c.execute("SELECT * FROM approved_prices WHERE product_id=? ORDER BY effective_start DESC",(product_id,)).fetchall()],"changes":[row_dict(r) for r in c.execute("SELECT * FROM pricing_change_history WHERE product_id=? ORDER BY changed_at DESC",(product_id,)).fetchall()]}


@app.get("/api/pricing/calendar")
def pricing_calendar():
    with connect() as c:
        rows = c.execute("SELECT pc.product_id,pc.product_category,pc.unit,pc.production_cost_per_unit,pc.current_approved_price,pc.target_gross_margin,p.name FROM pricing_configs pc LEFT JOIN products p ON p.product_id=pc.product_id ORDER BY p.name").fetchall()
        factors = c.execute("SELECT * FROM seasonality_factors ORDER BY product_id,month").fetchall()
    factor_map={}
    for factor in factors: factor_map.setdefault(factor["product_id"],[]).append(row_dict(factor))
    return [{**row_dict(row),"months":factor_map.get(row["product_id"],[]),"data_status":"FORECAST_SCENARIO"} for row in rows]


@app.get("/api/pricing/alerts")
def pricing_alerts():
    alerts=[]
    for item in pricing_products():
        rec=item.get("latest_recommendation")
        if item["current_approved_price"] is not None and item["current_approved_price"] < item["production_cost_per_unit"]: alerts.append({"product_id":item["product_id"],"rule":"BELOW_COST","message":"Approved price is below configured production cost.","severity":"HIGH","trigger":{"price":item["current_approved_price"],"unit_cost":item["production_cost_per_unit"]}})
        if rec and rec.get("conflict_warning"): alerts.append({"product_id":item["product_id"],"rule":"MARKET_MARGIN_CONFLICT","message":rec["conflict_warning"],"severity":"MEDIUM","trigger":rec})
        if item["market_observation"] is None: alerts.append({"product_id":item["product_id"],"rule":"MISSING_MARKET_DATA","message":"No market observation is available; recommendation must rely on explicit demo assumptions.","severity":"LOW"})
    return {"alerts":alerts,"rules":"Deterministic pricing rules; not LLM-generated.","data_status":"SYNTHETIC"}


def _lot_state(conn, lot_id: str) -> dict:
    lot = conn.execute("SELECT l.*, p.name product_name, p.category product_category, sf.facility_type storage_type FROM inventory_lots l JOIN products p ON p.product_id=l.product_id LEFT JOIN storage_facilities sf ON sf.storage_id=l.storage_id WHERE l.lot_id=?", (lot_id,)).fetchone()
    if not lot:
        raise HTTPException(404, "Inventory lot not found")
    movements = conn.execute("SELECT * FROM inventory_movements WHERE lot_id=? ORDER BY movement_at", (lot_id,)).fetchall()
    reservations = conn.execute("SELECT * FROM inventory_reservations WHERE lot_id=? AND status='ACTIVE'", (lot_id,)).fetchall()
    on_hand = round(sum(movement_delta(m["movement_type"], m["quantity"]) for m in movements), 6)
    reserved = round(sum(r["quantity"] for r in reservations), 6)
    if on_hand < -1e-6:
        raise HTTPException(500, "Inventory ledger is inconsistent: negative on-hand quantity")
    result = row_dict(lot)
    result.update({"on_hand": max(0.0, on_hand), "reserved": reserved, "available": available_quantity(on_hand, reserved),
                   "movements": [row_dict(m) for m in movements], "reservations": [row_dict(r) for r in reservations],
                   "data_status": lot["source_type"], "formula_version": INVENTORY_FORMULA_VERSION})
    return result


@app.post("/api/inventory/lots")
def create_inventory_lot(payload: InventoryLotCreate):
    if payload.sell_by_date and payload.sell_by_date < payload.production_date:
        raise HTTPException(422, "Sell-by date must be on or after production date")
    lot_id = "lot-" + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        farm = c.execute("SELECT farm_id FROM farms LIMIT 1").fetchone()
        if not c.execute("SELECT 1 FROM products WHERE product_id=?", (payload.product_id,)).fetchone(): raise HTTPException(422, "Product not found")
        if payload.storage_id and not c.execute("SELECT 1 FROM storage_facilities WHERE storage_id=? AND farm_id=?", (payload.storage_id,farm["farm_id"])).fetchone(): raise HTTPException(422, "Storage facility not found")
        c.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (lot_id,farm["farm_id"],payload.product_id,payload.origin_asset_id,payload.lot_type,payload.production_date.isoformat(),payload.quantity_produced,payload.quantity_unit,payload.quality_grade,payload.storage_id,payload.sell_by_date.isoformat() if payload.sell_by_date else None,"AVAILABLE",f"{payload.reason} / owner-created", "OWNER_ENTERED", now, now))
        c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-"+uuid.uuid4().hex[:12],lot_id,now,"RECEIPT",payload.quantity_produced,payload.quantity_unit,payload.reason,lot_id,payload.created_by,now,"OWNER_ENTERED"))
        return _lot_state(c, lot_id)


@app.post("/api/inventory/lots/{lot_id}/transfer")
def transfer_inventory(lot_id: str, target_storage_id: str, payload: InventoryAction, unit: str):
    with connect() as c:
        state = _lot_state(c, lot_id)
        if not c.execute("SELECT 1 FROM storage_facilities WHERE storage_id=?", (target_storage_id,)).fetchone(): raise HTTPException(422, "Target storage facility not found")
        if payload.quantity > state["on_hand"]: raise HTTPException(422, "Transfer exceeds on-hand inventory")
        _record_inventory_movement(c, lot_id, "TRANSFER_OUT", payload, unit, payload.reference_id or ("transfer-"+uuid.uuid4().hex[:8]))
        in_payload = InventoryAction(quantity=payload.quantity, reason=payload.reason, created_by=payload.created_by, reference_id=payload.reference_id)
        _record_inventory_movement(c, lot_id, "TRANSFER_IN", in_payload, unit, payload.reference_id or ("transfer-in-"+uuid.uuid4().hex[:8]))
        c.execute("UPDATE inventory_lots SET storage_id=?,updated_at=? WHERE lot_id=?", (target_storage_id,datetime.now(timezone.utc).isoformat(),lot_id))
        return _lot_state(c, lot_id)


@app.get("/api/inventory/summary")
def inventory_summary(as_of_date: date | None = None):
    selected = as_of_date or date.today()
    with connect() as c:
        lots = [row_dict(r) for r in c.execute("SELECT lot_id FROM inventory_lots ORDER BY production_date DESC").fetchall()]
        states = [_lot_state(c, lot["lot_id"]) for lot in lots]
        forecasts = [row_dict(r) for r in c.execute("SELECT p.plan_id,p.asset_id,a.name plot_name,c.name product_name,p.expected_harvest_date,p.expected_yield,p.status FROM production_plans p JOIN assets a ON a.asset_id=p.asset_id JOIN crops c ON c.crop_id=p.crop_id WHERE p.expected_harvest_date>=? ORDER BY p.expected_harvest_date", (selected.isoformat(),)).fetchall()]
        storage = [row_dict(r) for r in c.execute("SELECT * FROM storage_facilities").fetchall()]
    by_product = {}
    for state in states:
        item = by_product.setdefault(state["product_id"], {"product_id":state["product_id"],"product_name":state["product_name"],"unit":state["quantity_unit"],"on_hand":0,"reserved":0,"available":0,"lot_count":0})
        for key in ("on_hand","reserved","available"): item[key] = round(item[key] + state[key], 6)
        item["lot_count"] += 1
    return {"products":list(by_product.values()),"lots":states,"future_forecast_production":forecasts,"storage":storage,"as_of_date":selected.isoformat(),"data_status":"SYNTHETIC","formula_version":INVENTORY_FORMULA_VERSION}


@app.get("/api/inventory/export.csv")
def export_inventory_csv():
    with connect() as c:
        rows = [row_dict(r) for r in c.execute("SELECT * FROM inventory_movements ORDER BY movement_at").fetchall()]
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else ["movement_id"]); writer.writeheader(); writer.writerows(rows)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=farmtwin-inventory-movements.csv"})


@app.get("/api/inventory/lots/{lot_id}/traceability")
def lot_traceability_route(lot_id: str):
    with connect() as c:
        state = _lot_state(c, lot_id)
        origin = c.execute("SELECT l.*,a.name origin_name,p.name product_name FROM inventory_lots l LEFT JOIN assets a ON a.asset_id=l.origin_asset_id JOIN products p ON p.product_id=l.product_id WHERE l.lot_id=?", (lot_id,)).fetchone()
    return {"lot":state,"origin":row_dict(origin),"timeline":[{"event":"PRODUCED","date":origin["production_date"],"detail":f"{origin['quantity_produced']} {origin['quantity_unit']} recorded from {origin['origin_name'] or 'unrecorded origin'}"}]+[{"event":m["movement_type"],"date":m["movement_at"],"detail":f"{m['quantity']} {m['unit']} — {m['reason']}"} for m in state["movements"]],"data_status":origin["source_type"]}


@app.get("/api/inventory/lots/{lot_id}")
def inventory_lot(lot_id: str):
    with connect() as c: return _lot_state(c, lot_id)


def _record_inventory_movement(conn, lot_id: str, movement_type: str, payload: InventoryAction, unit: str, reference_id: str | None = None):
    state = _lot_state(conn, lot_id)
    if unit != state["quantity_unit"]:
        raise HTTPException(422, f"Unit mismatch: lot uses {state['quantity_unit']}")
    movement_id = "movement-" + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", (movement_id, lot_id, now, movement_type, payload.quantity, unit, payload.reason, reference_id or payload.reference_id, payload.created_by, now, "OWNER_ENTERED"))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Duplicate inventory movement or reference") from exc
    return _lot_state(conn, lot_id)


@app.post("/api/inventory/lots/{lot_id}/movement/{movement_type}")
def inventory_movement(lot_id: str, movement_type: str, payload: InventoryAction, unit: str):
    allowed = {"ADJUSTMENT", "SPOILAGE", "DISPOSAL", "DONATION"}
    if movement_type not in allowed: raise HTTPException(422, "Movement type requires a dedicated receipt, reservation, or fulfillment workflow")
    with connect() as c:
        state = _lot_state(c, lot_id)
        if movement_type in {"SPOILAGE","DISPOSAL","DONATION"} and payload.quantity > state["on_hand"]: raise HTTPException(422, "Disposition exceeds physical on-hand inventory")
        if movement_type == "ADJUSTMENT" and state["on_hand"] + payload.quantity < 0: raise HTTPException(422, "Adjustment cannot create negative inventory")
        return _record_inventory_movement(c, lot_id, movement_type, payload, unit)


@app.post("/api/inventory/lots/{lot_id}/reserve")
def reserve_inventory(lot_id: str, payload: ReservationCreate, unit: str):
    with connect() as c:
        state = _lot_state(c, lot_id)
        if unit != state["quantity_unit"]: raise HTTPException(422, f"Unit mismatch: lot uses {state['quantity_unit']}")
        if payload.quantity > state["available"]: raise HTTPException(422, "Reservation exceeds available inventory")
        reservation_id = "reservation-" + uuid.uuid4().hex[:12]
        try:
            c.execute("INSERT INTO inventory_reservations VALUES (?,?,?,?,?,?,?,?,?)", (reservation_id, lot_id, payload.buyer_reference, payload.quantity, "ACTIVE", datetime.now(timezone.utc).isoformat(), payload.expires_at.isoformat() if payload.expires_at else None, payload.created_by, "OWNER_ENTERED"))
        except sqlite3.IntegrityError as exc: raise HTTPException(409, "Could not create reservation") from exc
        return _lot_state(c, lot_id)


@app.post("/api/inventory/reservations/{reservation_id}/release")
def release_reservation(reservation_id: str, created_by: str = "Farm owner"):
    with connect() as c:
        row = c.execute("SELECT * FROM inventory_reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
        if not row: raise HTTPException(404, "Reservation not found")
        if row["status"] != "ACTIVE": raise HTTPException(409, "Only active reservations can be released")
        c.execute("UPDATE inventory_reservations SET status='RELEASED' WHERE reservation_id=?", (reservation_id,))
        return _lot_state(c, row["lot_id"])


@app.post("/api/inventory/reservations/{reservation_id}/fulfill")
def fulfill_reservation(reservation_id: str, payload: InventoryAction, unit: str):
    with connect() as c:
        row = c.execute("SELECT * FROM inventory_reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
        if not row: raise HTTPException(404, "Reservation not found")
        if row["status"] != "ACTIVE": raise HTTPException(409, "Reservation is not active")
        if payload.quantity != row["quantity"]: raise HTTPException(422, "Fulfillment quantity must equal reservation quantity")
        state = _lot_state(c, row["lot_id"])
        if payload.quantity > state["available"]: raise HTTPException(422, "Sale fulfillment exceeds available inventory")
        _record_inventory_movement(c, row["lot_id"], "SALE", payload, unit, reservation_id)
        c.execute("UPDATE inventory_reservations SET status='FULFILLED' WHERE reservation_id=?", (reservation_id,))
        return _lot_state(c, row["lot_id"])


@app.get("/api/inventory/lots/{lot_id}/traceability")
def lot_traceability(lot_id: str):
    with connect() as c:
        state = _lot_state(c, lot_id)
        origin = c.execute("SELECT l.*,a.name origin_name,p.name product_name FROM inventory_lots l LEFT JOIN assets a ON a.asset_id=l.origin_asset_id JOIN products p ON p.product_id=l.product_id WHERE l.lot_id=?", (lot_id,)).fetchone()
    return {"lot":state,"origin":row_dict(origin),"timeline":[{"event":"PRODUCED","date":origin["production_date"],"detail":f"{origin['quantity_produced']} {origin['quantity_unit']} recorded from {origin['origin_name'] or 'unrecorded origin'}"}]+[{"event":m["movement_type"],"date":m["movement_at"],"detail":f"{m['quantity']} {m['unit']} — {m['reason']}"} for m in state["movements"]],"data_status":origin["source_type"]}


@app.get("/api/inventory/spoilage")
def inventory_spoilage(as_of_date: date | None = None):
    selected = as_of_date or date.today(); output=[]
    with connect() as c:
        lot_ids = [r[0] for r in c.execute("SELECT lot_id FROM inventory_lots").fetchall()]
        for lot_id in lot_ids:
            state = _lot_state(c, lot_id)
            price = c.execute("SELECT current_approved_price,shelf_life_days FROM pricing_configs WHERE product_id=?", (state["product_id"],)).fetchone()
            assessment = spoilage_assessment(quantity_on_hand=state["on_hand"], reserved_quantity=state["reserved"], sell_by=state["sell_by_date"], as_of=selected, shelf_life_days=price[1] if price else None, approved_price=price[0] if price else None)
            if assessment["risk"] not in {"LOW","UNKNOWN"}:
                output.append({"lot_id":lot_id,"product_id":state["product_id"],"product_name":state["product_name"],"unit":state["quantity_unit"],**assessment,"recommendation":"Do not sell expired product; for non-expired lots prioritize approved buyers, review storage, or model an owner-approved discount."})
    return {"assessments":output,"as_of_date":selected.isoformat(),"data_status":"CALCULATED","assumption":"Age-based demonstration rule; not a food-safety determination."}


@app.get("/api/dairy/summary")
def dairy_summary():
    with connect() as c:
        summary = row_dict(c.execute("SELECT * FROM dairy_summary LIMIT 1").fetchone())
        animals = [row_dict(r) for r in c.execute("SELECT * FROM dairy_animals WHERE archived=0 ORDER BY name").fetchall()]
        records = [row_dict(r) for r in c.execute("SELECT * FROM dairy_production_records ORDER BY production_date DESC").fetchall()]
        lots = [row_dict(r) for r in c.execute("SELECT lot_id FROM inventory_lots WHERE lot_type='DAIRY'").fetchall()]
        costs = c.execute("SELECT COALESCE(SUM(amount),0) FROM financial_transactions WHERE transaction_type='EXPENSE' AND category='Feed' AND classification='ACTUAL'").fetchone()[0]
        dashboard = dairy_dashboard(c)
    return {"summary":summary,"animals":animals,"production_records":records,"milk_lots":[inventory_lot(r["lot_id"]) for r in lots],"feed_expenses":costs,"dashboard":dashboard,"data_status":"SYNTHETIC","health_data_status":"NOT_RECORDED"}


@app.get("/api/dairy/dashboard")
def dairy_dashboard_route(as_of_date: date | None = None):
    payload = _weather_for_farm()
    risks = [r for r in _risk_records(payload) if r.get("condition") == "DAIRY_HEAT"]
    with connect() as c:
        return dairy_dashboard(c, as_of_date=as_of_date, weather=payload, weather_risks=risks)


@app.get("/api/dairy/animals")
def dairy_animals(include_archived: bool = False):
    with connect() as c:
        query = "SELECT * FROM dairy_animals"
        if not include_archived:
            query += " WHERE archived=0"
        query += " ORDER BY name"
        return {"animals": [row_dict(r) for r in c.execute(query).fetchall()], "data_status": "SYNTHETIC"}


@app.post("/api/dairy/animals")
def create_dairy_animal(payload: AnimalCreate):
    animal_id = "animal-" + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        try:
            c.execute("""INSERT INTO dairy_animals
                (animal_id,farm_id,tag,name,species,breed,birth_date,production_status,facility_id,avatar_key,notes,source_type,created_at,updated_at,sex,herd_category,acquisition_date,acquisition_cost,lactation_number,days_in_milk,last_calving_date,expected_dry_off_date,archived)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (animal_id,"farm-green-valley",payload.tag,payload.name,"CATTLE",payload.breed,payload.birth_date.isoformat() if payload.birth_date else None,payload.production_status,payload.facility_id or "facility-barn","cow-custom",payload.notes,"OWNER_ENTERED",now,now,payload.sex,payload.herd_category,None,None,0,None,None,None,0))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Animal tag already exists") from exc
        return row_dict(c.execute("SELECT * FROM dairy_animals WHERE animal_id=?", (animal_id,)).fetchone())


@app.get("/api/dairy/animals/{animal_id}")
def dairy_animal(animal_id: str):
    with connect() as c:
        animal = c.execute("SELECT * FROM dairy_animals WHERE animal_id=?", (animal_id,)).fetchone()
        if not animal: raise HTTPException(404, "Animal not found")
        records = [row_dict(r) for r in c.execute("SELECT * FROM dairy_production_records WHERE animal_id=? ORDER BY production_date DESC", (animal_id,)).fetchall()]
    return {"animal":row_dict(animal),"production_history":records,"health_data":"NOT_RECORDED","data_status":animal["source_type"]}


@app.put("/api/dairy/animals/{animal_id}")
def update_dairy_animal(animal_id: str, payload: AnimalUpdate):
    with connect() as c:
        existing = c.execute("SELECT * FROM dairy_animals WHERE animal_id=?", (animal_id,)).fetchone()
        if not existing: raise HTTPException(404, "Animal not found")
        updates = {"name": payload.name, "production_status": payload.production_status, "notes": payload.notes, "breed": payload.breed, "sex": payload.sex, "herd_category": payload.herd_category, "facility_id": payload.facility_id}
        if payload.tag:
            updates["tag"] = payload.tag
        c.execute(f"UPDATE dairy_animals SET {', '.join(f'{key}=?' for key in updates)},source_type='OWNER_ENTERED',updated_at=? WHERE animal_id=?", (*updates.values(),datetime.now(timezone.utc).isoformat(),animal_id))
        return row_dict(c.execute("SELECT * FROM dairy_animals WHERE animal_id=?", (animal_id,)).fetchone())


@app.post("/api/dairy/animals/{animal_id}/production")
def record_milk(animal_id: str, payload: DairyProductionCreate):
    if payload.unit not in {"liter", "liters", "gallon", "gallons"}: raise HTTPException(422, "Supported dairy units are liters and gallons")
    if payload.saleable_quantity + payload.withheld_quantity > payload.quantity: raise HTTPException(422, "Saleable plus withheld quantity cannot exceed produced quantity")
    if payload.withheld_quantity > 0 and not payload.withholding_reason: raise HTTPException(422, "A withholding reason is required when milk is withheld")
    with connect() as c:
        animal = c.execute("SELECT farm_id FROM dairy_animals WHERE animal_id=?", (animal_id,)).fetchone()
        if not animal: raise HTTPException(404, "Animal not found")
        record_id = "milk-record-" + uuid.uuid4().hex[:12]
        try:
            c.execute("""INSERT INTO dairy_production_records
                (dairy_record_id,farm_id,animal_id,production_date,quantity,unit,processing_status,saleable_quantity,source_type,notes,session_type,withheld_quantity,withholding_reason,operator,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (record_id,animal["farm_id"],animal_id,payload.production_date.isoformat(),payload.quantity,payload.unit,payload.processing_status,payload.saleable_quantity,"OWNER_ENTERED",payload.notes,payload.session_type,payload.withheld_quantity,payload.withholding_reason,payload.operator,datetime.now(timezone.utc).isoformat(),datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "A milking record already exists for this cow, date, and session") from exc
        return row_dict(c.execute("SELECT * FROM dairy_production_records WHERE dairy_record_id=?", (record_id,)).fetchone())


@app.get("/api/dairy/production")
def dairy_production(as_of_date: date | None = None, days: int = 30):
    selected = as_of_date or date.today(); start = selected - timedelta(days=max(1, min(days, 365)) - 1)
    with connect() as c:
        rows = [row_dict(r) for r in c.execute("SELECT r.*,a.name animal_name,a.tag FROM dairy_production_records r LEFT JOIN dairy_animals a ON a.animal_id=r.animal_id WHERE r.production_date BETWEEN ? AND ? ORDER BY r.production_date DESC,a.name", (start.isoformat(),selected.isoformat())).fetchall()]
    return {"records": rows, "start_date": start.isoformat(), "end_date": selected.isoformat(), "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.get("/api/dairy/milk-collections")
def dairy_collections():
    with connect() as c:
        return {"collections": [row_dict(r) for r in c.execute("SELECT * FROM dairy_milk_collections ORDER BY collection_date DESC").fetchall()], "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.post("/api/dairy/milk-collections")
def create_milk_collection(payload: MilkCollectionCreate):
    if payload.unit not in {"liter", "liters", "gallon", "gallons"}:
        raise HTTPException(422, "Supported milk collection units are liters and gallons")
    total_liters = liters(payload.quantity_collected, payload.unit)
    withheld_liters = liters(payload.withheld_quantity, payload.unit)
    approved_liters = liters(payload.approved_quantity, payload.unit) if payload.approved_quantity is not None else total_liters - withheld_liters
    if approved_liters < 0 or approved_liters + withheld_liters > total_liters + 1e-6:
        raise HTTPException(422, "Approved and withheld quantities cannot exceed collected milk")
    if withheld_liters > 0 and not payload.withholding_reason:
        raise HTTPException(422, "A withholding reason is required for withheld milk")
    if payload.sell_by_date and payload.sell_by_date < payload.collection_date:
        raise HTTPException(422, "Sell-by date must be on or after collection date")
    now = datetime.now(timezone.utc).isoformat(); collection_id = "collection-" + uuid.uuid4().hex[:12]; lot_id = None
    with connect() as c:
        farm = c.execute("SELECT farm_id FROM farms LIMIT 1").fetchone()
        restricted = c.execute("SELECT 1 FROM dairy_health_records WHERE farm_id=? AND milk_withdrawal_until>=?", (farm["farm_id"],payload.collection_date.isoformat())).fetchone()
        if restricted and approved_liters > 0:
            raise HTTPException(422, "Milk collection is blocked by an active recorded milk-withdrawal restriction")
        if payload.storage_id and not c.execute("SELECT 1 FROM storage_facilities WHERE storage_id=? AND farm_id=?", (payload.storage_id,farm["farm_id"])).fetchone():
            raise HTTPException(422, "Storage facility not found for this farm")
        if approved_liters > 0:
            lot_id = "lot-dairy-" + uuid.uuid4().hex[:12]
            c.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (lot_id,farm["farm_id"],"product-milk","facility-barn","DAIRY",payload.collection_date.isoformat(),approved_liters,"liter",payload.quality_status,payload.storage_id or "storage-barn",payload.sell_by_date.isoformat() if payload.sell_by_date else None,"AVAILABLE","Dairy collection / owner-recorded approval","OWNER_ENTERED",now,now))
            c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-"+uuid.uuid4().hex[:12],lot_id,now,"RECEIPT",approved_liters,"liter","Approved milk collection",collection_id,payload.created_by,now,"OWNER_ENTERED"))
        try:
            c.execute("""INSERT INTO dairy_milk_collections
                (collection_id,farm_id,collection_date,source_scope,quantity_collected,unit,approved_quantity,withheld_quantity,withholding_reason,storage_id,temperature_f,quality_status,processing_status,processing_date,sell_by_date,lot_id,source_type,notes,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (collection_id,farm["farm_id"],payload.collection_date.isoformat(),payload.source_scope,total_liters,"liter",approved_liters,withheld_liters,payload.withholding_reason,payload.storage_id,payload.temperature_f,payload.quality_status,"RAW",None,payload.sell_by_date.isoformat() if payload.sell_by_date else None,lot_id,"OWNER_ENTERED",payload.notes,now))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "A collection for this date and source scope already exists") from exc
        return {"collection": row_dict(c.execute("SELECT * FROM dairy_milk_collections WHERE collection_id=?", (collection_id,)).fetchone()), "lot": _lot_state(c, lot_id) if lot_id else None, "data_status": "OWNER_ENTERED"}


@app.get("/api/dairy/processing/specs")
def dairy_processing_specs():
    with connect() as c:
        return {"specs": [row_dict(r) for r in c.execute("SELECT s.*,p.name product_name FROM dairy_processing_specs s JOIN products p ON p.product_id=s.product_id ORDER BY p.name").fetchall()], "data_status": "SYNTHETIC_ASSUMPTIONS"}


@app.post("/api/dairy/processing")
def process_dairy_batch(payload: DairyProcessingCreate):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        spec = c.execute("SELECT * FROM dairy_processing_specs WHERE product_id=?", (payload.product_id,)).fetchone()
        if not spec: raise HTTPException(404, "No dairy processing specification exists for this product")
        state = _lot_state(c, payload.input_lot_id)
        if state["product_id"] != "product-milk" or state["quantity_unit"] != "liter": raise HTTPException(422, "Processing input must be a raw milk lot measured in liters")
        if payload.input_quantity > state["available"]: raise HTTPException(422, "Processing input exceeds available milk; no double consumption is allowed")
        output_quantity = round(payload.input_quantity / float(spec["input_quantity_per_output"]), 6)
        batch_id = "dairy-batch-" + uuid.uuid4().hex[:12]; output_lot_id = "lot-processed-" + uuid.uuid4().hex[:12]
        sell_by = (payload.processed_at + timedelta(days=int(spec["shelf_life_days"]))).isoformat()
        c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-"+uuid.uuid4().hex[:12],payload.input_lot_id,now,"PROCESSING_INPUT",payload.input_quantity,"liter",f"Input consumed for {payload.product_id}",batch_id,payload.created_by,now,"OWNER_ENTERED"))
        c.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (output_lot_id,"farm-green-valley",payload.product_id,"facility-barn","DAIRY",payload.processed_at.isoformat(),output_quantity,spec["output_unit"],"A","storage-barn",sell_by,"AVAILABLE",f"Processed from {payload.input_lot_id}; {spec['assumption_note']}","OWNER_ENTERED",now,now))
        c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-"+uuid.uuid4().hex[:12],output_lot_id,now,"RECEIPT",output_quantity,spec["output_unit"],"Dairy processing output",batch_id,payload.created_by,now,"OWNER_ENTERED"))
        c.execute("INSERT INTO dairy_processing_batches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (batch_id,"farm-green-valley",payload.input_lot_id,payload.product_id,payload.processed_at.isoformat(),payload.input_quantity,output_quantity,spec["output_unit"],output_lot_id,"COMPLETED",round(output_quantity*float(spec["processing_cost_per_output"]),2),spec["assumption_note"],"OWNER_ENTERED"))
        return {"batch": row_dict(c.execute("SELECT * FROM dairy_processing_batches WHERE batch_id=?", (batch_id,)).fetchone()), "input_lot": _lot_state(c,payload.input_lot_id), "output_lot": _lot_state(c,output_lot_id), "data_status": "OWNER_ENTERED"}


@app.get("/api/dairy/feed")
def dairy_feed():
    with connect() as c:
        feeds = [row_dict(r) for r in c.execute("SELECT * FROM dairy_feed_inventory ORDER BY feed_type").fetchall()]
        usage = [row_dict(r) for r in c.execute("SELECT u.*,f.feed_type FROM dairy_feed_usage u JOIN dairy_feed_inventory f ON f.feed_id=u.feed_id ORDER BY usage_date DESC").fetchall()]
    return {"feeds": feeds, "usage": usage, "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.post("/api/dairy/feed/purchases")
def create_feed_purchase(payload: FeedPurchaseCreate):
    feed_id = "feed-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute("INSERT INTO dairy_feed_inventory VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (feed_id,"farm-green-valley",payload.feed_type,payload.quantity,payload.unit,payload.cost_per_unit,payload.dry_matter_pct,payload.received_date.isoformat(),payload.supplier,"OWNER_ENTERED",payload.notes,now,now))
        amount = round(payload.quantity * payload.cost_per_unit, 2)
        c.execute("""INSERT OR IGNORE INTO financial_transactions
            (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,classification,cash_accrual,source_note,source_type,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", ("transaction-feed-"+uuid.uuid4().hex[:12],"farm-green-valley",payload.received_date.isoformat(),"EXPENSE","Feed",f"Dairy feed purchase: {payload.feed_type}",amount,"ACTUAL","CASH","Linked dairy feed purchase","OWNER_ENTERED",now))
        return row_dict(c.execute("SELECT * FROM dairy_feed_inventory WHERE feed_id=?", (feed_id,)).fetchone())


@app.post("/api/dairy/feed/{feed_id}/usage")
def record_feed_usage(feed_id: str, payload: FeedUsageCreate):
    usage_id = "feed-use-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        feed = c.execute("SELECT * FROM dairy_feed_inventory WHERE feed_id=?", (feed_id,)).fetchone()
        if not feed: raise HTTPException(404, "Feed record not found")
        if feed["unit"] != payload.unit: raise HTTPException(422, "Feed usage unit must match feed inventory unit")
        if payload.quantity > feed["quantity"]: raise HTTPException(422, "Feed usage exceeds remaining feed inventory")
        c.execute("UPDATE dairy_feed_inventory SET quantity=quantity-?,updated_at=? WHERE feed_id=?", (payload.quantity,now,feed_id))
        c.execute("INSERT INTO dairy_feed_usage VALUES (?,?,?,?,?,?,?,?,?,?)", (usage_id,"farm-green-valley",feed_id,payload.usage_date.isoformat(),payload.quantity,payload.unit,payload.herd_group,"OWNER_ENTERED",payload.notes,now))
        return row_dict(c.execute("SELECT * FROM dairy_feed_usage WHERE usage_id=?", (usage_id,)).fetchone())


@app.get("/api/dairy/tasks")
def dairy_tasks(status: str | None = None):
    with connect() as c:
        query = "SELECT * FROM dairy_tasks"; params=[]
        if status: query += " WHERE status=?"; params.append(status)
        query += " ORDER BY due_date,priority"
        return {"tasks": [row_dict(r) for r in c.execute(query,params).fetchall()], "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.post("/api/dairy/tasks")
def create_dairy_task(payload: DairyTaskCreate):
    task_id="task-"+uuid.uuid4().hex[:12]; now=datetime.now(timezone.utc).isoformat()
    with connect() as c:
        try:
            c.execute("INSERT INTO dairy_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (task_id,"farm-green-valley",payload.category,payload.priority,payload.assigned_worker,payload.due_date.isoformat(),payload.animal_id,payload.facility_id,"OPEN",payload.title,payload.completion_notes,"OWNER_ENTERED",now,now))
        except sqlite3.IntegrityError as exc: raise HTTPException(409, "Duplicate dairy task") from exc
        return row_dict(c.execute("SELECT * FROM dairy_tasks WHERE task_id=?", (task_id,)).fetchone())


@app.put("/api/dairy/tasks/{task_id}")
def update_dairy_task(task_id: str, payload: DairyTaskUpdate):
    allowed={"OPEN","IN_PROGRESS","COMPLETED","DISMISSED"}
    if payload.status not in allowed: raise HTTPException(422, "Invalid dairy task status")
    with connect() as c:
        result=c.execute("UPDATE dairy_tasks SET status=?,completion_notes=?,updated_at=? WHERE task_id=?", (payload.status,payload.completion_notes,datetime.now(timezone.utc).isoformat(),task_id))
        if result.rowcount==0: raise HTTPException(404,"Dairy task not found")
        return row_dict(c.execute("SELECT * FROM dairy_tasks WHERE task_id=?", (task_id,)).fetchone())


@app.get("/api/dairy/animals/{animal_id}/health")
def animal_health(animal_id: str):
    with connect() as c:
        if not c.execute("SELECT 1 FROM dairy_animals WHERE animal_id=?",(animal_id,)).fetchone(): raise HTTPException(404,"Animal not found")
        return {"records":[row_dict(r) for r in c.execute("SELECT * FROM dairy_health_records WHERE animal_id=? ORDER BY record_date DESC",(animal_id,)).fetchall()],"health_data_status":"RECORDED_ONLY"}


@app.post("/api/dairy/animals/{animal_id}/health")
def create_animal_health(animal_id: str, payload: DairyHealthCreate):
    record_id="health-"+uuid.uuid4().hex[:12]; now=datetime.now(timezone.utc).isoformat()
    with connect() as c:
        animal=c.execute("SELECT farm_id FROM dairy_animals WHERE animal_id=?",(animal_id,)).fetchone()
        if not animal: raise HTTPException(404,"Animal not found")
        c.execute("INSERT INTO dairy_health_records VALUES (?,?,?,?,?,?,?,?,?,?,?)", (record_id,animal["farm_id"],animal_id,payload.record_date.isoformat(),payload.record_type,payload.observation,1 if payload.veterinary_review_required else 0,payload.milk_withdrawal_until.isoformat() if payload.milk_withdrawal_until else None,payload.recorded_by,"OWNER_ENTERED",now))
        if payload.veterinary_review_required:
            c.execute("INSERT OR IGNORE INTO dairy_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("task-health-"+record_id,animal["farm_id"],"VETERINARY","HIGH",payload.recorded_by,payload.record_date.isoformat(),animal_id,"facility-barn","OPEN",f"Veterinary review: {payload.record_type}","","OWNER_ENTERED",now,now))
        return row_dict(c.execute("SELECT * FROM dairy_health_records WHERE health_record_id=?",(record_id,)).fetchone())


# Poultry and egg operations -------------------------------------------------
@app.get("/api/poultry/overview")
def poultry_overview_route(as_of_date: date | None = None):
    payload = _weather_for_farm()
    with connect() as c:
        return poultry_overview(c, as_of_date=as_of_date, weather=payload)


@app.get("/api/poultry/weather")
def poultry_weather_route():
    payload = _weather_for_farm()
    return {"data_status": payload.get("data_status", "UNAVAILABLE"), "provider": payload.get("provider"), "retrieved_at": payload.get("retrieved_at"), "current": payload.get("current"), "forecast": payload.get("forecast", [])[:7], "alerts": payload.get("alerts", []), "risks": poultry_weather_risks(payload), "note": "Outdoor provider/model weather is not an indoor coop sensor reading."}


@app.get("/api/poultry/flocks")
def poultry_flocks():
    with connect() as c:
        rows = [row_dict(r) for r in c.execute("SELECT f.*,pf.name facility_name FROM poultry_flocks f LEFT JOIN poultry_facilities pf ON pf.facility_id=f.facility_id ORDER BY f.name").fetchall()]
    return {"flocks": rows, "data_status": "SYNTHETIC_OR_OWNER_ENTERED", "formula_version": POULTRY_FORMULA_VERSION}


@app.post("/api/poultry/flocks")
def create_poultry_flock(payload: PoultryFlockCreate):
    flock_id = "flock-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        facility = c.execute("SELECT * FROM poultry_facilities WHERE facility_id=?", (payload.facility_id,)).fetchone()
        if not facility: raise HTTPException(422, "Poultry facility not found")
        occupied = c.execute("SELECT COALESCE(SUM(hens_count),0) FROM poultry_flocks WHERE facility_id=?", (payload.facility_id,)).fetchone()[0]
        if occupied + payload.hens_count > facility["hen_capacity"]: raise HTTPException(422, "Flock would exceed recorded henhouse capacity")
        c.execute("""INSERT INTO poultry_flocks
            (flock_id,farm_id,name,breed,hens_count,roosters_count,chicks_count,hatch_date,production_status,facility_id,expected_laying_rate,notes,source_type,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (flock_id, "farm-green-valley", payload.name, payload.breed, payload.hens_count, payload.roosters_count, payload.chicks_count, payload.hatch_date.isoformat() if payload.hatch_date else None, payload.production_status, payload.facility_id, payload.expected_laying_rate, payload.notes, "OWNER_ENTERED", now, now))
        return row_dict(c.execute("SELECT * FROM poultry_flocks WHERE flock_id=?", (flock_id,)).fetchone())


@app.put("/api/poultry/flocks/{flock_id}")
def update_poultry_flock(flock_id: str, payload: PoultryFlockUpdate):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        current = c.execute("SELECT * FROM poultry_flocks WHERE flock_id=?", (flock_id,)).fetchone()
        if not current: raise HTTPException(404, "Flock not found")
        facility = c.execute("SELECT * FROM poultry_facilities WHERE facility_id=?", (payload.facility_id,)).fetchone()
        if not facility: raise HTTPException(422, "Poultry facility not found")
        occupied = c.execute("SELECT COALESCE(SUM(hens_count),0) FROM poultry_flocks WHERE facility_id=? AND flock_id<>?", (payload.facility_id, flock_id)).fetchone()[0]
        if occupied + payload.hens_count > facility["hen_capacity"]: raise HTTPException(422, "Flock would exceed recorded henhouse capacity")
        c.execute("""UPDATE poultry_flocks SET name=?,breed=?,hens_count=?,roosters_count=?,chicks_count=?,hatch_date=?,production_status=?,facility_id=?,expected_laying_rate=?,notes=?,source_type='OWNER_ENTERED',updated_at=? WHERE flock_id=?""", (payload.name, payload.breed, payload.hens_count, payload.roosters_count, payload.chicks_count, payload.hatch_date.isoformat() if payload.hatch_date else None, payload.production_status, payload.facility_id, payload.expected_laying_rate, payload.notes, now, flock_id))
        return row_dict(c.execute("SELECT * FROM poultry_flocks WHERE flock_id=?", (flock_id,)).fetchone())


@app.get("/api/poultry/collections")
def poultry_collections(days: int = 30):
    if days < 1 or days > 366: raise HTTPException(422, "Days must be between 1 and 366")
    start = date.today() - timedelta(days=days - 1)
    with connect() as c:
        rows = [row_dict(r) for r in c.execute("SELECT c.*,f.name flock_name,f.breed,b.batch_id,b.accepted_eggs,b.hold_status,b.packaging_status FROM poultry_egg_collections c JOIN poultry_flocks f ON f.flock_id=c.flock_id LEFT JOIN poultry_egg_batches b ON b.collection_id=c.collection_id WHERE c.collection_date>=? ORDER BY c.collection_date DESC,c.collection_time", (start.isoformat(),)).fetchall()]
    return {"collections": rows, "data_status": "SYNTHETIC_OR_OWNER_ENTERED", "formula_version": POULTRY_FORMULA_VERSION}


@app.post("/api/poultry/collections")
def create_egg_collection(payload: EggCollectionCreate):
    rejected = payload.broken_eggs + payload.dirty_rejected
    if rejected > payload.eggs_collected: raise HTTPException(422, "Broken and dirty/rejected eggs cannot exceed collected eggs")
    now = datetime.now(timezone.utc).isoformat(); collection_id = "egg-collection-" + uuid.uuid4().hex[:12]; batch_id = "egg-batch-" + uuid.uuid4().hex[:12]
    accepted = payload.eggs_collected - rejected
    with connect() as c:
        flock = c.execute("SELECT * FROM poultry_flocks WHERE flock_id=?", (payload.flock_id,)).fetchone()
        if not flock: raise HTTPException(404, "Flock not found")
        if payload.eggs_collected > flock["hens_count"]: raise HTTPException(422, "One collection session cannot exceed the flock's recorded laying-hen count")
        if not c.execute("SELECT 1 FROM storage_facilities WHERE storage_id='storage-egg-room'").fetchone():
            c.execute("INSERT OR IGNORE INTO storage_facilities VALUES (?,?,?,?,?,?,?,?,?,?)", ("storage-egg-room", "farm-green-valley", "facility-coop", "EGG_STORAGE", 1000, "egg_or_package", "Eggs", "Cool, clean demonstration storage", "SYNTHETIC", now))
        try:
            c.execute("""INSERT INTO poultry_egg_collections
                (collection_id,farm_id,flock_id,collection_date,collection_time,eggs_collected,broken_eggs,dirty_rejected,accepted_for_grading,worker,notes,source_type,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (collection_id, "farm-green-valley", payload.flock_id, payload.collection_date.isoformat(), payload.collection_time, payload.eggs_collected, payload.broken_eggs, payload.dirty_rejected, accepted, payload.worker, payload.notes, "OWNER_ENTERED", now))
        except sqlite3.IntegrityError as exc: raise HTTPException(409, "A collection already exists for this flock, date, and collection time") from exc
        lot_id = None
        if accepted:
            lot_id = "lot-eggs-" + uuid.uuid4().hex[:12]
            sell_by = payload.collection_date + timedelta(days=21)
            c.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (lot_id, "farm-green-valley", "product-eggs-loose", "facility-coop", "CROP", payload.collection_date.isoformat(), accepted, "egg", "UNVERIFIED", "storage-egg-room", sell_by.isoformat(), "AVAILABLE", f"Poultry collection {collection_id}; grade not certified", "OWNER_ENTERED", now, now))
            c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-" + uuid.uuid4().hex[:12], lot_id, now, "RECEIPT", accepted, "egg", "Approved egg collection receipt", collection_id, payload.worker, now, "OWNER_ENTERED"))
        c.execute("""INSERT INTO poultry_egg_batches
            (batch_id,farm_id,flock_id,collection_id,collection_date,total_eggs,accepted_eggs,rejected_eggs,quality_status,size_category,grading_status,packaging_status,lot_id,hold_status,source_type,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (batch_id, "farm-green-valley", payload.flock_id, collection_id, payload.collection_date.isoformat(), payload.eggs_collected, accepted, rejected, "UNVERIFIED", None, "PENDING", "UNPACKAGED", lot_id, "AVAILABLE", "OWNER_ENTERED", now))
        return {"collection": row_dict(c.execute("SELECT * FROM poultry_egg_collections WHERE collection_id=?", (collection_id,)).fetchone()), "batch": row_dict(c.execute("SELECT * FROM poultry_egg_batches WHERE batch_id=?", (batch_id,)).fetchone()), "lot": _lot_state(c, lot_id) if lot_id else None, "data_status": "OWNER_ENTERED"}


@app.get("/api/poultry/batches")
def poultry_batches():
    with connect() as c:
        return {"batches": [row_dict(r) for r in c.execute("SELECT b.*,f.name flock_name FROM poultry_egg_batches b JOIN poultry_flocks f ON f.flock_id=b.flock_id ORDER BY b.collection_date DESC").fetchall()], "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.post("/api/poultry/packaging")
def package_eggs(payload: EggPackagingCreate):
    try: spec = package_spec(payload.package_type)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    input_eggs = payload.package_count * spec["eggs_per_package"]
    packaging_id = "egg-packaging-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        batch = c.execute("SELECT * FROM poultry_egg_batches WHERE batch_id=?", (payload.batch_id,)).fetchone()
        if not batch: raise HTTPException(404, "Egg batch not found")
        if batch["hold_status"] in {"HOLD", "QUARANTINED"}: raise HTTPException(409, "Restricted egg batch cannot be packaged or sold")
        if not batch["lot_id"]: raise HTTPException(422, "Egg batch has no accepted inventory lot")
        try:
            c.execute("INSERT INTO poultry_packaging_batches (packaging_id,farm_id,batch_id,input_eggs,package_type,package_count,eggs_per_package,packaging_date,product_id,output_lot_id,storage_id,quality_status,source_type,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (packaging_id, "farm-green-valley", payload.batch_id, input_eggs, payload.package_type, payload.package_count, spec["eggs_per_package"], payload.packaging_date.isoformat(), spec["product_id"], None, payload.storage_id, payload.quality_status, "OWNER_ENTERED", payload.notes, now))
        except sqlite3.IntegrityError as exc: raise HTTPException(409, "Duplicate packaging record for this batch, package type, and date") from exc
        state = _lot_state(c, batch["lot_id"])
        if input_eggs > state["available"]: raise HTTPException(422, "Packaging exceeds available accepted eggs")
        action = InventoryAction(quantity=input_eggs, reason=f"Packaging {payload.package_type} from egg batch {payload.batch_id}", created_by=payload.created_by, reference_id=packaging_id)
        _record_inventory_movement(c, batch["lot_id"], "PROCESSING_INPUT", action, "egg", packaging_id)
        output_lot = "lot-eggs-packaged-" + uuid.uuid4().hex[:12]
        sell_by = payload.packaging_date + timedelta(days=21)
        c.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (output_lot, "farm-green-valley", spec["product_id"], "facility-coop", "CROP", payload.packaging_date.isoformat(), payload.package_count, spec["unit"], payload.quality_status, payload.storage_id, sell_by.isoformat(), "AVAILABLE", f"Packaged from egg batch {payload.batch_id}; conversion {spec['eggs_per_package']} eggs/package", "OWNER_ENTERED", now, now))
        c.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-" + uuid.uuid4().hex[:12], output_lot, now, "RECEIPT", payload.package_count, spec["unit"], "Egg packaging output", packaging_id, payload.created_by, now, "OWNER_ENTERED"))
        c.execute("UPDATE poultry_packaging_batches SET output_lot_id=? WHERE packaging_id=?", (output_lot, packaging_id))
        remaining = _lot_state(c, batch["lot_id"])["available"]
        c.execute("UPDATE poultry_egg_batches SET packaging_status=? WHERE batch_id=?", ("PACKAGED" if remaining <= 0 else "PARTIALLY_PACKAGED", payload.batch_id))
        return {"packaging": row_dict(c.execute("SELECT * FROM poultry_packaging_batches WHERE packaging_id=?", (packaging_id,)).fetchone()), "source_lot": _lot_state(c, batch["lot_id"]), "output_lot": _lot_state(c, output_lot), "conversion": {"input_eggs": input_eggs, "eggs_per_package": spec["eggs_per_package"], "package_count": payload.package_count}, "data_status": "OWNER_ENTERED"}


@app.get("/api/poultry/inventory")
def poultry_inventory():
    with connect() as c:
        lots = [_lot_state(c, row["lot_id"]) for row in c.execute("SELECT l.lot_id FROM inventory_lots l JOIN products p ON p.product_id=l.product_id WHERE p.category='POULTRY' ORDER BY l.production_date DESC").fetchall()]
    return {"lots": lots, "available_eggs": sum(row["available"] for row in lots if row["quantity_unit"] == "egg"), "available_packages": sum(row["available"] for row in lots if row["quantity_unit"] != "egg"), "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.get("/api/poultry/feed")
def poultry_feed():
    with connect() as c:
        feeds = [row_dict(r) for r in c.execute("SELECT * FROM poultry_feed_inventory ORDER BY feed_type").fetchall()]
        usage = [row_dict(r) for r in c.execute("SELECT u.*,f.feed_type,p.name flock_name FROM poultry_feed_usage u JOIN poultry_feed_inventory f ON f.feed_id=u.feed_id JOIN poultry_flocks p ON p.flock_id=u.flock_id ORDER BY usage_date DESC").fetchall()]
    return {"feeds": feeds, "usage": usage, "data_status": "SYNTHETIC_OR_OWNER_ENTERED", "note": "Feed examples are records and planning assumptions, not veterinary nutrition advice."}


@app.post("/api/poultry/feed/purchases")
def create_poultry_feed_purchase(payload: PoultryFeedPurchaseCreate):
    feed_id = "poultry-feed-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute("INSERT INTO poultry_feed_inventory VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (feed_id, "farm-green-valley", payload.feed_type, payload.quantity, payload.unit, payload.cost_per_unit, payload.received_date.isoformat(), payload.supplier, "OWNER_ENTERED", payload.notes, now, now))
        c.execute("""INSERT INTO financial_transactions
            (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,classification,cash_accrual,source_note,source_type,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", ("txn-" + uuid.uuid4().hex[:12], "farm-green-valley", payload.received_date.isoformat(), "EXPENSE", "Poultry Feed", f"Poultry feed purchase: {payload.feed_type}", round(payload.quantity * payload.cost_per_unit, 2), "product-eggs-dozen", "ACTUAL", "CASH", "Owner-entered poultry feed purchase.", "OWNER_ENTERED", now))
        return row_dict(c.execute("SELECT * FROM poultry_feed_inventory WHERE feed_id=?", (feed_id,)).fetchone())


@app.post("/api/poultry/feed/{feed_id}/usage")
def record_poultry_feed_usage(feed_id: str, payload: PoultryFeedUsageCreate):
    usage_id = "poultry-usage-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        feed = c.execute("SELECT * FROM poultry_feed_inventory WHERE feed_id=?", (feed_id,)).fetchone()
        if not feed: raise HTTPException(404, "Poultry feed record not found")
        if not c.execute("SELECT 1 FROM poultry_flocks WHERE flock_id=?", (payload.flock_id,)).fetchone(): raise HTTPException(404, "Flock not found")
        if feed["unit"] != payload.unit: raise HTTPException(422, "Feed usage unit must match poultry feed inventory unit")
        if payload.quantity > feed["quantity"]: raise HTTPException(422, "Feed usage exceeds remaining poultry feed inventory")
        c.execute("UPDATE poultry_feed_inventory SET quantity=quantity-?,updated_at=? WHERE feed_id=?", (payload.quantity, now, feed_id))
        c.execute("INSERT INTO poultry_feed_usage VALUES (?,?,?,?,?,?,?,?,?,?)", (usage_id, "farm-green-valley", feed_id, payload.flock_id, payload.usage_date.isoformat(), payload.quantity, payload.unit, "OWNER_ENTERED", payload.notes, now))
        return row_dict(c.execute("SELECT * FROM poultry_feed_usage WHERE usage_id=?", (usage_id,)).fetchone())


@app.get("/api/poultry/tasks")
def poultry_tasks(status: str | None = None):
    query = "SELECT * FROM poultry_tasks"; params = []
    if status: query += " WHERE status=?"; params.append(status)
    query += " ORDER BY due_date,priority"
    with connect() as c: return {"tasks": [row_dict(r) for r in c.execute(query, params).fetchall()], "data_status": "SYNTHETIC_OR_OWNER_ENTERED"}


@app.post("/api/poultry/tasks")
def create_poultry_task(payload: PoultryTaskCreate):
    task_id = "poultry-task-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        try: c.execute("INSERT INTO poultry_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (task_id, "farm-green-valley", payload.category, payload.priority, payload.assigned_worker, payload.due_date.isoformat(), payload.flock_id, payload.facility_id, "OPEN", payload.title, payload.completion_notes, "OWNER_ENTERED", now, now))
        except sqlite3.IntegrityError as exc: raise HTTPException(409, "Duplicate poultry task") from exc
        return row_dict(c.execute("SELECT * FROM poultry_tasks WHERE task_id=?", (task_id,)).fetchone())


@app.put("/api/poultry/tasks/{task_id}")
def update_poultry_task(task_id: str, payload: PoultryTaskUpdate):
    if payload.status not in {"OPEN", "IN_PROGRESS", "COMPLETED", "DISMISSED"}: raise HTTPException(422, "Invalid poultry task status")
    with connect() as c:
        result = c.execute("UPDATE poultry_tasks SET status=?,completion_notes=?,updated_at=? WHERE task_id=?", (payload.status, payload.completion_notes, datetime.now(timezone.utc).isoformat(), task_id))
        if result.rowcount == 0: raise HTTPException(404, "Poultry task not found")
        return row_dict(c.execute("SELECT * FROM poultry_tasks WHERE task_id=?", (task_id,)).fetchone())


@app.get("/api/poultry/health")
def poultry_health():
    with connect() as c: return {"records": [row_dict(r) for r in c.execute("SELECT h.*,f.name flock_name FROM poultry_health_records h JOIN poultry_flocks f ON f.flock_id=h.flock_id ORDER BY event_date DESC").fetchall()], "data_status": "RECORDED_ONLY", "note": "No veterinary diagnosis or automatic product release is provided."}


@app.post("/api/poultry/health")
def create_poultry_health(payload: PoultryHealthCreate, flock_id: str):
    record_id = "poultry-health-" + uuid.uuid4().hex[:12]; now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        if not c.execute("SELECT 1 FROM poultry_flocks WHERE flock_id=?", (flock_id,)).fetchone(): raise HTTPException(404, "Flock not found")
        c.execute("INSERT INTO poultry_health_records VALUES (?,?,?,?,?,?,?,?,?,?,?)", (record_id, "farm-green-valley", flock_id, payload.event_date.isoformat(), payload.event_type, payload.observation, 1 if payload.veterinary_review_required else 0, 1 if payload.product_hold else 0, payload.recorded_by, "OWNER_ENTERED", now))
        if payload.product_hold:
            c.execute("UPDATE poultry_egg_batches SET hold_status='HOLD' WHERE flock_id=?", (flock_id,))
            c.execute("UPDATE inventory_lots SET lot_status='HOLD' WHERE lot_id IN (SELECT lot_id FROM poultry_egg_batches WHERE flock_id=? AND lot_id IS NOT NULL)", (flock_id,))
        return row_dict(c.execute("SELECT * FROM poultry_health_records WHERE health_record_id=?", (record_id,)).fetchone())


@app.post("/api/poultry/batches/{batch_id}/release")
def release_poultry_batch(batch_id: str, created_by: str = "Farm owner"):
    with connect() as c:
        batch = c.execute("SELECT * FROM poultry_egg_batches WHERE batch_id=?", (batch_id,)).fetchone()
        if not batch: raise HTTPException(404, "Egg batch not found")
        active_hold = c.execute("SELECT 1 FROM poultry_health_records WHERE flock_id=? AND product_hold=1", (batch["flock_id"],)).fetchone()
        if active_hold: raise HTTPException(409, "Batch cannot be released while a recorded flock product hold remains active")
        c.execute("UPDATE poultry_egg_batches SET hold_status='RELEASED',quality_status='OWNER_RELEASED' WHERE batch_id=?", (batch_id,))
        if batch["lot_id"]: c.execute("UPDATE inventory_lots SET lot_status='AVAILABLE' WHERE lot_id=?", (batch["lot_id"],))
        return {"batch": row_dict(c.execute("SELECT * FROM poultry_egg_batches WHERE batch_id=?", (batch_id,)).fetchone()), "released_by": created_by, "warning": "Owner release is a recordkeeping action, not a regulatory food-safety certification."}


@app.get("/api/poultry/egg-lots/{lot_id}/traceability")
def poultry_lot_traceability(lot_id: str):
    with connect() as c:
        try: state = _lot_state(c, lot_id)
        except HTTPException: raise
        origin = c.execute("SELECT * FROM poultry_egg_batches WHERE lot_id=?", (lot_id,)).fetchone()
        packaging = [row_dict(r) for r in c.execute("SELECT * FROM poultry_packaging_batches WHERE output_lot_id=? OR batch_id=?", (lot_id, origin["batch_id"] if origin else "")).fetchall()]
    return {"lot": state, "egg_batch": row_dict(origin), "packaging": packaging, "timeline": [{"event": "EGG_LOT", "date": state["production_date"], "detail": f"{state['quantity_produced']} {state['quantity_unit']} from recorded poultry collection"}] + [{"event": m["movement_type"], "date": m["movement_at"], "detail": f"{m['quantity']} {m['unit']} — {m['reason']}"} for m in state["movements"]], "data_status": state["source_type"]}


@app.get("/api/sales/buyers")
def sales_buyers(search: str | None = None, category: str | None = None, include_archived: bool = False):
    query = "SELECT * FROM buyers WHERE farm_id=(SELECT farm_id FROM farms LIMIT 1)"; params=[]
    if not include_archived: query += " AND archived=0"
    if search: query += " AND (business_name LIKE ? OR contact_name LIKE ?)"; params += [f"%{search}%", f"%{search}%"]
    if category: query += " AND category=?"; params.append(category)
    query += " ORDER BY business_name"
    with connect() as c: return [row_dict(r) for r in c.execute(query, params).fetchall()]


@app.post("/api/sales/buyers")
def create_buyer(payload: BuyerCreate):
    buyer_id = "buyer-" + uuid.uuid4().hex[:12]; now=datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute("INSERT INTO buyers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (buyer_id,"farm-green-valley",payload.business_name,payload.category,None,None,None,payload.contact_name,payload.contact_role,payload.email,payload.phone,payload.contact_verification_status,payload.delivery_preferences,payload.minimum_order_quantity,"PROSPECT",None,payload.notes,"OWNER_ENTERED",None,0,now,now))
        return row_dict(c.execute("SELECT * FROM buyers WHERE buyer_id=?", (buyer_id,)).fetchone())


@app.get("/api/sales/buyers/{buyer_id}")
def get_buyer(buyer_id: str):
    with connect() as c:
        buyer=c.execute("SELECT * FROM buyers WHERE buyer_id=?",(buyer_id,)).fetchone()
        if not buyer: raise HTTPException(404,"Buyer not found")
        prefs=[row_dict(r) for r in c.execute("SELECT bp.*,p.name product_name,p.unit FROM buyer_preferences bp JOIN products p ON p.product_id=bp.product_id WHERE buyer_id=?",(buyer_id,)).fetchall()]
        activities=[row_dict(r) for r in c.execute("SELECT * FROM sales_activities WHERE buyer_id=? ORDER BY activity_date DESC",(buyer_id,)).fetchall()]
    return {"buyer":row_dict(buyer),"preferences":prefs,"activities":activities,"data_status":buyer["source_type"]}


@app.put("/api/sales/buyers/{buyer_id}")
def update_buyer(buyer_id: str, payload: BuyerCreate):
    with connect() as c:
        if not c.execute("SELECT 1 FROM buyers WHERE buyer_id=?", (buyer_id,)).fetchone(): raise HTTPException(404, "Buyer not found")
        c.execute("UPDATE buyers SET business_name=?,category=?,contact_name=?,contact_role=?,email=?,phone=?,contact_verification_status=?,delivery_preferences=?,minimum_order_quantity=?,notes=?,source_type='OWNER_ENTERED',updated_at=? WHERE buyer_id=?", (payload.business_name,payload.category,payload.contact_name,payload.contact_role,payload.email,payload.phone,payload.contact_verification_status,payload.delivery_preferences,payload.minimum_order_quantity,payload.notes,datetime.now(timezone.utc).isoformat(),buyer_id))
        return row_dict(c.execute("SELECT * FROM buyers WHERE buyer_id=?",(buyer_id,)).fetchone())


@app.get("/api/sales/match/{product_id}")
def match_buyers(product_id: str, quantity: float, delivery_date: date):
    if quantity <= 0: raise HTTPException(422,"Quantity must be positive")
    with connect() as c:
        product=c.execute("SELECT * FROM products WHERE product_id=?",(product_id,)).fetchone()
        if not product: raise HTTPException(404,"Product not found")
        price=c.execute("SELECT current_approved_price FROM pricing_configs WHERE product_id=?",(product_id,)).fetchone()
        approved=float(price[0]) if price and price[0] is not None else None
        lots=[]
        for row in c.execute("SELECT lot_id FROM inventory_lots WHERE product_id=?",(product_id,)).fetchall():
            state=_lot_state(c,row[0])
            if state["lot_status"] == "AVAILABLE" and state["available"]>0: lots.append(state)
        available=sum(x["available"] for x in lots); sell_by=min((x["sell_by_date"] for x in lots if x["sell_by_date"]),default=None)
        buyers=[]
        for buyer in c.execute("SELECT * FROM buyers WHERE archived=0").fetchall():
            suppressed=c.execute("SELECT 1 FROM outreach_suppressions WHERE buyer_id=?",(buyer["buyer_id"],)).fetchone() is not None
            pref=c.execute("SELECT * FROM buyer_preferences WHERE buyer_id=? AND product_id=?",(buyer["buyer_id"],product_id)).fetchone()
            result=match_score(preference_match=pref is not None,category_match=buyer["category"] in {"INDEPENDENT_GROCERY","SUPERMARKET","RESTAURANT","FOOD_COOPERATIVE","FOOD_HUB","WHOLESALE_DISTRIBUTOR","INSTITUTIONAL"},quantity=quantity,minimum_order=float(pref["min_quantity"] if pref else buyer["minimum_order_quantity"]),available=available,price=approved or 0,min_price=float(pref["min_price"]) if pref and pref["min_price"] is not None else None,max_price=float(pref["max_price"]) if pref and pref["max_price"] is not None else None,delivery_date=delivery_date,sell_by_date=sell_by,suppressed=suppressed)
            if result["eligible"]: buyers.append({"buyer":row_dict(buyer),"score":result["score"],"explanation":result["explanation"],"product_id":product_id,"quantity":quantity,"approved_price":approved,"data_status":"CALCULATED"})
    return {"matches":sorted(buyers,key=lambda x:x["score"],reverse=True),"product_id":product_id,"quantity":quantity,"available_inventory":available,"approved_price":approved,"classification":"POTENTIAL_COMMERCIAL_OPPORTUNITY","formula_version":SALES_FORMULA_VERSION}


@app.post("/api/sales/offers")
def create_offer(payload: OfferCreate):
    offer_id="offer-"+uuid.uuid4().hex[:12]; now=datetime.now(timezone.utc).isoformat(); lines=[]
    with connect() as c:
        buyer=c.execute("SELECT * FROM buyers WHERE buyer_id=? AND archived=0",(payload.buyer_id,)).fetchone()
        if not buyer: raise HTTPException(404,"Buyer not found or archived")
        for item in payload.lines:
            state=_lot_state(c,item.lot_id)
            if state["product_id"] != item.product_id: raise HTTPException(422,"Lot does not belong to selected product")
            if state["lot_status"] != "AVAILABLE": raise HTTPException(422,"Restricted, held, spoiled, or otherwise unavailable lots cannot be offered")
            if state["quantity_unit"] != item.unit: raise HTTPException(422,"Offer unit does not match lot unit")
            if item.quantity > state["available"]: raise HTTPException(422,f"Offer exceeds available inventory for {state['product_name']}")
            config=c.execute("SELECT current_approved_price,minimum_acceptable_price FROM pricing_configs WHERE product_id=?",(item.product_id,)).fetchone()
            if not config or config[0] is None: raise HTTPException(422,"No approved price is available")
            unit_price=float(item.unit_price if item.unit_price is not None else config[0])
            if unit_price < float(config[1]): raise HTTPException(422,"Price is below the approved minimum price floor")
            lines.append({"product_id":item.product_id,"product_name":state["product_name"],"lot_id":item.lot_id,"quantity":item.quantity,"unit":item.unit,"quality_grade":item.quality_grade or state["quality_grade"],"unit_price":unit_price,"line_total":round(item.quantity*unit_price,2),"price_source":"OWNER_OVERRIDE" if item.unit_price is not None else "APPROVED_PRICE"})
        total=offer_total(lines)
        c.execute("INSERT INTO wholesale_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(offer_id,"farm-green-valley",payload.buyer_id,payload.proposed_delivery_date.isoformat(),payload.expiration_date.isoformat() if payload.expiration_date else None,payload.payment_terms,payload.delivery_terms,payload.notes,total,"DRAFT","OWNER_ENTERED",now,now))
        for line in lines: c.execute("INSERT INTO offer_line_items VALUES (?,?,?,?,?,?,?,?,?,?)",("offer-line-"+uuid.uuid4().hex[:12],offer_id,line["product_id"],line["lot_id"],line["quantity"],line["unit"],line["quality_grade"],line["unit_price"],line["line_total"],line["price_source"]))
    return {"offer_id":offer_id,"buyer":row_dict(buyer),"lines":lines,"total_value":total,"status":"DRAFT","classification":"NONBINDING_OFFER","data_status":"CALCULATED"}


def _offer_detail(offer_id: str):
    with connect() as c:
        offer=c.execute("SELECT o.*,b.business_name,b.contact_name,b.email FROM wholesale_offers o JOIN buyers b ON b.buyer_id=o.buyer_id WHERE o.offer_id=?",(offer_id,)).fetchone()
        if not offer: raise HTTPException(404,"Offer not found")
        lines=[row_dict(r) for r in c.execute("SELECT li.*,p.name product_name FROM offer_line_items li JOIN products p ON p.product_id=li.product_id WHERE offer_id=?",(offer_id,)).fetchall()]
        draft=c.execute("SELECT * FROM email_drafts WHERE offer_id=? ORDER BY created_at DESC LIMIT 1",(offer_id,)).fetchone()
    return {"offer":row_dict(offer),"lines":lines,"email_draft":row_dict(draft)}


@app.get("/api/sales/offers/{offer_id}")
def get_offer(offer_id: str): return _offer_detail(offer_id)


@app.post("/api/sales/offers/{offer_id}/email-draft")
def create_email_draft(offer_id: str):
    detail=_offer_detail(offer_id); offer=detail["offer"]
    farm=_farm(); result=draft_email(farm_name=farm["name"],farm_location=farm["location"],buyer_name=offer["business_name"],contact_name=offer["contact_name"],lines=detail["lines"],delivery_date=offer["proposed_delivery_date"])
    draft_id="draft-"+uuid.uuid4().hex[:12]; now=datetime.now(timezone.utc).isoformat()
    with connect() as c: c.execute("INSERT INTO email_drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(draft_id,offer_id,offer["email"],offer["contact_name"],result["subject"],result["body"],"DRAFT",None,None,"DETERMINISTIC_TEMPLATE",now,now))
    return {"draft_id":draft_id,**result,"recipient_email":offer["email"],"recipient_name":offer["contact_name"],"approval_required":True}


@app.post("/api/sales/email-drafts/{draft_id}/export")
def export_email_draft(draft_id: str):
    with connect() as c:
        draft=c.execute("SELECT * FROM email_drafts WHERE draft_id=?",(draft_id,)).fetchone()
        if not draft: raise HTTPException(404,"Email draft not found")
        now=datetime.now(timezone.utc).isoformat(); c.execute("UPDATE email_drafts SET status='EXPORTED',exported_at=?,updated_at=? WHERE draft_id=?",(now,now,draft_id))
        return {"draft":row_dict(c.execute("SELECT * FROM email_drafts WHERE draft_id=?",(draft_id,)).fetchone()),"sent":False,"message":"Recorded as exported only; no email was sent."}


@app.get("/api/sales/pipeline")
def sales_pipeline():
    with connect() as c: rows=[row_dict(r) for r in c.execute("SELECT o.*,b.business_name FROM buyer_opportunities o JOIN buyers b ON b.buyer_id=o.buyer_id ORDER BY o.updated_at DESC").fetchall()]
    return {"opportunities":rows,"stages":["PROSPECT","QUALIFIED","OFFER_DRAFTED","OFFER_SHARED","NEGOTIATION","ORDER_CONFIRMED","FULFILLMENT","WON","LOST"],"data_status":"SYNTHETIC"}


@app.put("/api/sales/pipeline/{opportunity_id}")
def update_pipeline(opportunity_id: str, payload: PipelineUpdate):
    allowed={"PROSPECT","QUALIFIED","OFFER_DRAFTED","OFFER_SHARED","NEGOTIATION","ORDER_CONFIRMED","FULFILLMENT","WON","LOST"}
    if payload.stage not in allowed: raise HTTPException(422,"Invalid sales pipeline stage")
    with connect() as c:
        if not c.execute("SELECT 1 FROM buyer_opportunities WHERE opportunity_id=?",(opportunity_id,)).fetchone(): raise HTTPException(404,"Opportunity not found")
        c.execute("UPDATE buyer_opportunities SET stage=?,owner_notes=COALESCE(?,owner_notes),next_action=COALESCE(?,next_action),updated_at=? WHERE opportunity_id=?",(payload.stage,payload.owner_notes,payload.next_action,datetime.now(timezone.utc).isoformat(),opportunity_id))
        return row_dict(c.execute("SELECT * FROM buyer_opportunities WHERE opportunity_id=?",(opportunity_id,)).fetchone())


@app.post("/api/sales/offers/{offer_id}/confirm")
def confirm_order(offer_id: str, payload: OrderConfirm):
    detail=_offer_detail(offer_id); offer=detail["offer"]
    if offer["status"] not in {"DRAFT","APPROVED","SHARED"}: raise HTTPException(409,"Offer is not confirmable in its current status")
    order_id="order-"+uuid.uuid4().hex[:12]; now=datetime.now(timezone.utc).isoformat(); reservations=[]
    with connect() as c:
        for line in detail["lines"]:
            state=_lot_state(c,line["lot_id"])
            if state["lot_status"] != "AVAILABLE": raise HTTPException(422,"Order cannot be confirmed from a restricted or unavailable lot")
            if line["quantity"] > state["available"]: raise HTTPException(422,"Order cannot be confirmed: inventory is no longer available")
            reservation_id="reservation-"+uuid.uuid4().hex[:12]
            c.execute("INSERT INTO inventory_reservations VALUES (?,?,?,?,?,?,?,?,?)",(reservation_id,line["lot_id"],f"Order {order_id}",line["quantity"],"ACTIVE",now,offer["proposed_delivery_date"],payload.created_by,"OWNER_ENTERED")); reservations.append((line,reservation_id))
        c.execute("INSERT INTO customer_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(order_id,"farm-green-valley",offer["buyer_id"],offer_id,date.today().isoformat(),offer["proposed_delivery_date"],"CONFIRMED",offer["total_value"],payload.buyer_confirmation_reference,now,now,"OWNER_ENTERED"))
        for line,reservation_id in reservations: c.execute("INSERT INTO order_line_items VALUES (?,?,?,?,?,?,?,?,?)",("order-line-"+uuid.uuid4().hex[:12],order_id,line["product_id"],line["lot_id"],reservation_id,line["quantity"],line["unit"],line["unit_price"],line["line_total"]))
        c.execute("UPDATE wholesale_offers SET status='ORDER_CONFIRMED',updated_at=? WHERE offer_id=?",(now,offer_id))
    return {"order_id":order_id,"offer_id":offer_id,"status":"CONFIRMED","total_value":offer["total_value"],"reservations_created":len(reservations),"revenue_recognition":"Not automatically posted; finance recognition follows fulfillment policy."}


@app.get("/api/sales/orders")
def sales_orders(status: str | None = None):
    with connect() as c:
        query="SELECT o.*,b.business_name FROM customer_orders o JOIN buyers b ON b.buyer_id=o.buyer_id"; params=[]
        if status: query += " WHERE o.status=?"; params.append(status)
        return [row_dict(r) for r in c.execute(query+" ORDER BY o.order_date DESC",params).fetchall()]


@app.post("/api/sales/orders/{order_id}/cancel")
def cancel_order(order_id: str):
    with connect() as c:
        order=c.execute("SELECT * FROM customer_orders WHERE order_id=?",(order_id,)).fetchone()
        if not order: raise HTTPException(404,"Order not found")
        if order["status"] in {"FULFILLED","CANCELLED"}: raise HTTPException(409,"Order cannot be cancelled in its current status")
        c.execute("UPDATE customer_orders SET status='CANCELLED',updated_at=? WHERE order_id=?",(datetime.now(timezone.utc).isoformat(),order_id))
        reservations=c.execute("SELECT reservation_id FROM order_line_items WHERE order_id=?",(order_id,)).fetchall()
        for row in reservations: c.execute("UPDATE inventory_reservations SET status='RELEASED' WHERE reservation_id=? AND status='ACTIVE'",(row[0],))
        return {"order_id":order_id,"status":"CANCELLED","reservations_released":len(reservations)}


@app.post("/api/sales/orders/{order_id}/fulfill")
def fulfill_order(order_id: str, payload: OrderConfirm):
    with connect() as c:
        order=c.execute("SELECT * FROM customer_orders WHERE order_id=?",(order_id,)).fetchone()
        if not order: raise HTTPException(404,"Order not found")
        if order["status"] != "CONFIRMED": raise HTTPException(409,"Only confirmed orders can be fulfilled")
        lines=c.execute("SELECT * FROM order_line_items WHERE order_id=?",(order_id,)).fetchall()
        for line in lines:
            reservation=c.execute("SELECT * FROM inventory_reservations WHERE reservation_id=?",(line["reservation_id"],)).fetchone()
            if not reservation or reservation["status"] != "ACTIVE": raise HTTPException(409,"Order reservation is no longer active")
            state = _lot_state(c,line["lot_id"])
            if state["lot_status"] != "AVAILABLE": raise HTTPException(422,"Held or restricted lot cannot be fulfilled")
            action=InventoryAction(quantity=line["quantity"],reason=f"Fulfillment of order {order_id}",created_by=payload.created_by,reference_id=order_id)
            _record_inventory_movement(c,line["lot_id"],"SALE",action,line["unit"],order_id)
            c.execute("UPDATE inventory_reservations SET status='FULFILLED' WHERE reservation_id=?",(line["reservation_id"],))
        now=datetime.now(timezone.utc).isoformat(); c.execute("UPDATE customer_orders SET status='FULFILLED',updated_at=? WHERE order_id=?",(now,order_id))
        return {"order_id":order_id,"status":"FULFILLED","lines_fulfilled":len(lines),"finance_status":"No duplicate finance transaction created by inventory fulfillment."}


@app.get("/api/ai/status")
def ai_status():
    status=provider_status()
    return {**status,"connection_status":"CONNECTED" if status["available"] else "UNAVAILABLE","deterministic_mode":True,"keys_server_side":True}


@app.get("/api/ai/tools")
def ai_tools():
    return [{k:v for k,v in tool.items() if k != "call"} for tool in tool_registry().values()]


@app.post("/api/ai/runs")
def create_ai_run(payload: AgentRunRequest):
    result=run_agent(payload.request)
    return result


@app.get("/api/ai/runs/{run_id}")
def ai_run(run_id: str):
    result=get_run(run_id)
    if result.get("error"): raise HTTPException(404,result["error"])
    return result


@app.get("/api/ai/runs/{run_id}/export")
def export_ai_run(run_id: str):
    result=get_run(run_id)
    if result.get("error"): raise HTTPException(404,result["error"])
    result.pop("final_response",None)
    for call in result.get("calls",[]):
        call.pop("input_summary",None); call.pop("output_summary",None)
    return {"run":result,"export_status":"SANITIZED"}


@app.get("/api/ai/tokenomics")
def ai_tokenomics():
    with connect() as c:
        rows=[row_dict(r) for r in c.execute("SELECT * FROM agent_calls ORDER BY started_at DESC").fetchall()]
    numeric=lambda key: sum(r[key] for r in rows if r.get(key) is not None)
    completed=len({r["run_id"] for r in rows})
    return {"model_calls":len(rows),"completed_runs":completed,"input_tokens":numeric("input_tokens"),"cached_input_tokens":numeric("cached_input_tokens"),"output_tokens":numeric("output_tokens"),"total_tokens":numeric("total_tokens"),"average_latency_ms":round(sum(r["latency_ms"] for r in rows if r.get("latency_ms") is not None)/max(1,len(rows)),2),"cost":"UNAVAILABLE","cost_status":"UNAVAILABLE","scale_assumptions":{"runs_per_user_per_month":20,"users":100,"users_10000":10000},"note":"Provider pricing for the configured course gateway/model has not been verified; no dollar estimate is invented."}


def _finance_period(period: str):
    today = date.today()
    if period == "month": start = today.replace(day=1)
    elif period == "quarter": start = today.replace(month=((today.month - 1)//3)*3 + 1, day=1)
    else: start = today.replace(month=1, day=1)
    return start.isoformat(), today.isoformat()


def _finance_totals(start: str, end: str, classification: str | None = "ACTUAL"):
    with connect() as c:
        params = [start, end]
        query = "SELECT COALESCE(SUM(CASE WHEN transaction_type='REVENUE' THEN amount ELSE 0 END),0) revenue, COALESCE(SUM(CASE WHEN transaction_type='EXPENSE' THEN amount ELSE 0 END),0) expenses FROM financial_transactions WHERE transaction_date BETWEEN ? AND ?"
        if classification:
            query += " AND classification=?"; params.append(classification)
        row = c.execute(query, params).fetchone()
        cogs = c.execute("SELECT COALESCE(SUM(amount),0) FROM financial_transactions WHERE transaction_date BETWEEN ? AND ? AND transaction_type='EXPENSE' AND classification=? AND category IN ('Seeds','Seed and transplants','Fertilizer','Pesticides','Agricultural labor','Labor','Feed','Packaging','Transportation','Storage')", (start,end,classification or "ACTUAL")).fetchone()[0]
        categories = [row_dict(r) for r in c.execute("SELECT category, transaction_type, ROUND(SUM(amount),2) amount FROM financial_transactions WHERE transaction_date BETWEEN ? AND ? AND classification=? GROUP BY category,transaction_type ORDER BY amount DESC", (start,end,classification or "ACTUAL")).fetchall()]
        monthly = [row_dict(r) for r in c.execute("SELECT substr(transaction_date,1,7) period, ROUND(SUM(CASE WHEN transaction_type='REVENUE' THEN amount ELSE 0 END),2) revenue, ROUND(SUM(CASE WHEN transaction_type='EXPENSE' THEN amount ELSE 0 END),2) expenses FROM financial_transactions WHERE transaction_date BETWEEN ? AND ? AND classification=? GROUP BY substr(transaction_date,1,7) ORDER BY period", (start,end,classification or "ACTUAL")).fetchall()]
    revenue, expenses = row[0], row[1]
    gross = gross_profit(revenue, cogs)
    operating = operating_profit(revenue, cogs, max(0, expenses-cogs))
    return {"period":{"start":start,"end":end},"classification":classification or "ALL","formula_version":FORMULA_VERSION,"revenue":revenue,"cogs":cogs,"gross_profit":serialize(gross["gross_profit"]),"gross_margin_pct":serialize(gross["gross_margin_pct"]),"operating_expenses":round(max(0,expenses-cogs),2),"operating_profit":serialize(operating["operating_profit"]),"cash_inflows":revenue,"cash_outflows":expenses,"net_operating_cash_movement":round(revenue-expenses,2),"expense_categories":categories,"monthly":monthly,"data_status":"SYNTHETIC"}


@app.get("/api/finance/summary")
def finance_summary(period: str = "year", classification: str = "ACTUAL"):
    if period not in {"month","quarter","year"}: raise HTTPException(422, "Period must be month, quarter, or year")
    return _finance_totals(*_finance_period(period), classification)


@app.get("/api/finance/transactions")
def finance_transactions(period: str = "year", classification: str | None = None):
    start, end = _finance_period(period)
    with connect() as c:
        query = "SELECT * FROM financial_transactions WHERE transaction_date BETWEEN ? AND ?"; params: list = [start,end]
        if classification:
            query += " AND classification=?"; params.append(classification)
        query += " ORDER BY transaction_date DESC, transaction_type"
        return [row_dict(r) for r in c.execute(query, params).fetchall()]


@app.post("/api/finance/transactions")
def create_transaction(payload: FinancialTransactionCreate):
    if payload.transaction_type not in {"EXPENSE","REVENUE"}: raise HTTPException(422, "Transaction type must be EXPENSE or REVENUE")
    if payload.classification not in {"ACTUAL","BUDGET","FORECAST"}: raise HTTPException(422, "Invalid classification")
    now = datetime.now(timezone.utc).isoformat(); transaction_id = "txn-owner-" + uuid.uuid4().hex[:12]
    with connect() as c:
        try:
            c.execute("INSERT INTO financial_transactions (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,asset_id,vendor_customer,classification,cash_accrual,source_note,source_type,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (transaction_id, "farm-green-valley", payload.transaction_date.isoformat(), payload.transaction_type, payload.category, payload.description, payload.amount, payload.product_id, payload.asset_id, payload.vendor_customer, payload.classification, payload.cash_accrual, payload.source_note, "OWNER_ENTERED", now))
        except sqlite3.IntegrityError as exc: raise HTTPException(409, "Duplicate or invalid financial transaction") from exc
        return row_dict(c.execute("SELECT * FROM financial_transactions WHERE transaction_id=?", (transaction_id,)).fetchone())


@app.get("/api/finance/budgets")
def finance_budgets(period: str = "year"):
    start, end = _finance_period(period)
    with connect() as c:
        rows = c.execute("SELECT b.*, COALESCE(SUM(t.amount),0) actual_amount FROM budgets b LEFT JOIN financial_transactions t ON t.farm_id=b.farm_id AND t.category=b.category AND t.transaction_type=b.budget_type AND t.classification='ACTUAL' AND t.transaction_date BETWEEN b.period_start AND b.period_end WHERE b.period_start BETWEEN ? AND ? GROUP BY b.budget_id ORDER BY b.period_start,b.budget_type,b.category", (start,end)).fetchall()
        output=[]
        for r in rows:
            item=row_dict(r); item["variance"]=round(item["actual_amount"]-item["budgeted_amount"],2); item["variance_pct"]=(round(item["variance"]/item["budgeted_amount"]*100,2) if item["budgeted_amount"] else None); item["favorable"]=(item["variance"]>=0 if item["budget_type"]=="REVENUE" else item["variance"]<=0); output.append(item)
        return output


@app.get("/api/finance/plot/{asset_id}")
def plot_financials(asset_id: str):
    with connect() as c:
        plot = c.execute("SELECT a.name,c.name crop,p.expected_yield,p.actual_yield,p.estimated_cost,p.expected_revenue FROM assets a JOIN production_plans p ON p.asset_id=a.asset_id JOIN crops c ON c.crop_id=p.crop_id WHERE a.asset_id=?", (asset_id,)).fetchone()
        if not plot: raise HTTPException(404, "Plot not found")
        actual = c.execute("SELECT COALESCE(SUM(CASE WHEN transaction_type='REVENUE' THEN amount ELSE 0 END),0), COALESCE(SUM(CASE WHEN transaction_type='EXPENSE' THEN amount ELSE 0 END),0) FROM financial_transactions WHERE asset_id=? AND classification='ACTUAL'", (asset_id,)).fetchone()
    has_actual = actual[0] > 0 or actual[1] > 0
    revenue, cost, units, status = (actual[0], actual[1], plot["actual_yield"] or plot["expected_yield"], "ACTUAL") if has_actual else (plot["expected_revenue"], plot["estimated_cost"], plot["expected_yield"], "FORECAST")
    return {"plot":plot["name"],"crop":plot["crop"],"total_production_cost":cost,"direct_materials":cost*0.45,"labor_expenses":cost*0.35,"allocated_overhead":cost*0.20,"saleable_yield":units,"unit_production_cost":serialize(unit_cost(cost,units)),"average_selling_price":serialize(money(revenue/units if units else 0)),"revenue":revenue,"gross_profit":serialize(gross_profit(revenue,cost)["gross_profit"]),"gross_margin_pct":serialize(gross_profit(revenue,cost)["gross_margin_pct"]),"status":status,"data_status":"SYNTHETIC" if status=="FORECAST" else "OWNER_ENTERED"}


@app.get("/api/finance/dairy")
def dairy_financials():
    with connect() as c:
        expenses = c.execute("SELECT COALESCE(SUM(amount),0) FROM financial_transactions WHERE transaction_type='EXPENSE' AND (dairy_id IS NOT NULL OR category IN ('Feed','Veterinary expenses')) AND classification='ACTUAL'").fetchone()[0]
        dairy = c.execute("SELECT daily_milk_liters FROM dairy_summary LIMIT 1").fetchone()[0]
        revenue = c.execute("SELECT COALESCE(SUM(amount),0) FROM financial_transactions WHERE transaction_type='REVENUE' AND product_id='product-milk' AND classification='ACTUAL'").fetchone()[0]
    return {"total_dairy_costs":expenses,"milk_produced_liters":dairy*365,"cost_per_liter":serialize(unit_cost(expenses,dairy*365)),"dairy_revenue":revenue,"gross_profit":serialize(gross_profit(revenue,expenses)["gross_profit"]),"break_even_milk_price":serialize(break_even_price(expenses,dairy*365,0)),"data_status":"SYNTHETIC","note":"Seeded dairy costs and milk records are synthetic; individual animal cost precision is not assumed."}


@app.post("/api/finance/investments/evaluate")
def evaluate_investment(payload: InvestmentAssumptions):
    annual_cash = payload.annual_incremental_revenue - payload.annual_operating_costs - payload.annual_maintenance
    taxable_cash = annual_cash * (1-payload.tax_rate)
    flows = [-payload.initial_investment-payload.working_capital] + [taxable_cash] * payload.lifespan_years
    flows[-1] += payload.working_capital_recovery + payload.residual_value
    result = {"project_name":payload.project_name,"formula_version":FORMULA_VERSION,"initial_investment":payload.initial_investment,"annual_cash_flow":taxable_cash,"cash_flows":flows,"npv":serialize(npv(payload.initial_investment,[taxable_cash]*payload.lifespan_years,payload.discount_rate,payload.working_capital,payload.working_capital_recovery,payload.residual_value)),"irr":serialize(irr(flows)),"payback_years":serialize(payback_period(flows)),"roi_pct":serialize((sum(flows[1:])-payload.initial_investment)/payload.initial_investment*100 if payload.initial_investment else None),"status":"HYPOTHETICAL","data_status":"OWNER_ENTERED"}
    return result


@app.get("/api/finance/insights")
def finance_insights():
    summary = _finance_totals(*_finance_period("year"), "ACTUAL")
    insights=[]
    if summary["gross_margin_pct"] is not None and summary["gross_margin_pct"] < 0: insights.append({"rule":"NEGATIVE_GROSS_MARGIN","severity":"HIGH","message":"Recorded costs exceed recorded revenue in the selected period."})
    if summary["net_operating_cash_movement"] < 0: insights.append({"rule":"NEGATIVE_CASH_MOVEMENT","severity":"MEDIUM","message":"Recorded cash outflows exceed recorded cash inflows; this is not the same as accounting profit."})
    with connect() as c:
        over = c.execute("SELECT COUNT(*) FROM budgets b JOIN (SELECT category, SUM(amount) actual FROM financial_transactions WHERE classification='ACTUAL' GROUP BY category) t ON t.category=b.category WHERE b.budget_type='EXPENSE' AND t.actual>b.budgeted_amount").fetchone()[0]
    if over: insights.append({"rule":"BUDGET_OVERRUN","severity":"MEDIUM","message":f"{over} synthetic budget categories exceed their budgeted amounts."})
    if not insights: insights.append({"rule":"NO_FLAGGED_RULES","severity":"LOW","message":"No configured finance warning rules were triggered for the selected period."})
    return {"formula_version":FORMULA_VERSION,"insights":insights,"rules":"Deterministic rules over recorded synthetic transactions; not LLM-generated.","data_status":"SYNTHETIC"}


@app.get("/api/finance/export.csv")
def export_finance_csv():
    with connect() as c: rows=[row_dict(r) for r in c.execute("SELECT * FROM financial_transactions ORDER BY transaction_date").fetchall()]
    output=io.StringIO(); writer=csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else ["transaction_id"]); writer.writeheader(); writer.writerows(rows)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=farmtwin-financial-transactions.csv"})


@app.get("/api/summaries")
def summaries():
    with connect() as c:
        dairy = row_dict(c.execute("SELECT * FROM dairy_summary LIMIT 1").fetchone())
        crop_count = c.execute("SELECT COUNT(*) n FROM assets WHERE asset_type='PLOT'").fetchone()[0]
        harvest = [row_dict(r) for r in c.execute("SELECT a.name, c.name crop, p.expected_harvest_date, p.expected_yield, p.status FROM production_plans p JOIN assets a ON a.asset_id=p.asset_id JOIN crops c ON c.crop_id=p.crop_id ORDER BY p.expected_harvest_date LIMIT 5").fetchall()]
        expenses = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
        revenue = c.execute("SELECT COALESCE(SUM(expected_revenue),0) FROM production_plans").fetchone()[0]
        acres = c.execute("SELECT COALESCE(SUM(acreage),0) FROM assets WHERE asset_type='PLOT'").fetchone()[0]
        activities = [row_dict(r) for r in c.execute("SELECT * FROM activities ORDER BY activity_date DESC LIMIT 4").fetchall()]
        return {"active_crop_plots": crop_count, "planted_acres": acres, "dairy": dairy, "upcoming_harvests": harvest, "synthetic_expenses": expenses, "synthetic_expected_revenue": revenue, "synthetic_expected_profit": revenue-expenses, "activities": activities, "data_status": "SYNTHETIC"}

