"""Deterministic, Decimal-safe financial calculations for FarmTwin AI."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

FORMULA_VERSION = "finance-v1"
CENT = Decimal("0.01")


def money(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Amount must be numeric") from exc
    if not result.is_finite():
        raise ValueError("Amount must be finite")
    return result.quantize(CENT, rounding=ROUND_HALF_UP)


def production_cost(direct_materials, direct_labor, attributable_operating, allocated_overhead) -> Decimal:
    values = [money(v) for v in (direct_materials, direct_labor, attributable_operating, allocated_overhead)]
    if any(v < 0 for v in values): raise ValueError("Costs cannot be negative")
    return sum(values, Decimal("0.00")).quantize(CENT)


def unit_cost(total_allocated_production_cost, saleable_units) -> Decimal:
    total, units = money(total_allocated_production_cost), Decimal(str(saleable_units))
    if units <= 0: raise ValueError("Saleable units must be greater than zero")
    return (total / units).quantize(CENT, rounding=ROUND_HALF_UP)


def contribution_margin(revenue, variable_costs) -> dict:
    rev, costs = money(revenue), money(variable_costs)
    margin = (rev - costs).quantize(CENT)
    return {"revenue": rev, "variable_costs": costs, "contribution_margin": margin, "contribution_margin_pct": (margin / rev if rev else None)}


def gross_profit(revenue, cogs) -> dict:
    rev, cost = money(revenue), money(cogs)
    profit = (rev - cost).quantize(CENT)
    return {"revenue": rev, "cogs": cost, "gross_profit": profit, "gross_margin_pct": (profit / rev if rev else None)}


def operating_profit(revenue, cogs, operating_expenses) -> dict:
    rev, cost, expenses = money(revenue), money(cogs), money(operating_expenses)
    profit = (rev - cost - expenses).quantize(CENT)
    return {"revenue": rev, "cogs": cost, "operating_expenses": expenses, "operating_profit": profit}


def break_even_quantity(fixed_costs, unit_price, variable_unit_cost) -> Decimal:
    fixed, price, variable = money(fixed_costs), money(unit_price), money(variable_unit_cost)
    margin = price - variable
    if margin <= 0: raise ValueError("Unit price must exceed variable unit cost")
    return (fixed / margin).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def break_even_price(fixed_costs, expected_units, variable_unit_cost) -> Decimal:
    fixed, units, variable = money(fixed_costs), Decimal(str(expected_units)), money(variable_unit_cost)
    if units <= 0: raise ValueError("Expected units must be greater than zero")
    return (fixed / units + variable).quantize(CENT, rounding=ROUND_HALF_UP)


def allocation(amount, method: str, basis_value: float, target_basis: float) -> Decimal:
    total, basis, target = money(amount), Decimal(str(basis_value)), Decimal(str(target_basis))
    if total < 0 or basis <= 0 or target < 0: raise ValueError("Allocation values are invalid")
    if method.upper() == "DIRECT": return money(target)
    return (total * target / basis).quantize(CENT, rounding=ROUND_HALF_UP)


def depreciation(purchase_price, residual_value, useful_life_years) -> Decimal:
    price, residual, life = money(purchase_price), money(residual_value), Decimal(str(useful_life_years))
    if life <= 0 or residual < 0 or price < residual: raise ValueError("Invalid depreciation assumptions")
    return ((price - residual) / life).quantize(CENT, rounding=ROUND_HALF_UP)


def npv(initial_investment, cash_flows: Iterable, discount_rate: float, working_capital=0, recovery=0, residual_value=0) -> Decimal:
    initial, rate = money(initial_investment), Decimal(str(discount_rate))
    if rate <= -1: raise ValueError("Discount rate must be greater than -100%")
    total = -initial - money(working_capital)
    flows = list(cash_flows)
    for index, flow in enumerate(flows, 1):
        terminal = money(recovery) + money(residual_value) if index == len(flows) else Decimal("0")
        total += (money(flow) + terminal) / ((Decimal("1") + rate) ** index)
    return total.quantize(CENT, rounding=ROUND_HALF_UP)


def irr(cash_flows: Iterable, max_iterations=200) -> Decimal | None:
    flows = [money(f) for f in cash_flows]
    if not flows or not any(f < 0 for f in flows) or not any(f > 0 for f in flows): return None
    # A single sign change is required for a well-defined simple IRR in this MVP.
    signs = [f > 0 for f in flows]
    if sum(1 for a, b in zip(signs, signs[1:]) if a != b) != 1: return None
    low, high = Decimal("-0.99"), Decimal("10")
    def value(rate): return sum(flow / ((Decimal("1") + rate) ** i) for i, flow in enumerate(flows))
    while value(low) * value(high) > 0 and high < Decimal("1000"):
        high *= 2
    if value(low) * value(high) > 0: return None
    for _ in range(max_iterations):
        mid = (low + high) / 2
        current = value(mid)
        if abs(current) < Decimal("0.0001"): return mid.quantize(Decimal("0.0001"))
        if value(low) * current <= 0: high = mid
        else: low = mid
    return ((low + high) / 2).quantize(Decimal("0.0001"))


def payback_period(cash_flows: Iterable) -> Decimal | None:
    flows = [money(f) for f in cash_flows]
    if not flows: return None
    cumulative = flows[0]
    for year, flow in enumerate(flows[1:], 1):
        previous = cumulative
        cumulative += flow
        if cumulative >= 0:
            if flow == 0: return Decimal(year)
            return (Decimal(year - 1) + abs(previous) / flow).quantize(Decimal("0.01"))
    return None


def serialize(value):
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, dict): return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list): return [serialize(v) for v in value]
    return value
