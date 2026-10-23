# FarmTwin AI

Repository: <https://github.com/xw557206/Final-Project---FarmTwin-AI>

FarmTwin AI is a local-first virtual farm management foundation for the Yale SOM MGT 409 AI Agents project. It provides a seeded Connecticut demonstration farm, a relational SQLite database, FastAPI endpoints, a responsive React dashboard, an interactive database-driven SVG farm map, weather intelligence, deterministic financial management, and auditable seasonal pricing.

All seeded operational and financial records are clearly marked `SYNTHETIC`. Weather is labeled by provider/data status. Step 8 adds bounded, observable AI orchestration; deterministic farm services remain authoritative for all calculations and state changes.

## Requirements

- Python 3.11+ (tested with the available Python installation)
- Node.js 18+
- npm

## Install and initialize

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
python -m backend.db
```

The API also initializes and seeds `data/farmtwin.db` automatically on startup. Seed initialization is idempotent.

## Run

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

Open <http://localhost:5173>. API documentation is available at <http://localhost:8000/docs>.

## Slide deck

Open [slides.html](slides.html) directly in a browser, or serve the repository with a local static server. It is a 10-slide reveal.js presentation loaded from the reveal.js CDN; use the arrow keys to navigate and `F` for fullscreen. The deck uses original inline SVG/HTML illustrations and labels them as illustrations because no browser screenshots were captured in the evidence workspace.

## Project report

Open [report.html](report.html) directly in a browser or through the same local static server. It is a 12-page print-friendly US Letter HTML report covering motivation, differentiation, agents, tokenomics, safety, impact, limitations, and reproducibility. It labels unavailable live AI, cost, user-impact, and screenshot evidence instead of presenting estimates as measurements.

## Configuration

Copy `.env.example` to `.env` in the project root if configuration is needed. The backend checks the project root first and the parent directory second, with project-root values taking precedence. For Step 8, configure either `OPENAI_API_KEY` plus `OPENAI_MODEL`, or the course `PORTKEY_API_KEY` plus the exact verified `PORTKEY_BASE_URL` supplied by the course. No Portkey endpoint or model mapping is guessed. Keys remain server-side and are never returned to the browser. Without a verified provider, the advisor clearly reports `UNAVAILABLE` and does not show a scripted AI answer. `.env` and local database files are ignored by Git.

## Working features

- Overview dashboard with farm, acreage, crop-plot, dairy, harvest, synthetic financial, and activity metrics from SQLite.
- Interactive SVG farm map with crop plots and facilities.
- Virtual Farm plots with original database-linked pixel-art sprites for tomatoes, lettuce, spinach, carrots, potatoes, strawberries, sweet corn, and cucumbers; plot sprites change through projected growth stages using a read-only Farm Time Machine date.
- Plot detail/edit form with validation and persistence.
- Farm profile settings with persistence.
- FastAPI OpenAPI documentation.
- Seeded relational tables for farms, assets, crops, production plans, products, dairy summary, expenses, and activities.
- Backend tests for initialization, idempotent seeding, summary calculations, validation, and persistence.
- Live Open-Meteo current/hourly/seven-day weather for the default approximate New Haven coordinates (41.3083, -72.9279), with Fahrenheit/mph/inch normalization, 15-minute server cache, manual refresh, explicit LIVE_FORECAST/CACHED/UNAVAILABLE status, and official NWS active-alert enrichment.
- Windows socket-permission failures such as WinError 10013 are caught and translated into an actionable provider message; cached weather is retained when available instead of exposing a raw backend exception.
- Settings allow the owner to update farm latitude, longitude, timezone, and location; crop/dairy risk rules and the AI Weather tool consume the same normalized weather snapshot.
- Weather risk thresholds and persistent owner-controlled Farm Missions.
- Crop seasonality parameters, deterministic crop-stage calendar, editable agronomic demonstration assumptions, and dairy heat-monitoring signals.
- Weather Intelligence Center at `/api/weather/intelligence` and on the Weather page: America/New_York seasonal overview, every database crop, stable plot assignments, deterministic FAVORABLE/MONITOR/AT RISK/CRITICAL/INSUFFICIENT DATA classification, forecast-low frost and forecast-high heat checks, wind/rain monitoring, and source-labeled modeled soil temperature/moisture and ET₀ metrics.
- Finance page with transaction-backed KPI cards, monthly performance bars, expense mix, budget variance, dairy unit economics, expense entry, and CSV export.
- Decimal-safe deterministic calculations for production cost, unit cost, contribution margin, gross profit, operating profit, break-even, depreciation, NPV, IRR, ROI, and payback.
- Hypothetical capital investment evaluation that never changes actual farm records.
- Dynamic Pricing page with deterministic target-margin, cost-floor, seasonal/supply-adjusted market-reference, inventory/perishability, scenario, alert, and owner-approval workflows. Pricing examples are synthetic/demo data unless explicitly marked otherwise.
- Optional market-data adapter boundary prepared for USDA MyMarketNews; the local app does not require a USDA credential and does not claim USDA data when unavailable.
- Inventory Operations page with physical lots, on-hand/reserved/available quantities, future harvest projections, transaction-safe reservations, release and fulfillment, storage records, and movement history.
- Harvest-lot traceability from product and originating plot/facility through movement events and reservations.
- Dairy Operations page with six synthetic cow profiles, original cow icons, milk-production records, milk inventory, feed-expense context, and explicit `NOT_RECORDED` health-data labeling.
- Expanded Dairy Operations workspace with database-backed Overview, Interactive Barn, Herd & Profiles, Milking & Production, Feed Management, Milk Inventory, and Tasks & Weather tabs. It includes six idempotently seeded `SYNTHETIC` animals, 30 days of production history, herd classification, editable animal records, duplicate-session protection, milk collection and withholding controls, shared-ledger processing inputs/outputs, feed purchase/usage records, deterministic dairy finance and outdoor THI calculations, and read-only dairy advisor tools.
- Poultry & Eggs workspace with an in-map database-linked chicken coop and outdoor run, three synthetic flocks totaling 40 laying hens, idempotent collection history, deterministic laying-rate calculations, exact single/half-dozen/dozen/case packaging conversions, shared inventory lots and traceability, feed expenses, poultry finance, weather-risk checks, health holds, owner-controlled tasks, and read-only poultry advisor tools.
- Spoilage Rescue panel with deterministic age-based risk classes, predicted waste separated from recorded spoilage, gross sales value at risk, and owner-review-only recovery guidance.
- Wholesale Buyers page with eight synthetic buyer records, explainable deterministic matching, nonbinding offer creation, approved-price/inventory validation, pipeline opportunities, and deterministic email-draft preview.
- Order confirmation, transactional inventory reservation, cancellation/release, fulfillment, and duplicate-fulfillment protection. Fulfillment does not automatically create a duplicate finance transaction.
- AI Farm Advisor with a Farm Manager model call for bounded role selection and synthesis, allowlisted read-only farm tools, persistent sanitized execution traces, provider status, and token usage fields. A successful run is labeled `GENUINE MODEL RUN`; no-key mode never fabricates one.
- AI observability endpoints: `/api/ai/status`, `/api/ai/tools`, `/api/ai/runs`, `/api/ai/runs/{run_id}`, sanitized run export, and `/api/ai/tokenomics`.
- Step 9 evaluation artifacts under `docs/evidence/`, including an implementation audit, threat model, six-case benchmark catalog, safety-lab result, token ledger, and explicitly unmeasured impact/cost-optimization templates.
- Weather connectivity diagnostics and live-request evidence are preserved in `docs/evidence/weather_connectivity_diagnostics.md` and `docs/evidence/weather_live_request.md`; crop requirement values remain configurable demonstration assumptions unless a cited source is supplied.
- Dairy verification evidence is preserved in `docs/evidence/dairy_operations_verification.md`. The current persistent database is not reset by the dairy seed; its totals can include earlier synthetic records, while isolated tests use deterministic known-answer fixtures.

## Not implemented in the current phase

Direct email sending, authentication, autonomous external actions, and the AI Decision Simulator remain limited/deferred. Finance, dynamic pricing, inventory, dairy profiles, poultry operations, traceability, spoilage rescue, buyer CRM, matching, offer drafts, and basic order tracking remain deterministic tooling. Step 8 uses one genuine model-based manager decision and synthesis around deterministic specialist executors; it is not six independent autonomous loops. The course Portkey gateway is blocked until its exact verified URL/model configuration is supplied. OpenAI cost estimates remain unavailable unless official pricing is configured. All buyer emails remain draft/export-only. Open-Meteo and NWS require runtime network access; when unavailable, the app preserves an explicitly labeled cached snapshot or returns `UNAVAILABLE` rather than substituting fake live values. Crop weather thresholds and poultry weather thresholds are configurable Connecticut demonstration assumptions and are not crop/flock-health, sensor, disease, or yield predictions. Egg grades are `UNVERIFIED` unless an owner records a release; the app does not certify regulatory compliance.

## Step 9 evaluation status

The repository includes an implementation audit, application-specific threat model, isolated deterministic safety lab, six-scenario benchmark catalog, and evidence templates. Run `python -m backend.safety_lab` to reproduce the no-provider safety checks, and `python -m backend.benchmarks` to print the offline benchmark catalog. Use `python -m backend.benchmarks --live` only after explicitly configuring an authorized provider; it may incur API cost. Live model tokens, verified pricing, cost optimization, real-user impact, and screenshots are not claimed until actually collected.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
pytest backend\tests -q
cd frontend
npm run build
```

