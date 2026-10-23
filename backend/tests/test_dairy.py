from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend import db, dairy, main
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "dairy.db")
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_dairy_dashboard_and_herd_categories_are_database_backed():
    with TestClient(app) as client:
        response = client.get("/api/dairy/summary")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["animals"]) == 6
        assert payload["dashboard"]["herd"]["total"] == 6
        assert payload["dashboard"]["herd"]["active_milking"] == 5
        assert payload["dashboard"]["herd"]["dry_cows"] == 1
        assert len(payload["dashboard"]["production"]["daily"]) == 30
        assert payload["dashboard"]["production"]["today_liters"] == pytest.approx(185, abs=.1)


def test_animal_edit_and_milking_duplicate_protection():
    with TestClient(app) as client:
        update = client.put("/api/dairy/animals/animal-daisy", json={"tag": "GV-001", "name": "Daisy II", "breed": "Holstein", "birth_date": "2021-03-12", "sex": "FEMALE", "herd_category": "LACTATING_COW", "production_status": "MILKING", "facility_id": "facility-barn", "notes": "Owner-entered note"})
        assert update.status_code == 200
        assert client.get("/api/dairy/animals/animal-daisy").json()["animal"]["name"] == "Daisy II"
        payload = {"production_date": date.today().isoformat(), "quantity": 20, "unit": "liter", "session_type": "EVENING", "saleable_quantity": 20, "withheld_quantity": 0, "operator": "Owner"}
        assert client.post("/api/dairy/animals/animal-daisy/production", json=payload).status_code == 200
        assert client.post("/api/dairy/animals/animal-daisy/production", json=payload).status_code == 409


def test_collection_processing_and_inventory_reconcile():
    with TestClient(app) as client:
        collection = client.post("/api/dairy/milk-collections", json={"collection_date": date.today().isoformat(), "source_scope": "TEST-HERD", "quantity_collected": 100, "approved_quantity": 90, "withheld_quantity": 10, "withholding_reason": "Quality hold for demonstration", "storage_id": "storage-barn", "quality_status": "RELEASED", "sell_by_date": date.today().isoformat()}).json()
        assert collection["collection"]["approved_quantity"] == pytest.approx(90)
        lot_id = collection["lot"]["lot_id"]
        assert collection["lot"]["available"] == pytest.approx(90)
        processed = client.post("/api/dairy/processing", json={"input_lot_id": lot_id, "product_id": "product-cream", "input_quantity": 40, "processed_at": date.today().isoformat()})
        assert processed.status_code == 200
        result = processed.json()
        assert result["input_lot"]["available"] == pytest.approx(50)
        assert result["output_lot"]["quantity_produced"] == pytest.approx(10)
        assert result["output_lot"]["available"] == pytest.approx(10)
        assert result["batch"]["source_type"] == "OWNER_ENTERED"


def test_feed_usage_and_task_completion():
    with TestClient(app) as client:
        feed = client.get("/api/dairy/feed").json()["feeds"][0]
        before = feed["quantity"]
        usage = client.post(f"/api/dairy/feed/{feed['feed_id']}/usage", json={"usage_date": date.today().isoformat(), "quantity": 10, "unit": feed["unit"], "herd_group": "LACTATING_COWS"})
        assert usage.status_code == 200
        after = next(item for item in client.get("/api/dairy/feed").json()["feeds"] if item["feed_id"] == feed["feed_id"])
        assert after["quantity"] == pytest.approx(before - 10)
        task = client.get("/api/dairy/tasks").json()["tasks"][0]
        completed = client.put(f"/api/dairy/tasks/{task['task_id']}", json={"status": "COMPLETED", "completion_notes": "Recorded in test."})
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"


def test_thi_formula_and_missing_weather_are_explicit():
    value = dairy.calculate_thi(80, 50)
    assert value == pytest.approx(74.2, abs=.2)
    assert dairy.classify_thi(value) == "MODERATE_RISK"
    assert dairy.calculate_thi(None, 50) is None
