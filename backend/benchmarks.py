"""Small Step 8 benchmark catalog.

The default command is offline and only prints the reproducible cases. Pass
``--live`` explicitly after configuring an authorized provider to incur model
calls; results are not fabricated when no provider is available.
"""

import argparse
import json

from .agents import configured_provider, run_agent


CASES = [
    {"id": "weather-risk", "request": "What weather risks affect an active tomato crop?", "expected_tools": ["get_farm_weather", "evaluate_weather_risks"]},
    {"id": "profitability", "request": "What is the farm's recorded financial summary?", "expected_tools": ["get_farm_financial_summary"]},
    {"id": "seasonal-price", "request": "What is the current tomato pricing evidence?", "expected_tools": ["get_product_pricing"]},
    {"id": "inventory-buyers", "request": "Which buyers could be considered for available tomatoes?", "expected_tools": ["get_farm_inventory_summary", "get_matching_buyers"]},
    {"id": "crop-allocation", "request": "What happens if I replace two acres of corn with strawberries?", "expected_tools": ["get_crop_calendar", "get_farm_financial_summary"], "note": "Decision Simulator is not yet implemented; this case must report that limitation."},
    {"id": "tomato-workflow", "request": "We expect a tomato harvest next week. Check weather, production risk, unit cost, seasonal price, grocery buyers, and prepare an email for approval.", "expected_tools": ["get_farm_weather", "evaluate_weather_risks", "get_crop_calendar", "get_farm_financial_summary", "get_product_pricing", "get_matching_buyers"]},
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run real provider calls; may incur cost")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"mode": "OFFLINE_CATALOG", "cases": CASES}, indent=2))
        return
    provider = configured_provider()
    if not provider.status().get("available"):
        print(json.dumps({"mode": "LIVE", "status": "UNAVAILABLE", "message": provider.status()["message"]}, indent=2))
        return
    results = []
    for case in CASES:
        run = run_agent(case["request"], provider)
        called = [event["tool_name"] for event in run.get("tool_events", [])]
        results.append({"id": case["id"], "run_id": run.get("run_id"), "status": run.get("status"), "expected_tools": case["expected_tools"], "called_tools": called, "calls": len(run.get("calls", []))})
    print(json.dumps({"mode": "LIVE", "results": results}, indent=2))


if __name__ == "__main__":
    main()
