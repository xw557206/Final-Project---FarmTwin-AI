import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.inventory import available_quantity, spoilage_assessment
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "inventory.db")
    import backend.main as main
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_inventory_seed_reconciles_and_forecast_is_separate():
    with TestClient(app) as client:
        summary = client.get("/api/inventory/summary").json()
        tomato = next(x for x in summary["products"] if x["product_id"] == "product-tomato")
        assert tomato["on_hand"] == 800
        assert tomato["reserved"] == 150
        assert tomato["available"] == 650
        assert summary["future_forecast_production"]


def test_reservation_release_and_fulfillment_safety():
    with TestClient(app) as client:
        over = client.post("/api/inventory/lots/lot-tomato-2026-01/reserve?unit=lb", json={"quantity":700,"buyer_reference":"x","created_by":"Owner","reason":"test"})
        assert over.status_code == 422
        released = client.post("/api/inventory/reservations/reservation-tomato-demo/release").json()
        assert released["available"] == 800
        reserved = client.post("/api/inventory/lots/lot-tomato-2026-01/reserve?unit=lb", json={"quantity":200,"buyer_reference":"buyer-1","created_by":"Owner","reason":"test"}).json()
        reservation_id = reserved["reservations"][0]["reservation_id"]
        fulfilled = client.post(f"/api/inventory/reservations/{reservation_id}/fulfill?unit=lb", json={"quantity":200,"created_by":"Owner","reason":"sale"}).json()
        assert fulfilled["on_hand"] == 600
        assert fulfilled["available"] == 600


def test_traceability_spoilage_and_dairy_profile():
    with TestClient(app) as client:
        trace = client.get("/api/inventory/lots/lot-tomato-2026-01/traceability")
        assert trace.status_code == 200
        assert trace.json()["origin"]["origin_name"] == "Tomato Field"
        spoilage = client.get("/api/inventory/spoilage").json()
        assert any(x["lot_id"] == "lot-spinach-2026-01" and x["risk"] == "EXPIRED" for x in spoilage["assessments"])
        dairy = client.get("/api/dairy/summary").json()
        assert len(dairy["animals"]) == 6
        animal = client.get("/api/dairy/animals/animal-daisy").json()
        assert animal["health_data"] == "NOT_RECORDED"


def test_pure_inventory_rules():
    assert available_quantity(100, 30) == 70
    with pytest.raises(ValueError): available_quantity(10, 11)
    result = spoilage_assessment(quantity_on_hand=100, reserved_quantity=20, sell_by="2020-01-01", as_of=__import__('datetime').date(2020,1,2), shelf_life_days=7, approved_price=2)
    assert result["risk"] == "EXPIRED"
    assert result["gross_sales_value_at_risk"] == 160
