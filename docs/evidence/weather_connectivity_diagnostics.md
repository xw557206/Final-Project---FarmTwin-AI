# Weather connectivity diagnostics and crop-intelligence evidence

Collected during the weather-intelligence verification run on 2026-10-23 (UTC). Farm data is the seeded synthetic Green Valley Farm record; weather observations/forecasts below are external provider responses, not sensor readings.

## Diagnosis

The original `WinError 10013` came from the restricted execution environment refusing an outbound socket. It was not caused by the Open-Meteo URL, New Haven coordinates, response parsing, or a local FastAPI bind. A previous stale backend process also continued serving the pre-route application on port 8010; a fresh process was used for final verification. No firewall, antivirus, SSL verification, or system security setting was disabled.

Controlled checks:

| Check | Observed result |
|---|---|
| DNS `api.open-meteo.com` | Resolved to `188.40.99.226` during the diagnostic; provider uses normal DNS/CDN infrastructure. |
| Python HTTPS request | Succeeded; response timezone `America/New_York`, current timestamp present, temperature field present. |
| PowerShell request | Succeeded; timezone `America/New_York`, timestamp `2026-10-22T23:45`. |
| `curl.exe` request | Succeeded with the same timezone and timestamp as PowerShell. |
| Proxy variables | No configured `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, or `NO_PROXY` values were reported; credentials were not printed. |
| Fresh FastAPI request | Succeeded on `127.0.0.1:8123`; live provider path returned HTTP 200. |
| NWS request | Returned zero active alerts in the final live verification; NWS failures are independently labeled unavailable. |

## Final live verification

`GET /api/weather/intelligence?refresh=true` on the fresh server returned:

- `data_status`: `LIVE_FORECAST`
- provider: `Open-Meteo + National Weather Service alerts`
- location: `41.3083, -72.9279`
- timezone: `America/New_York`
- crop records: `8`
- calendar season: `Autumn`
- modeled soil temperature at 6 cm: `52.4°F`
- modeled ET₀: `0.132 mm`

The values above are recorded from that API response and are not hardcoded into the UI. A subsequent `/api/weather` and `/api/weather/intelligence` request returned `CACHED`, and both responses contained the same weather snapshot ID. This verifies that the dashboard and crop-intelligence route read one shared snapshot.

## Implementation boundaries

- Open-Meteo provides current, hourly, and seven-day model forecast fields in Fahrenheit, mph, and inches.
- NWS provides official active-alert enrichment; an empty result is displayed as “No active NWS alerts reported.”
- Server cache lifetime is 15 minutes. Manual refresh uses `?refresh=true`; on provider failure the last valid snapshot is retained as `CACHED`, otherwise the response is `UNAVAILABLE`.
- `OSError`/`PermissionError` socket failures are caught at the HTTP adapter boundary. WinError 10013 is presented as a network-policy guidance message rather than a raw exception; no security control is disabled.
- Crop frost and heat checks use configured forecast thresholds; rainfall and wind checks are deterministic monitoring rules. No yield loss, disease, or farm-sensor claim is made.
- Crop requirements currently come from editable database values labeled `Northeast U.S. configurable demonstration assumption; verify locally before operational use.` Preferred humidity and soil-temperature requirements are returned as unavailable because they are not sourced in the current database.
- Weather-triggered missions use deterministic event keys and existing SQLite uniqueness constraints, so repeated reads do not create duplicate active missions.

## Reproduction

```powershell
python -m compileall -q backend
python -m pytest backend\tests -q
cd frontend
npm.cmd run build
```

For a live local check, start the backend with `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8123` and request `/api/weather?refresh=true` and `/api/weather/intelligence?refresh=true`. Network access and provider availability are runtime dependencies; do not interpret mocked tests as proof of a live request.
