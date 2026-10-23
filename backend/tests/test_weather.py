from datetime import date
import pytest
from fastapi.testclient import TestClient

from backend import db, weather
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "weather.db")
    monkeypatch.setattr(__import__("backend.main", fromlist=["seed_database"]), "seed_database", db.seed_database)


def sample_open_meteo():
    times = [f"2026-10-{day:02d}" for day in range(22, 29)]
    hours = [f"2026-10-22T{hour:02d}:00" for hour in range(48)]
    return {
        "timezone": "America/New_York", "generationtime_ms": 0.4,
        "current": {"time": hours[0], "temperature_2m": 61.2, "relative_humidity_2m": 72, "apparent_temperature": 60.1, "precipitation": 0, "weather_code": 2, "wind_speed_10m": 8.5},
        "hourly": {"time": hours, "temperature_2m": [61] * 48, "precipitation_probability": [20] * 48, "precipitation": [0] * 48, "wind_speed_10m": [8] * 48, "relative_humidity_2m": [70] * 48, "weather_code": [2] * 48, "soil_temperature_6cm": [55] * 48, "soil_moisture_0_to_1cm": [.22] * 48},
        "daily": {"time": times, "temperature_2m_max": [70] * 7, "temperature_2m_min": [48] * 7, "precipitation_sum": [0.1] * 7, "precipitation_probability_max": [20] * 7, "weather_code": [2] * 7, "et0_fao_evapotranspiration": [3.1] * 7, "sunshine_duration": [18000] * 7, "shortwave_radiation_sum": [12.5] * 7},
    }


def test_open_meteo_normalization_and_units(monkeypatch):
    def fake(url, **kwargs):
        if "weather.gov" in url:
            return {"features": []}
        return sample_open_meteo()
    monkeypatch.setattr(weather, "_get_json", fake)
    result = weather.fetch_open_meteo(41.3083, -72.9279)
    assert result["data_status"] == "LIVE_FORECAST"
    assert result["location"] == {"latitude": 41.3083, "longitude": -72.9279}
    assert result["units"]["temperature"] == "fahrenheit"
    assert result["units"]["wind_speed"] == "mph"
    assert result["units"]["precipitation"] == "inch"
    assert result["current"]["temperature_f"] == 61.2
    assert result["agricultural_metrics"]["soil_temperature_6cm_f"] == 55
    assert result["agricultural_metrics"]["soil_moisture_0_to_1cm"] == pytest.approx(.22)
    assert result["agricultural_metrics"]["evapotranspiration_mm"] == pytest.approx(3.1)
    assert len(result["forecast"]) == 7
    assert result["alerts"] == []


def test_nws_alert_normalization_and_no_alerts(monkeypatch):
    payload = sample_open_meteo()
    alert = {"features": [{"id": "https://api.weather.gov/alerts/1", "properties": {"event": "Test Alert", "headline": "Test headline", "severity": "Moderate", "effective": "2026-10-22T10:00:00Z", "expires": "2026-10-22T12:00:00Z", "description": "Test description"}}]}
    monkeypatch.setattr(weather, "_get_json", lambda url, **kwargs: alert if "weather.gov" in url else payload)
    result = weather.fetch_open_meteo(41.3083, -72.9279)
    assert result["alerts"][0]["event"] == "Test Alert"
    assert result["alerts"][0]["source"] == "National Weather Service"


def test_weather_failure_is_unavailable(monkeypatch):
    def fail(*args, **kwargs):
        raise weather.WeatherUnavailable("timeout")
    monkeypatch.setattr(weather, "_get_json", fail)
    with pytest.raises(weather.WeatherUnavailable):
        weather.fetch_open_meteo(41.3083, -72.9279)


def test_windows_socket_permission_error_is_actionable(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError(10013, "An attempt was made to access a socket in a way forbidden by its access permissions")
    monkeypatch.setattr(weather, "urlopen", fail)
    with pytest.raises(weather.WeatherUnavailable) as caught:
        weather._get_json("https://api.open-meteo.com")
    assert "socket permission 10013" in str(caught.value)
    assert "Allow the backend Python process" in str(caught.value)


def test_farm_location_update_persists_coordinates():
    with TestClient(app) as client:
        farm = client.get("/api/farm").json()
        assert farm["latitude"] == pytest.approx(41.3083)
        assert farm["longitude"] == pytest.approx(-72.9279)
        response = client.put("/api/farm", json={"name": farm["name"], "location": "New Haven, CT", "latitude": 41.31, "longitude": -72.92, "timezone": "America/New_York"})
        assert response.status_code == 200
        assert client.get("/api/farm").json()["latitude"] == pytest.approx(41.31)


def test_crop_weather_intelligence_returns_all_database_crops(monkeypatch):
    monkeypatch.setattr(weather, "_get_json", lambda url, **kwargs: {"features": []} if "weather.gov" in url else sample_open_meteo())
    with TestClient(app) as client:
        response = client.get("/api/weather/intelligence?refresh=true")
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_status"] == "LIVE_FORECAST"
        assert len(payload["crops"]) == 8
        assert {crop["crop_id"] for crop in payload["crops"]} == {"crop-tomatoes", "crop-lettuce", "crop-spinach", "crop-carrots", "crop-potatoes", "crop-strawberries", "crop-corn", "crop-cucumbers"}
        assert payload["seasonal_overview"]["timezone"] == "America/New_York"
        assert all(crop["requirements_source"] for crop in payload["crops"])


def test_crop_weather_intelligence_classifies_frost_from_forecast_low(monkeypatch):
    payload = sample_open_meteo()
    payload["daily"]["temperature_2m_min"] = [25] * 7
    monkeypatch.setattr(weather, "_get_json", lambda url, **kwargs: {"features": []} if "weather.gov" in url else payload)
    with TestClient(app) as client:
        crops = client.get("/api/weather/intelligence?refresh=true").json()["crops"]
        tomato = next(crop for crop in crops if crop["crop_id"] == "crop-tomatoes")
        assert tomato["status"] in {"At Risk", "Critical"}
        assert tomato["major_risk"] == "Frost risk"


def test_missing_agricultural_variables_are_explicitly_unavailable(monkeypatch):
    payload = sample_open_meteo()
    payload["hourly"].pop("soil_temperature_6cm")
    payload["hourly"].pop("soil_moisture_0_to_1cm")
    payload["daily"].pop("et0_fao_evapotranspiration")
    monkeypatch.setattr(weather, "_get_json", lambda url, **kwargs: {"features": []} if "weather.gov" in url else payload)
    result = weather.fetch_open_meteo(41.3083, -72.9279)
    assert result["agricultural_metrics"]["soil_temperature_6cm_f"] is None
    assert result["agricultural_metrics"]["soil_moisture_0_to_1cm"] is None
    assert result["agricultural_metrics"]["evapotranspiration_mm"] is None
