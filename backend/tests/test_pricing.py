import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.main import app
from backend.pricing import adjusted_market_reference, gross_margin, normalize_market_price, recommend_price, simulate_price, target_margin_price


def test_known_pricing_formulas():
    assert float(target_margin_price(2.0, .25)) == pytest.approx(2.67)
    assert float(gross_margin(4.0, 2.0)) == pytest.approx(.5)
    assert float(adjusted_market_reference(4.0, 1.1, .9)) == pytest.approx(3.96)
    assert normalize_market_price(24, "dozen", "unit", 1) == 2
    with pytest.raises(ValueError): normalize_market_price(10, "bushel", "liter")


def test_conflict_and_scenario_are_explicit():
    result = recommend_price(unit_cost=2, target_margin=.5, market_price=2.2, seasonality_factor=1, supply_factor=1, minimum_price=2, objective="margin_preservation")
    assert result["market_indicated_price"] == 2.2
    assert result["target_margin_price"] == 4
    assert result["conflict_warning"]
    scenario = simulate_price(price=3, unit_cost=2, expected_volume=100, sales_volume=80, estimated_spoilage=.2)
    assert scenario["classification"] == "HYPOTHETICAL_SCENARIO"
    assert scenario["gross_profit"] == 80


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "pricing.db")
    import backend.main as main
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_pricing_approval_creates_history_without_mutating_finance():
    with TestClient(app) as client:
        product = client.get("/api/pricing/product/product-tomato").json()
        before = client.get("/api/finance/summary").json()["revenue"]
        payload = {"product_id":"product-tomato","target_margin":.3,"market_reference":3.1,"seasonality_factor":1.08,"supply_factor":1,"selling_price":3.25,"expected_volume":1000,"sales_volume":900,"estimated_spoilage":.1,"objective":"margin_preservation","inventory_age_days":1,"weather_supply_factor":1}
        rec = client.post("/api/pricing/recommend/product-tomato", json=payload).json()
        approved = client.post("/api/pricing/approve/product-tomato?recommendation_id=" + rec["recommendation_id"], json={"price":3.4,"effective_start":"2026-10-23","approved_by":"Owner","reason":"Test approval"})
        assert approved.status_code == 200
        assert client.get("/api/pricing/history/product-tomato").json()["changes"]
        assert client.get("/api/finance/summary").json()["revenue"] == before
        assert client.post("/api/pricing/approve/product-tomato", json={"price":1,"effective_start":"2026-10-23","approved_by":"Owner","reason":"Too low"}).status_code == 422
