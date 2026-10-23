"""Open-Meteo forecast adapter with official NWS alert enrichment."""

from datetime import datetime, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

class WeatherUnavailable(Exception):
    pass


def friendly_weather_error(exc: Exception) -> str:
    """Turn provider/socket failures into safe, actionable UI text."""
    text = str(exc)
    winerror = getattr(exc, "winerror", None)
    if winerror == 10013 or "WinError 10013" in text or "Errno 10013" in text:
        return "Windows or the current network environment blocked the outbound weather request (socket permission 10013). Allow the backend Python process to make HTTPS requests or use the cached weather snapshot."
    if winerror == 10048 or "WinError 10048" in text:
        return "The local backend port is already in use. Stop the older backend process or start FarmTwin on another local port."
    if isinstance(exc, TimeoutError) or "timed out" in text.lower():
        return "The weather provider did not respond before the timeout. Cached weather will be used when available."
    return text or "The weather provider request failed."

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
DEFAULT_TIMEZONE = "America/New_York"
REQUEST_TIMEOUT_SECONDS = 10
WMO_CONDITIONS = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",45:"Fog",48:"Depositing rime fog",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",56:"Freezing drizzle",57:"Heavy freezing drizzle",61:"Slight rain",63:"Rain",65:"Heavy rain",66:"Freezing rain",67:"Heavy freezing rain",71:"Slight snow",73:"Snow",75:"Heavy snow",77:"Snow grains",80:"Rain showers",81:"Rain showers",82:"Heavy rain showers",85:"Snow showers",86:"Heavy snow showers",95:"Thunderstorm",96:"Thunderstorm with hail",99:"Thunderstorm with hail"}

def _get_json(url: str, *, user_agent: str = "FarmTwinAI/1.0 educational weather client", timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise WeatherUnavailable(friendly_weather_error(exc)) from exc
    if not isinstance(payload, dict):
        raise WeatherUnavailable("Weather provider returned a non-object response")
    return payload

def _condition(code) -> str:
    try: return WMO_CONDITIONS.get(int(code), "Unknown weather condition")
    except (TypeError, ValueError): return "Unknown weather condition"

def _value(values: list, index: int):
    return values[index] if index < len(values) else None

def _alert_rows(payload: dict) -> list[dict]:
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        rows.append({"id":feature.get("id") or props.get("id"),"event":props.get("event"),"headline":props.get("headline"),"severity":props.get("severity"),"urgency":props.get("urgency"),"description":props.get("description"),"effective":props.get("effective"),"expires":props.get("expires"),"source":"National Weather Service","source_url":feature.get("id") or NWS_ALERTS_URL})
    return rows

def fetch_open_meteo(latitude: float, longitude: float, timezone_name: str = DEFAULT_TIMEZONE) -> dict:
    """Fetch and normalize current, hourly, and seven-day Open-Meteo data."""
    params = {"latitude":f"{float(latitude):.4f}","longitude":f"{float(longitude):.4f}","current":"temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m","hourly":"temperature_2m,precipitation_probability,precipitation,wind_speed_10m,relative_humidity_2m,weather_code,soil_temperature_6cm,soil_moisture_0_to_1cm","daily":"temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code,et0_fao_evapotranspiration,sunshine_duration,shortwave_radiation_sum","temperature_unit":"fahrenheit","wind_speed_unit":"mph","precipitation_unit":"inch","timezone":timezone_name or DEFAULT_TIMEZONE,"forecast_days":"7"}
    forecast_url = f"{OPEN_METEO_URL}?{urlencode(params)}"
    raw = _get_json(forecast_url)
    current_raw, hourly_raw, daily_raw = raw.get("current") or {}, raw.get("hourly") or {}, raw.get("daily") or {}
    if not current_raw.get("time") or not daily_raw.get("time"): raise WeatherUnavailable("Open-Meteo response omitted current or daily timestamps")
    code = current_raw.get("weather_code")
    current = {"time":current_raw.get("time"),"temperature_f":current_raw.get("temperature_2m"),"feels_like_f":current_raw.get("apparent_temperature"),"relative_humidity_pct":current_raw.get("relative_humidity_2m"),"precipitation_in":current_raw.get("precipitation"),"wind_speed_mph":current_raw.get("wind_speed_10m"),"weather_code":code,"condition":_condition(code),"data_status":"LIVE_OBSERVATION"}
    forecast = []
    for index, day in enumerate((daily_raw.get("time") or [])[:7]):
        code = _value(daily_raw.get("weather_code",[]), index)
        forecast.append({"name":day,"start":f"{day}T00:00:00","end":f"{day}T23:59:59","temperature_f":_value(daily_raw.get("temperature_2m_max",[]),index),"temperature_max_f":_value(daily_raw.get("temperature_2m_max",[]),index),"temperature_min_f":_value(daily_raw.get("temperature_2m_min",[]),index),"temperature_unit":"F","short_forecast":_condition(code),"precip_probability_pct":_value(daily_raw.get("precipitation_probability_max",[]),index),"rainfall_in":_value(daily_raw.get("precipitation_sum",[]),index),"weather_code":code,"data_status":"LIVE_FORECAST"})
    hourly = []
    for index, timestamp in enumerate((hourly_raw.get("time") or [])[:48]):
        code = _value(hourly_raw.get("weather_code",[]), index)
        hourly.append({"start":timestamp,"temperature_f":_value(hourly_raw.get("temperature_2m",[]),index),"temperature_unit":"F","precip_probability_pct":_value(hourly_raw.get("precipitation_probability",[]),index),"rainfall_in":_value(hourly_raw.get("precipitation",[]),index),"wind_speed_mph":_value(hourly_raw.get("wind_speed_10m",[]),index),"humidity_pct":_value(hourly_raw.get("relative_humidity_2m",[]),index),"soil_temperature_6cm_f":_value(hourly_raw.get("soil_temperature_6cm",[]),index),"soil_moisture_0_to_1cm":_value(hourly_raw.get("soil_moisture_0_to_1cm",[]),index),"weather_code":code,"short_forecast":_condition(code),"data_status":"LIVE_FORECAST"})
    agricultural_metrics = {"soil_temperature_6cm_f": hourly[0].get("soil_temperature_6cm_f") if hourly else None, "soil_moisture_0_to_1cm": hourly[0].get("soil_moisture_0_to_1cm") if hourly else None, "evapotranspiration_mm": _value(daily_raw.get("et0_fao_evapotranspiration",[]), 0), "sunshine_duration_seconds": _value(daily_raw.get("sunshine_duration",[]), 0), "shortwave_radiation_sum_mj_m2": _value(daily_raw.get("shortwave_radiation_sum",[]), 0), "source": "Open-Meteo weather model estimate; not an on-farm sensor observation"}
    for index, period in enumerate(forecast):
        period["agricultural_metrics"] = {"evapotranspiration_mm": _value(daily_raw.get("et0_fao_evapotranspiration",[]), index), "sunshine_duration_seconds": _value(daily_raw.get("sunshine_duration",[]), index), "shortwave_radiation_sum_mj_m2": _value(daily_raw.get("shortwave_radiation_sum",[]), index), "source": agricultural_metrics["source"]}
    alerts_url = f"{NWS_ALERTS_URL}?{urlencode({'point': f'{float(latitude):.4f},{float(longitude):.4f}'})}"
    alerts_error = None
    try: alerts = _alert_rows(_get_json(alerts_url, user_agent="FarmTwinAI/1.0 educational project contact: local-demo"))
    except WeatherUnavailable as exc: alerts, alerts_error = [], str(exc)
    retrieved = datetime.now(timezone.utc).isoformat()
    result = {"provider":"Open-Meteo + National Weather Service alerts","provider_code":"OPEN_METEO_NWS_ALERTS","data_status":"LIVE_FORECAST","retrieved_at":retrieved,"last_successful_refresh":retrieved,"forecast_updated_at":raw.get("generationtime_ms"),"timezone":raw.get("timezone") or timezone_name or DEFAULT_TIMEZONE,"location":{"latitude":float(latitude),"longitude":float(longitude)},"current":current,"observation":current,"forecast":forecast,"hourly":hourly,"alerts":alerts,"agricultural_metrics":agricultural_metrics,"source_urls":{"forecast":forecast_url,"alerts":alerts_url},"units":{"temperature":"fahrenheit","wind_speed":"mph","precipitation":"inch","soil_temperature":"fahrenheit","soil_moisture":"m³/m³","evapotranspiration":"millimeter"},"alerts_status":"UNAVAILABLE" if alerts_error else "LIVE"}
    if alerts_error: result["alerts_error"] = alerts_error
    return result

def unavailable_payload(reason: str, latitude: float | None = None, longitude: float | None = None) -> dict:
    return {"provider":"Open-Meteo + National Weather Service alerts","provider_code":"OPEN_METEO_NWS_ALERTS","data_status":"UNAVAILABLE","retrieved_at":datetime.now(timezone.utc).isoformat(),"reason":reason,"forecast":[],"hourly":[],"alerts":[],"observation":None,"location":{"latitude":latitude,"longitude":longitude},"timezone":DEFAULT_TIMEZONE,"source_urls":{},"units":{"temperature":"fahrenheit","wind_speed":"mph","precipitation":"inch"}}

fetch_nws = fetch_open_meteo
