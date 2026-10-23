# Live weather integration evidence

Collected: 2026-10-23T03:34:36Z (UTC). This was an actual external request, not a mock.

- Backend endpoint: `GET /api/weather?refresh=true`
- Open-Meteo request coordinates: latitude `41.3083`, longitude `-72.9279`
- Normalized response status: `LIVE_FORECAST`
- Provider: `Open-Meteo + National Weather Service alerts`
- Forecast length: 7 days
- Active NWS alerts returned: 0
- Units: Fahrenheit, mph, inches
- Refresh timestamp: `2026-10-23T03:34:36.355816+00:00`

A subsequent request without `refresh=true` returned `CACHED` with an observed cache age of approximately 5.8 seconds. No weather values were hardcoded. The request used the approximate New Haven city-center demonstration coordinates and stored the normalized snapshot locally.

The external request required the execution environment's network permission. If the network is unavailable during a future run, the application preserves the last successful snapshot as `CACHED` or reports `UNAVAILABLE`.
