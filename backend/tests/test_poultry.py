from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend import db, poultry, main
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "poultry.db")
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_poultry_overview_is_flock_backed_and_plausible():
    with TestClient(app) as client:
        result = client.get("/api/poultry/overview")
        assert result.status_code == 200
        payload = result.json()
        assert payload["flock"]["total_hens"] == 40
        assert payload["flock"]["flock_count"] == 3
        assert payload["production"]["today_eggs"] <= 40
        assert payload["production"]["laying_rate"] <= 1
        assert payload["inventory"]["available_eggs"] == pytest.approx(30)
        assert payload["data_status"] == "SYNTHETIC"


def test_collection_packaging_and_exact_inventory_conversion():
    with TestClient(app) as client:
        collection = client.post("/api/poultry/collections", json={
            "collection_date": date.today().isoformat(), "collection_time": "PM", "flock_id": "flock-brown",
            "eggs_collected": 18, "broken_eggs": 1, "dirty_rejected": 1, "worker": "Owner"
        })
        assert collection.status_code == 200
        body = collection.json()
        assert body["collection"]["accepted_for_grading"] == 16
        batch_id = body["batch"]["batch_id"]
        packaged = client.post("/api/poultry/packaging", json={
            "batch_id": batch_id, "package_type": "DOZEN", "package_count": 1,
            "packaging_date": date.today().isoformat(), "quality_status": "UNVERIFIED"
        })
        assert packaged.status_code == 200
        result = packaged.json()
        assert result["conversion"] == {"input_eggs": 12, "eggs_per_package": 12, "package_count": 1}
        assert result["source_lot"]["available"] == pytest.approx(4)
        assert result["output_lot"]["available"] == pytest.approx(1)
        duplicate = client.post("/api/poultry/packaging", json={
            "batch_id": batch_id, "package_type": "DOZEN", "package_count": 1,
            "packaging_date": date.today().isoformat(), "quality_status": "UNVERIFIED"
        })
        assert duplicate.status_code == 409


def test_poultry_rejects_capacity_and_product_hold_blocks_packaging():
    with TestClient(app) as client:
        too_many = client.post("/api/poultry/flocks", json={
            "name": "Over-capacity fixture", "breed": "Demo", "hens_count": 41,
            "facility_id": "facility-coop", "expected_laying_rate": 0.8
        })
        assert too_many.status_code == 422
        collection = client.post("/api/poultry/collections", json={
            "collection_date": date.today().isoformat(), "collection_time": "PM", "flock_id": "flock-white",
            "eggs_collected": 10, "broken_eggs": 0, "dirty_rejected": 0, "worker": "Owner"
        }).json()
        batch_id = collection["batch"]["batch_id"]
        held = client.post("/api/poultry/health?flock_id=flock-white", json={
            "event_date": date.today().isoformat(), "event_type": "BIOSECURITY_OBSERVATION",
            "observation": "Synthetic hold fixture; veterinarian review required.", "product_hold": True,
            "veterinary_review_required": True, "recorded_by": "Owner"
        })
        assert held.status_code == 200
        packaging = client.post("/api/poultry/packaging", json={
            "batch_id": batch_id, "package_type": "SINGLE", "package_count": 1,
            "packaging_date": date.today().isoformat(), "quality_status": "UNVERIFIED"
        })
        assert packaging.status_code == 409


def test_poultry_formula_and_weather_unknown_are_explicit():
    assert poultry.laying_rate(32, 40) == pytest.approx(0.8)
    assert poultry.package_spec("DOZEN")["eggs_per_package"] == 12
    assert poultry.weather_risks({"data_status": "UNAVAILABLE"})[0]["status"] == "INSUFFICIENT_DATA"
