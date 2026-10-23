"""Bounded AI orchestration for FarmTwin.

The model may select roles and summarize evidence. Allowlisted deterministic
tools own all arithmetic and state-changing business rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import time
import uuid
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import CONFIG
from .db import connect

MAX_MODEL_CALLS = 3
MAX_TOOL_CALLS = 32
MAX_OUTPUT_TOKENS = 900
MAX_RUN_SECONDS = 60
MAX_TOTAL_TOKENS = 5000


class ProviderUnavailable(RuntimeError):
    pass


@dataclass
class ModelResult:
    text: str
    provider: str
    model: str
    usage: dict[str, int | None]
    latency_ms: float


class ModelProvider:
    provider = "UNAVAILABLE"
    model = "UNAVAILABLE"

    def status(self) -> dict:
        return {"available": False, "provider": self.provider, "model": self.model, "message": "No verified AI provider is configured."}

    def complete(self, messages: list[dict[str, str]], *, max_output_tokens: int = MAX_OUTPUT_TOKENS) -> ModelResult:
        raise ProviderUnavailable(self.status()["message"])


class OpenAIResponsesProvider(ModelProvider):
    provider = "OPENAI"

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def status(self) -> dict:
        return {"available": True, "provider": self.provider, "model": self.model, "message": "Configured; API access is verified only when a call succeeds."}

    def complete(self, messages: list[dict[str, str]], *, max_output_tokens: int = MAX_OUTPUT_TOKENS) -> ModelResult:
        prompt = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        body = json.dumps({"model": self.model, "input": prompt, "max_output_tokens": max_output_tokens}).encode()
        request = Request("https://api.openai.com/v1/responses", data=body, headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}, method="POST")
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ProviderUnavailable(f"OpenAI request failed: {exc}") from exc
        usage = payload.get("usage") or {}
        details = usage.get("input_tokens_details") or {}
        text = payload.get("output_text")
        if not text:
            output_parts = []
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"}: output_parts.append(content.get("text", ""))
            text = "\n".join(output_parts)
        if not text:
            raise ProviderUnavailable("Provider returned no text output.")
        return ModelResult(text=text, provider=self.provider, model=self.model, usage={"input_tokens": usage.get("input_tokens"), "cached_input_tokens": details.get("cached_tokens"), "output_tokens": usage.get("output_tokens"), "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"), "total_tokens": usage.get("total_tokens")}, latency_ms=round((time.perf_counter()-started)*1000, 2))


class PortkeyProvider(ModelProvider):
    provider = "PORTKEY"

    def __init__(self, key: str, base_url: str):
        self.key, self.base_url = key, base_url
        self.model = "gpt-6-luna"

    def status(self) -> dict:
        return {"available": False, "provider": self.provider, "model": self.model, "message": "PORTKEY_API_KEY is present, but no verified course gateway URL is configured; no endpoint is invented."}


def configured_provider() -> ModelProvider:
    if CONFIG.get("PORTKEY_API_KEY"):
        base = CONFIG.get("PORTKEY_BASE_URL")
        return PortkeyProvider(CONFIG["PORTKEY_API_KEY"], base) if base else PortkeyProvider(CONFIG["PORTKEY_API_KEY"], "")
    if CONFIG.get("OPENAI_API_KEY"):
        model = CONFIG.get("OPENAI_MODEL")
        if not model: return ModelProvider()
        return OpenAIResponsesProvider(CONFIG["OPENAI_API_KEY"], model)
    return ModelProvider()


def _tool_rows(name: str, fn: Callable[[], Any], role: str, mutating: bool = False) -> dict:
    return {"name": name, "description": fn.__doc__ or name, "role": role, "mutating": mutating,
            "input_schema": {"type": "object", "additionalProperties": False, "properties": {}}, "call": fn}


def tool_registry() -> dict[str, dict]:
    def calendar():
        """Read crop calendar stages and expected harvests."""
        from .main import calendar
        return calendar()
    def inventory():
        """Read physical inventory, reservations, and future forecast production."""
        from .main import inventory_summary
        return inventory_summary()
    def finance():
        """Read deterministic year-to-date financial summary."""
        from .main import _finance_period, _finance_totals
        return _finance_totals(*_finance_period("year"), "ACTUAL")
    def pricing():
        """Read approved product pricing and cost configurations."""
        from .main import pricing_products
        return pricing_products()
    def buyers():
        """Read active buyer records without exposing contact details to model context."""
        from .main import sales_buyers
        return [{k: row[k] for k in ("buyer_id", "business_name", "category", "customer_status") if k in row} for row in sales_buyers()]
    def matches():
        """Read deterministic tomato buyer matches for a bounded example quantity."""
        from .main import match_buyers
        result = match_buyers("product-tomato", 200, date.today())
        return {**result, "matches": [{k: m.get(k) for k in ("score", "explanation", "product_id", "quantity", "approved_price")} | {"buyer_id": m["buyer"]["buyer_id"], "business_name": m["buyer"]["business_name"]} for m in result["matches"]]}
    def dairy():
        """Read dairy production, milk lots, and animal identity records."""
        from .main import dairy_summary
        return dairy_summary()
    def dairy_dashboard_tool():
        """Read the deterministic dairy dashboard, herd, milk, financial, inventory, task, and outdoor weather-risk summaries."""
        from .main import dairy_dashboard_route
        return dairy_dashboard_route()
    def herd_summary():
        """Read mutually exclusive dairy herd categories and counts."""
        return dairy_dashboard_tool()["herd"]
    def milk_production():
        """Read recorded milk production for the current dashboard period."""
        from .main import dairy_production
        return dairy_production()
    def feed_cost_analysis():
        """Read feed inventory and recorded feed-cost context."""
        from .main import dairy_feed
        return dairy_feed()
    def dairy_inventory():
        """Read raw and finished dairy inventory through the shared inventory ledger."""
        return dairy_dashboard_tool()["inventory"]
    def dairy_weather_risks():
        """Read outdoor weather status, THI estimate, and dairy heat-risk signals."""
        from .main import dairy_weather
        return dairy_weather()
    def dairy_tasks():
        """Read open and completed dairy task records."""
        from .main import dairy_tasks as route
        return route()
    def dairy_profitability():
        """Read deterministic dairy cost, revenue, and margin calculations."""
        return dairy_dashboard_tool()["finance"]
    def animal_profile():
        """Read the first synthetic animal profile and its recorded history as a bounded example."""
        from .main import dairy_animal
        first = dairy_dashboard_tool()["animals"][0]
        return dairy_animal(first["animal_id"])
    def lot_traceability():
        """Read traceability for the first available dairy lot as a bounded example."""
        from .main import lot_traceability_route
        lots = dairy_dashboard_tool()["inventory"]["lots"]
        first = next((lot for lot in lots if lot.get("lot_type") == "DAIRY"), None)
        return lot_traceability_route(first["lot_id"]) if first else {"timeline": [], "data_status": "NO_DAIRY_LOT"}
    def expansion_scenario():
        """Return a read-only dairy expansion framing; it never changes records."""
        dashboard = dairy_dashboard_tool()
        return {"status": "HYPOTHETICAL_ONLY", "current_herd": dashboard["herd"], "current_monthly_liters": dashboard["production"]["monthly_liters"], "note": "No expansion assumption was supplied; deterministic baseline only."}
    def poultry_overview_tool():
        """Read the deterministic flock, egg, inventory, feed, finance, task, and weather overview."""
        from .main import poultry_overview_route
        return poultry_overview_route()
    def flock_details():
        """Read recorded laying flocks and facility capacity."""
        from .main import poultry_flocks
        return poultry_flocks()
    def egg_production():
        """Read recorded egg collection sessions for the current period."""
        from .main import poultry_collections
        return poultry_collections()
    def egg_inventory():
        """Read saleable and packaged egg lots from the shared inventory ledger."""
        from .main import poultry_inventory
        return poultry_inventory()
    def egg_cost_per_dozen():
        """Read deterministic poultry costs per saleable egg and dozen."""
        return poultry_overview_tool()["finance"]
    def poultry_feed_costs():
        """Read poultry feed stock and usage without prescribing a ration."""
        from .main import poultry_feed
        return poultry_feed()
    def poultry_weather():
        """Read shared New Haven weather and deterministic poultry management risks."""
        from .main import poultry_weather_route
        return poultry_weather_route()
    def egg_pricing():
        """Read approved egg prices and explicit demonstration assumptions."""
        from .main import pricing_products
        return [row for row in pricing_products() if row.get("product_id", "").startswith("product-eggs-")]
    def egg_buyers():
        """Read deterministic potential buyer matches for a bounded 20-dozen egg example."""
        from .main import match_buyers
        result = match_buyers("product-eggs-dozen", 20, date.today())
        return {**result, "matches": [{"buyer_id": item["buyer"]["buyer_id"], "business_name": item["buyer"]["business_name"], "score": item["score"], "explanation": item["explanation"]} for item in result["matches"]]}
    def egg_offer_preview():
        """Prepare a nonbinding egg offer preview; it never reserves stock or sends email."""
        inventory = egg_inventory(); price_rows = egg_pricing()
        price = next((row.get("current_approved_price") for row in price_rows if row.get("product_id") == "product-eggs-dozen"), None)
        return {"status": "DRAFT_PREVIEW_ONLY", "product_id": "product-eggs-dozen", "requested_quantity": 20, "available_packages": inventory.get("available_packages", 0), "approved_price_per_dozen": price, "approval_required": True, "email_sent": False, "note": "Owner confirmation is required before an offer/order mutation; no contact details are invented."}
    def egg_traceability():
        """Read traceability for the first recorded egg lot."""
        from .main import poultry_inventory, poultry_lot_traceability
        lots = poultry_inventory()["lots"]
        return poultry_lot_traceability(lots[0]["lot_id"]) if lots else {"timeline": [], "data_status": "NO_EGG_LOT"}
    def weather():
        """Read the saved-coordinate weather result with provider status."""
        from .main import weather
        return weather()
    def weather_risks():
        """Read deterministic crop and dairy weather risks."""
        from .main import weather_risks
        return weather_risks()
    return {x["name"]: x for x in [_tool_rows("get_farm_weather", weather, "Weather"), _tool_rows("evaluate_weather_risks", weather_risks, "Weather"), _tool_rows("get_crop_calendar", calendar, "Production"), _tool_rows("get_farm_inventory_summary", inventory, "Production"), _tool_rows("get_farm_financial_summary", finance, "Finance"), _tool_rows("get_product_pricing", pricing, "Pricing"), _tool_rows("search_buyers", buyers, "Sales"), _tool_rows("get_matching_buyers", matches, "Sales"), _tool_rows("get_dairy_production_summary", dairy, "Production"), _tool_rows("get_dairy_dashboard", dairy_dashboard_tool, "Production"), _tool_rows("get_herd_summary", herd_summary, "Production"), _tool_rows("get_animal_profile", animal_profile, "Production"), _tool_rows("get_milk_production", milk_production, "Production"), _tool_rows("get_feed_cost_analysis", feed_cost_analysis, "Finance"), _tool_rows("get_dairy_inventory", dairy_inventory, "Production"), _tool_rows("get_dairy_product_profitability", dairy_profitability, "Finance"), _tool_rows("get_dairy_weather_risks", dairy_weather_risks, "Weather"), _tool_rows("get_dairy_tasks", dairy_tasks, "Production"), _tool_rows("get_dairy_lot_traceability", lot_traceability, "Production"), _tool_rows("evaluate_dairy_expansion", expansion_scenario, "Production"), _tool_rows("get_poultry_overview", poultry_overview_tool, "Production"), _tool_rows("get_flock_details", flock_details, "Production"), _tool_rows("get_egg_production", egg_production, "Production"), _tool_rows("get_egg_inventory", egg_inventory, "Production"), _tool_rows("get_egg_cost_per_dozen", egg_cost_per_dozen, "Finance"), _tool_rows("get_poultry_feed_costs", poultry_feed_costs, "Finance"), _tool_rows("evaluate_poultry_weather_risks", poultry_weather, "Weather"), _tool_rows("get_egg_pricing", egg_pricing, "Pricing"), _tool_rows("get_egg_wholesale_buyers", egg_buyers, "Sales"), _tool_rows("draft_egg_wholesale_offer", egg_offer_preview, "Sales"), _tool_rows("get_egg_lot_traceability", egg_traceability, "Production")]}


def _json_from_text(text: str) -> dict:
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start: raise ValueError("Model did not return a JSON object")
    return json.loads(cleaned[start:end+1])


def _record_call(run_id: str, result: ModelResult, agent: str, call_type: str, started: str, status: str = "COMPLETED", error: str | None = None):
    with connect() as c:
        c.execute("""INSERT INTO agent_calls
            (call_id,run_id,agent_id,call_type,tool_name,started_at,completed_at,latency_ms,
             input_tokens,cached_input_tokens,output_tokens,reasoning_tokens,total_tokens,
             provider,model,status,error_message,input_summary,output_summary,retry_count,cost_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("call-"+uuid.uuid4().hex[:12], run_id, agent, call_type, None, started,
             datetime.now(timezone.utc).isoformat(), result.latency_ms,
             result.usage.get("input_tokens"), result.usage.get("cached_input_tokens"),
             result.usage.get("output_tokens"), result.usage.get("reasoning_tokens"),
             result.usage.get("total_tokens"), result.provider, result.model, status, error,
             "redacted", "redacted", 0, "UNAVAILABLE"))


def _record_blocked_provider_event(run_id: str, call_type: str, started: str, error: str) -> None:
    """Persist a safe trace entry when a provider stops a run before tools execute."""
    event_id = "event-" + uuid.uuid4().hex[:12]
    completed = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute(
            "INSERT INTO agent_tool_events VALUES (?,?,?,?,?,?,?,?,?,?)",
            (event_id, run_id, "FarmManager", f"model_provider:{call_type}", "{}",
             json.dumps({"status": "BLOCKED", "reason": "Model provider unavailable"}),
             "BLOCKED", started, completed, error),
        )


def run_agent(user_request: str, provider: ModelProvider | None = None) -> dict:
    provider = provider or configured_provider(); run_id="run-"+uuid.uuid4().hex[:12]; started=datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute("""INSERT INTO agent_runs
            (run_id,user_request,provider,model,status,started_at,completed_at,agents_json,
             final_response,warnings_json,approval_required)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, user_request, provider.provider, provider.model, "RUNNING", started,
             None, "[]", None, "[]", 0))
    tools=tool_registry(); events=[]; agents=[]
    model_calls = 0
    total_tokens = 0
    run_started = time.monotonic()
    active_call_type = "ROLE_SELECTION"
    call_recorded = False
    try:
        if len(user_request) > 4000:
            raise ValueError("Request exceeds the maximum context size")
        decision=provider.complete([{"role":"system","content":"You are FarmTwin Farm Manager. Select the minimum specialist roles needed. Return JSON only with a roles array containing Weather, Production, Finance, Pricing, or Sales, plus a reason string. Never invent data."},{"role":"user","content":user_request}],max_output_tokens=300)
        model_calls += 1
        total_tokens += decision.usage.get("total_tokens") or 0
        if total_tokens > MAX_TOTAL_TOKENS: raise RuntimeError("Token budget exceeded")
        _record_call(run_id,decision,"FarmManager","ROLE_SELECTION",started)
        call_recorded = True
        selected=_json_from_text(decision.text); allowed={"Weather","Production","Finance","Pricing","Sales"}; roles=[r for r in selected.get("roles",[]) if r in allowed]
        if not roles: raise ValueError("Model selected no valid specialist roles")
        for role in roles:
            if time.monotonic() - run_started > MAX_RUN_SECONDS: raise RuntimeError("Execution time budget exceeded")
            if len(events)>=MAX_TOOL_CALLS: raise RuntimeError("Tool-call budget exceeded")
            role_tools=[t for t in tools.values() if t["role"]==role]
            for tool in role_tools:
                event_id="event-"+uuid.uuid4().hex[:12]; t0=datetime.now(timezone.utc).isoformat()
                try: output=tool["call"](); event_status="COMPLETED"; error=None
                except Exception as exc: output={"error":str(exc)}; event_status="ERROR"; error=str(exc)
                events.append({"event_id":event_id,"agent_id":role,"tool_name":tool["name"],"arguments":{},"output":output,"status":event_status})
                with connect() as c: c.execute("INSERT INTO agent_tool_events VALUES (?,?,?,?,?,?,?,?,?,?)",(event_id,run_id,role,tool["name"],"{}",json.dumps(output,default=str)[:12000],event_status,t0,datetime.now(timezone.utc).isoformat(),error))
            agents.append(role)
        compact=json.dumps({"roles":roles,"tool_results":[{"agent":e["agent_id"],"tool":e["tool_name"],"output":e["output"]} for e in events]},default=str)[:30000]
        if model_calls >= MAX_MODEL_CALLS: raise RuntimeError("Model-call budget exceeded")
        active_call_type = "SYNTHESIS"
        call_recorded = False
        synthesis=provider.complete([{"role":"system","content":"Synthesize an evidence-backed farm-owner answer. Use only tool results. State source labels, assumptions, unavailable data, and approval needs. Do not invent numbers."},{"role":"user","content":f"Request: {user_request}\nEvidence: {compact}"}],max_output_tokens=MAX_OUTPUT_TOKENS)
        model_calls += 1
        total_tokens += synthesis.usage.get("total_tokens") or 0
        if total_tokens > MAX_TOTAL_TOKENS: raise RuntimeError("Token budget exceeded")
        _record_call(run_id,synthesis,"FarmManager","SYNTHESIS",started)
        call_recorded = True
        with connect() as c: c.execute("UPDATE agent_runs SET status='COMPLETED',completed_at=?,agents_json=?,final_response=?,warnings_json=? WHERE run_id=?",(datetime.now(timezone.utc).isoformat(),json.dumps(agents),synthesis.text,json.dumps([]),run_id))
        return get_run(run_id)
    except (ProviderUnavailable, ValueError, RuntimeError) as exc:
        if isinstance(exc, ProviderUnavailable):
            if not call_recorded:
                failed = ModelResult("", provider.provider, provider.model,
                                     {"input_tokens": None, "cached_input_tokens": None,
                                      "output_tokens": None, "reasoning_tokens": None,
                                      "total_tokens": None}, 0)
                _record_call(run_id, failed, "FarmManager", active_call_type, started, status="ERROR", error=str(exc))
            _record_blocked_provider_event(run_id, active_call_type, started, str(exc))
        with connect() as c: c.execute("UPDATE agent_runs SET status=?,completed_at=?,warnings_json=? WHERE run_id=?",("UNAVAILABLE" if isinstance(exc,ProviderUnavailable) else "ERROR",datetime.now(timezone.utc).isoformat(),json.dumps([str(exc)]),run_id))
        return get_run(run_id)


def get_run(run_id: str) -> dict:
    with connect() as c:
        run=c.execute("SELECT * FROM agent_runs WHERE run_id=?",(run_id,)).fetchone()
        if not run: return {"error":"Run not found"}
        calls=[dict(x) for x in c.execute("SELECT * FROM agent_calls WHERE run_id=? ORDER BY started_at",(run_id,)).fetchall()]
        events=[dict(x) for x in c.execute("SELECT event_id,agent_id,tool_name,status,started_at,completed_at,error_message FROM agent_tool_events WHERE run_id=? ORDER BY started_at",(run_id,)).fetchall()]
    result=dict(run); result["agents"]=json.loads(result.pop("agents_json")); result["warnings"]=json.loads(result.pop("warnings_json")); result["calls"]=calls; result["tool_events"]=events; result["real_model_run"]=result["status"]=="COMPLETED" and bool(calls); return result


def provider_status() -> dict:
    return configured_provider().status()
