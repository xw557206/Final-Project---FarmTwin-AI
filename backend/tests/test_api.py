import pytest
from fastapi.testclient import TestClient
from backend import db
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "test.db")
    import backend.main as main
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_seed_and_dashboard():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        summary = client.get("/api/summaries").json()
        assert summary["active_crop_plots"] == 8
        assert summary["planted_acres"] == pytest.approx(11.0)
        assert summary["data_status"] == "SYNTHETIC"


def test_plot_edit_persists_and_invalid_dates_rejected():
    with TestClient(app) as client:
        plot = client.get("/api/plots/plot-tomato").json()
        payload = {"name": plot["name"], "acreage": 2.0, "crop": "Tomatoes", "planting_date": "2026-04-01", "expected_harvest_date": "2026-09-01", "expected_yield": 2500, "actual_yield": None, "status": "GROWING", "estimated_cost": 4900, "expected_revenue": 9000}
        assert client.put("/api/plots/plot-tomato", json=payload).status_code == 200
        assert client.get("/api/plots/plot-tomato").json()["expected_yield"] == 2500
        payload["expected_harvest_date"] = "2026-03-01"
        assert client.put("/api/plots/plot-tomato", json=payload).status_code == 422


def test_seed_is_idempotent():
    db.seed_database(); db.seed_database()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM farms").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 14


def test_crop_calendar_and_parameters_are_available_without_weather():
    with TestClient(app) as client:
        calendar = client.get("/api/calendar?as_of_date=2026-06-15")
        assert calendar.status_code == 200
        assert len(calendar.json()["items"]) == 8
        assert {item["stage"] for item in calendar.json()["items"]}
        crops = client.get("/api/crops").json()
        tomatoes = next(item for item in crops if item["name"] == "Tomatoes")
        assert tomatoes["maturity_days"] == 80
        updated = client.put(f"/api/crops/{tomatoes['crop_id']}", json={"maturity_days": 81})
        assert updated.status_code == 200
        assert updated.json()["source_type"] == "OWNER_ENTERED"


def test_weather_unavailable_is_explicit_and_safe(monkeypatch):
    from backend import main
    from backend.weather import WeatherUnavailable
    monkeypatch.setattr(main, "fetch_nws", lambda *_: (_ for _ in ()).throw(WeatherUnavailable("test provider failure")))
    with TestClient(app) as client:
        result = client.get("/api/weather")
        assert result.status_code == 200
        assert result.json()["data_status"] == "UNAVAILABLE"
        assert result.json()["forecast"] == []

