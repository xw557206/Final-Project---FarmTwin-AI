"""Deterministic pricing functions. No model or external market text participates in arithmetic."""
from decimal import Decimal, ROUND_HALF_UP

FORMULA_VERSION = "pricing-v1"


def _d(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite(): raise ValueError("Numeric assumption must be finite")
    return result


def _price(value) -> Decimal:
    result = _d(value)
    if result < 0: raise ValueError("Price cannot be negative")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def gross_margin(selling_price, unit_cost) -> Decimal:
    price, cost = _price(selling_price), _price(unit_cost)
    if price <= 0: raise ValueError("Selling price must be greater than zero")
    return ((price - cost) / price).quantize(Decimal("0.0001"))


def target_margin_price(unit_cost, target_margin) -> Decimal:
    cost, margin = _price(unit_cost), _d(target_margin)
    if cost < 0 or margin < 0 or margin >= 1: raise ValueError("Margin must be between 0 and 1")
    return (cost / (Decimal("1") - margin)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def adjusted_market_reference(comparable_market_price, seasonality_factor=1, supply_factor=1) -> Decimal | None:
    if comparable_market_price is None: return None
    price, season, supply = _price(comparable_market_price), _d(seasonality_factor), _d(supply_factor)
    if season <= 0 or supply < 0: raise ValueError("Seasonality and supply factors are invalid")
    return (price * season * supply).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_market_price(price, quoted_unit, normalized_unit, package_size=1) -> Decimal:
    value, size = _price(price), _d(package_size)
    if size <= 0: raise ValueError("Package size must be positive")
    if quoted_unit.lower() == normalized_unit.lower(): return (value / size).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    conversions = {("case", "lb"): Decimal("1"), ("dozen", "unit"): Decimal("12"), ("gallon", "liter"): Decimal("3.78541"), ("liter", "gallon"): Decimal("0.264172")}
    factor = conversions.get((quoted_unit.lower(), normalized_unit.lower()))
    if factor is None: raise ValueError(f"Incompatible units: {quoted_unit} cannot be normalized to {normalized_unit}")
    return (value / size / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recommend_price(*, unit_cost, target_margin, market_price=None, seasonality_factor=1, supply_factor=1, minimum_price=None, objective="margin_preservation", inventory_age_days=0, shelf_life_days=None, weather_supply_factor=1, confidence="DEMO_ASSUMPTION") -> dict:
    cost = _price(unit_cost); floor = _price(minimum_price if minimum_price is not None else cost)
    target = target_margin_price(cost, target_margin)
    market = adjusted_market_reference(market_price, seasonality_factor, supply_factor) if market_price is not None else None
    if market is not None and _d(weather_supply_factor) <= 0: raise ValueError("Weather supply factor must be positive")
    if market is not None: market = (market * _d(weather_supply_factor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    conflict = None
    if market is not None and market < target:
        conflict = "Market-indicated price is below the target-margin price; owner must choose margin protection, competitiveness, or clearance explicitly."
    if objective == "market_competitiveness" and market is not None: recommendation = max(floor, market)
    elif objective == "inventory_clearance" and market is not None: recommendation = max(floor, (market * Decimal("0.95")).quantize(Decimal("0.01")))
    else: recommendation = max(floor, target)
    perishability_note = None
    if shelf_life_days and inventory_age_days >= shelf_life_days * .75:
        perishability_note = "Inventory age is near the configured shelf-life window; consider an owner-approved disposition scenario. No price was changed automatically."
    return {"formula_version":FORMULA_VERSION,"unit_cost":float(cost),"cost_floor":float(floor),"target_margin":float(_d(target_margin)),"target_margin_price":float(target),"market_indicated_price":float(market) if market is not None else None,"recommended_price":float(recommendation),"expected_gross_margin_at_recommendation":float(gross_margin(recommendation,cost)),"expected_gross_margin_at_market":float(gross_margin(market,cost)) if market and market > 0 else None,"conflict_warning":conflict,"perishability_note":perishability_note,"objective":objective,"confidence":confidence,"market_status":"AVAILABLE" if market is not None else "UNAVAILABLE","assumptions":{"seasonality_factor":float(seasonality_factor),"supply_factor":float(supply_factor),"weather_supply_factor":float(weather_supply_factor),"inventory_age_days":inventory_age_days,"shelf_life_days":shelf_life_days}}


def simulate_price(*, price, unit_cost, expected_volume, sales_volume=None, estimated_spoilage=0, variable_cost_per_unit=0) -> dict:
    selling_price, cost, volume = _price(price), _price(unit_cost), _d(expected_volume)
    if volume < 0 or _d(estimated_spoilage) < 0 or _d(estimated_spoilage) > 1: raise ValueError("Volume or spoilage assumption is invalid")
    sales = _d(sales_volume if sales_volume is not None else volume * (Decimal("1")-_d(estimated_spoilage)))
    if sales < 0 or sales > volume: raise ValueError("Sales volume must be between zero and expected volume")
    revenue = (selling_price * sales).quantize(Decimal("0.01")); cogs = (cost * sales).quantize(Decimal("0.01")); variable = (_price(variable_cost_per_unit) * sales).quantize(Decimal("0.01"))
    return {"formula_version":FORMULA_VERSION,"selling_price":float(selling_price),"expected_volume":float(volume),"sales_volume":float(sales),"estimated_remaining_stock":float(volume-sales),"estimated_inventory_at_risk":float(volume* _d(estimated_spoilage)),"revenue":float(revenue),"cogs":float(cogs),"gross_profit":float(revenue-cogs),"gross_margin":float(gross_margin(selling_price,cost)),"contribution_margin":float(revenue-variable),"break_even_price":float(cost+_price(variable_cost_per_unit)),"classification":"HYPOTHETICAL_SCENARIO"}
