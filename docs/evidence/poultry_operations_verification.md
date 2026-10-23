# Poultry Operations Verification

Collected: 2026-10-23 (America/New_York)

This evidence describes only runs performed in the local workspace. Seeded poultry records are synthetic. Owner-entered workflows in tests use isolated temporary SQLite databases. No production reset or live buyer contact was performed.

## Backend regression

Command:

```powershell
python -m pytest backend\tests -q
```

Result: **41 passed**, 275 deprecation warnings, 16.01 seconds. The suite includes collection validation, laying-rate calculations, exact packaging conversion, shared inventory reconciliation, duplicate packaging protection, flock-capacity protection, product holds, unavailable weather, dairy/crop/inventory/finance/pricing/sales regression, and AI registry tests.

Command:

```powershell
python -m compileall -q backend
```

Result: passed with no compiler errors.

## Frontend build

Command:

```powershell
cd frontend
npm.cmd run build
```

Result: passed. Vite transformed 1,945 modules and produced `frontend/dist`. Vite emitted a configuration deprecation warning only. This is a build check, not a browser inspection.

## Local API smoke check

The backend was started with:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8131
```

Read-only requests to `/api/poultry/overview`, `/api/poultry/flocks`, `/api/poultry/inventory`, and `/api/ai/tools` returned:

| Check | Observed result |
|---|---|
| Poultry data status | `SYNTHETIC` |
| Recorded laying hens | `40` |
| Flocks | `3` |
| Eggs collected today | `33` |
| Available loose eggs | `30.0` |
| Poultry/egg tool count matched by name | `10` |

The tool-count query is name-filtered and does not claim that every poultry-capable agent tool has a poultry-specific name.

## Safety and scope notes

- Collection records cannot exceed the flock's recorded hens and reject quantities cannot exceed collection quantity.
- The shared inventory ledger prevents negative availability and exact packaging conversions are tested.
- Held egg batches cannot be packaged or offered; owner release is explicit and does not certify regulatory compliance.
- Offer drafting is preview-only; no email transport was invoked.
- No real model call, buyer contact, browser walkthrough, screenshot, or regulatory inspection was performed for this verification.
- `CASE = 180 eggs` is a project demonstration assumption, not a claim about a jurisdiction's packaging standard.
