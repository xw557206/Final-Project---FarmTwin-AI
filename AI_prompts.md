# FarmTwin AI — Prompt and Scope Log

This file is the chronological record of user-requested project scope and constraints. It should be updated at the beginning or end of each future FarmTwin AI step. It records the prompt intent and decisions, not fabricated implementation results.

## Entry 1 — Step 1: Project architecture and planning

**Request:** Plan FarmTwin AI as a virtual farm management platform for the Yale SOM MGT 409 AI Agents final project, with an October 26, 2026 deadline.

**Product vision:** Combine a digital farm twin, agricultural operations software, deterministic financial management, seasonal pricing, inventory, wholesale buyer relationships, weather intelligence, and AI decision support for small and midsized farms.

**Required modules:**

- Interactive virtual farm layout with configurable plots, crops, facilities, and assets.
- Weather intelligence using farm coordinates, forecasts, alerts, crop vulnerability, and clear live/simulated labels.
- Crop, dairy, production, yield, inventory, product, and shelf-life records.
- Transparent financial calculations including unit cost, margins, operating profit, and break-even.
- Explainable seasonal dynamic pricing with cost floors, margins, supply, inventory age, risk, and owner overrides.
- Inventory forecasting, reservations, sales, spoilage, availability, and audit history.
- Buyer CRM and owner-approved draft wholesale outreach; no unapproved email sending.
- Farm Manager Agent coordinating Weather, Production, Finance, Pricing, and Sales agents.

**Architecture requirements:** Use deterministic functions for financial calculations, inventory updates, and pricing formulas. Use LLMs only for interpretation, orchestration, and natural-language generation when needed. Keep agent calls bounded and auditable.

**Demonstration farm:** Fictional Connecticut farm, approximately 20 acres, multiple crops, small dairy operation, synthetic costs/revenue/inventory/yields/buyers. The primary end-to-end demonstration request is an upcoming tomato harvest involving weather, production, finance, pricing, and wholesale offer drafting.

**Technical direction:** FastAPI/Python backend, React/TypeScript/Vite frontend, SQLite, Tailwind-oriented styling, Recharts where useful, SVG farm visualization, modular agents, minimal services, no Docker/Redis/complex infrastructure.

**Course requirements:** Reproducible README and synthetic dataset, root/parent `.env` precedence, `.env.example`, server-side secrets, verified Portkey/OpenAI configuration, real model tokenomics, safety tests, report.html, slides.html, screenshots, traces, and no fabricated claims.

**Planning-only deliverables:** Inspect workspace; create `PROJECT_PLAN.md` and `AGENTS.md`; define MVP/stretch scope, schema, Mermaid architecture, dataset, formulas, pages, APIs, risks, implementation phases, tests, and evidence collection. Do not build or install anything in Step 1.

## Entry 2 — Step 2: Application foundation, database, and interactive virtual farm

**Request:** Implement Phase 1 while preserving the planning documents. Build the application foundation with React/TypeScript/Vite, FastAPI/Python, SQLite, SVG map, minimal dependencies, tests, README, `.env.example`, and `.gitignore`.

**Functional scope:**

- Professional dashboard with farm identity, acreage, crop plots, dairy summary, harvest schedule, inventory/financial placeholders, weather placeholder, activities, and AI placeholder.
- Database-driven clickable SVG farm map with plots, greenhouse, barn, storage, equipment, roads/paths, and persistent plot editing.
- Fictional Green Valley Farm in Connecticut: 20 acres, tomatoes, lettuce, spinach, carrots, potatoes, strawberries, sweet corn, cucumbers, dairy cows, and whole milk.
- Relational tables for farms, assets/plots, facilities, crops, production plans, products, dairy summary, expenses, and activities.
- API endpoints for farm details/update, plot listing/detail/update, products, summaries, validation, and OpenAPI docs.
- Full sidebar navigation; only Overview, Virtual Farm, and Settings fully functional. Other pages must clearly say they are coming later.
- Root `.env` takes precedence over parent `.env`; no AI or weather API calls in this phase.

**Safety and truthfulness:** Operational metrics must come from SQLite. Demo data must be labeled synthetic. Future functionality must not be represented as live. Preserve backend persistence and do not add AI agents, dynamic pricing, weather APIs, or email.

**Validation requirements:** Initialize database, verify idempotent seed data, run backend tests, build frontend, verify persistence, and report untested browser behavior honestly.

## Entry 3 — Step 2.5: Visual design upgrade and original pixel-art system

**Request:** Improve visual design without breaking Step 2 functionality or beginning Step 3.

**Design direction:** Cute, creative, warm, memorable, playful but professional, with an original blocky 2D/pixel-farm/voxel-inspired style. Do not copy Minecraft or use copyrighted assets, textures, branding, mobs, or UI.

**Visual system:** Forest green, moss, sage, wheat/beige, warm cream, barn red, sky blue, and muted soil tones. Use rounded cards where appropriate, blocky borders, soft shadows, readable modern typography, and optional pixel-inspired headings.

**Original assets:** Create reusable inline SVG components for produce, milk, cows, facilities, fields, tools/crates, farmer/owner, buyers, and AI advisor. Keep assets lightweight and scalable.

**Map/UI requirements:** Redesign the database-driven SVG farm map as a playful top-down farm board with paths, buildings, crop textures/icons, hover states, and clickable plot details. Apply the visual system to Overview, Virtual Farm, Settings, navigation, cards, forms, detail panels, empty states, and later-phase placeholders. Preserve accessibility and responsive behavior.

**Documentation:** Add `docs/DESIGN_SYSTEM.md` describing palette, component philosophy, SVG icon system, map language, and accessibility.

**Validation:** Build frontend, preserve backend tests and plot interactions, verify assets/build, and do not claim browser visual testing unless performed.

## Entry 4 — Step 2.6: Feature enhancement planning

**Request:** Do planning only. Read governing documents and inspect implementation, then update `PROJECT_PLAN.md` with a more distinctive and useful roadmap.

**Enhancements to plan:**

1. AI Farm Decision Simulator for deterministic planting/operating scenarios, including a two-acre corn-to-strawberry example, baseline/proposed deltas, labor, cost, production, profit, and risk. Scenarios must not modify real records without explicit confirmation.
2. Farm Time Machine using crop calendars and planting records to reconstruct planting, growth, flowering, harvest, and post-harvest stages.
3. Spoilage Rescue distinguishing predicted waste from actual spoilage and proposing owner-approved discounts, outreach, or other dispositions.
4. Smart Buyer Matching using availability, approved pricing, location, preferences, and timing without inventing contacts or sending communications.
5. Weather-Based Farm Tasks with priorities, deadlines, affected plots, explanations, and approval gates.
6. Dairy Animal Profiles with original pixel-art icons and linked production/cost records; do not invent health data.
7. Harvest Batch Traceability from plot and harvest date through inventory, reservations, sales, and disposition.

**Priority:** Decision Simulator, simplified Farm Time Machine, and Spoilage Rescue are distinctive MVP enhancements. Integrate buyer matching, weather tasks, dairy profiles, and traceability where feasible. Do not introduce a game engine, autonomous campaigns, or complex animation.

**Planning deliverables:** Record current implementation, database changes, revised phases through the deadline, MVP versus stretch commitments, acceptance tests, and impact/rubric rationale.

## Entry 5 — Step 3: Real weather intelligence, crop seasonality, and farm missions

**Request:** Implement weather and crop production intelligence while preserving Steps 2/2.5 and accounting for the Step 2.6 roadmap.

**Explicitly deferred in this step:** Finance, Dynamic Pricing, Buyer CRM, Sales Agent, and future AI Decision Simulator implementation.

**Weather requirements:** Integrate the U.S. National Weather Service without an API key using saved farm latitude/longitude, documented point lookup, returned forecast URLs, seven-day forecast, hourly data, active alerts, current observations when valid, source/provider/timestamp/freshness, timeouts, and safe error handling. Never fabricate weather. Open-Meteo is optional only if needed.

**Weather UI:** Functional Weather page with current conditions only when observed, seven-day high/low, precipitation probability/rainfall, wind, frost/heat warnings, official alerts, update time, original weather SVG icons, and pixel-style weather station art.

**Crop seasonality:** Add configurable crop category, planting/harvest windows, maturity, temperature thresholds, frost tolerance, heat sensitivity, water needs, yield per acre, growth stage, production status, and agronomic provenance for eight seeded crops. Unsupported precision must be labeled as configurable demonstration assumptions. Allow owner edits.

**Calendar:** Functional planting/harvest calendar with deterministic crop stages, date editing where supported, readiness, growth periods, and upcoming harvests. Do not infer crop health or actual harvest quantity from dates alone.

**Risk engine:** Deterministically compare weather forecasts to crop/facility thresholds for frost, heat, heavy rain, high wind, irrigation attention, harvest disruption, and dairy heat monitoring. Each risk needs IDs, affected records, date/time, condition, threshold, value, severity, explanation, action, source, and forecast timestamp. Do not claim guaranteed damage or fabricate financial loss.

**Farm Missions:** Persist suggested operational tasks with unique IDs, linked records, risk category, priority, deadline, action, source, and statuses Suggested/Approved/In Progress/Completed/Dismissed. Owner approval is required; no automatic worker assignments or schedule changes. Prevent duplicates and preserve audit history on refresh.

**Farm Time Machine V1:** Add a date selector/slider or calendar behavior for crop stages, distinguish recorded past/current data from reconstructed past and projected future, keep weather horizon truthfulness, preserve plot interactions, and never change production/inventory/system time.

**Dairy:** Add weather-related operational risk signals where feasible; do not present them as animal-health observations.

**Validation:** Preserve database/navigation/dashboard/map/pixel design, run backend tests and frontend build, verify live/unavailable weather behavior, and report browser verification honestly.

## Entry 6 — Prompt-log maintenance instruction

**Request:** Before proceeding to future steps, check whether `AI_prompts.md` exists. It did not exist in the workspace, so create it and summarize/log all prior prompts in chronological format. Keep this file updated for the rest of the FarmTwin AI steps and prompts using the same format.

**Status:** `AI_prompts.md` created in the project root. Future FarmTwin AI implementation or planning turns should add a new dated/numbered entry describing the user request, scope, constraints, deferred work, and validation requirements before completion.

## Maintenance format for future entries

For every future prompt, append:

- Entry number and step name.
- User-requested objective.
- Features and technical requirements.
- Explicitly deferred or prohibited work.
- Safety, data-truthfulness, and approval constraints.
- Required tests/evidence and final deliverables.
- Implementation status or planning-only status.

## Entry 7 — Step 4: Financial management, cost accounting, and capital budgeting

**Request:** Implement a comprehensive deterministic financial-management phase while preserving all previous dashboard, virtual-farm, pixel-art, crop/dairy, weather, seasonality, missions, and Time Machine work.

**Financial database scope:** Add financial transactions, annual/monthly budgets, cost allocations, and capital assets. Track direct and shared costs, product/plot/facility/dairy links, actual/budget/forecast classifications, cash/accrual distinctions, depreciation conventions, and source notes. Seed at least 12 months of internally consistent synthetic/demo financial activity.

**Deterministic calculation scope:** Implement reusable tested functions for production cost, unit cost with explicit units and zero-production handling, contribution margin, gross profit/margin, operating profit without double counting, unit and price break-even, farm-wide/product/plot/dairy profitability, overhead reconciliation, and dairy cost per liter/gallon.

**Finance UI scope:** Create a pixel-art-styled Finance page with database-backed KPI cards and charts for revenue, expenses, crop/dairy performance, monthly performance, budget versus actual, and product cost breakdown. Support month/quarter/year/product/operation filtering and clearly distinguish actual, budget, forecast, and demo assumption values.

**Operations scope:** Add financial performance to plot details, dairy financial costing, budget-versus-actual analysis, an expense manager with persistence/filtering/CSV export, validation, duplicate protection, and confirmation for destructive actions.

**Capital budgeting scope:** Add hypothetical investment scenarios for greenhouse, tractor, storage, barn, irrigation, and equipment projects. Calculate NPV, reliable IRR with invalid/multiple-result warnings, simple payback from cumulative undiscounted cash flow, defined ROI, and base/optimistic/downside sensitivity. Hypothetical scenarios must not mutate actual financial records.

**AI-readiness:** Create structured deterministic finance tools for future Finance Agent use, including farm summary, product/plot profitability, dairy financials, unit cost, budget variance, break-even, investment evaluation, and scenario comparison. Do not build full multi-agent orchestration or rely on an LLM for arithmetic in this step.

**Insights and safety:** Add rule-based insights for negative margins, unusual expenses, budget overruns, declining profitability, high unit cost, low yield, fixed-cost underutilization, and negative-NPV projects. Use Decimal or equivalent monetary safety, explicit rounding, unit validation, actual/forecast segregation, depreciation-versus-cash separation, historical-data protection, and auditability.

**Explicitly deferred:** Dynamic pricing, direct email, buyer CRM automation, full LLM agent coordination, autonomous transactions, and external accounting integrations. Do not begin Step 5 until validation passes.

**Required validation/evidence:** Safe migrations and idempotent seed data; backend tests for known-answer finance, allocation, reconciliation, dairy, budgets, NPV/IRR/payback/sensitivity, persistence, validation, and actual-versus-forecast segregation; frontend build; app startup; financial dashboard and expense persistence checks; regression checks for weather and virtual farm; honest reporting of browser limitations; README and PROJECT_PLAN updates.

## Entry 8 — Step 5: Dynamic seasonal pricing and wholesale market intelligence

**Request:** Implement a real, persistent, auditable wholesale pricing system while preserving the farm dashboard, pixel-art design, virtual farm, Time Machine, crop calendar, weather missions, cost accounting, and investment simulator.

**Pricing database scope:** Add product pricing configurations, historical selling prices, market observations, seasonality factors, pricing recommendations, scenarios, owner-approved effective-dated prices, and pricing change history for produce and dairy. Preserve raw observations separately from normalized values and retain source, unit, grade, location, freshness, and classification.

**Deterministic pricing scope:** Reuse Finance unit costs. Calculate target-margin price, gross margin, seasonality/supply-adjusted market reference, inventory/perishability and weather-risk adjustments, margin-vs-market conflict warnings, demand/sales-volume scenarios, break-even price, revenue, COGS, profit, remaining stock, and at-risk inventory. Every adjustment must be explicit, configurable, source-labeled, and never invented by an LLM.

**Market intelligence:** Build an adapter interface for USDA MyMarketNews. Do not invent credentials or require a new key. Support manual observations and a realistic synthetic dataset without USDA credentials. Validate compatible units, grades, package sizes, commercial terms, freshness, and source classification. Do not present terminal wholesale quotes as direct farm-producer prices.

**UI scope:** Add a pixel-art Dynamic Pricing page with product cards, current/recommended/minimum/approved prices, costs, margins, seasonality, inventory, market references, freshness, charts, a 12-month pricing calendar, interactive scenario simulator, formula breakdown, alerts, and owner approval/rejection/override workflow. Scenarios must not mutate transactions or approved prices.

**Integrations:** Use finance, production, weather, and available/reserved inventory identifiers consistently. Show approved price and estimated profitability in farm contexts where useful. No buyer emails, autonomous sales, payment processing, contracts, or full multi-agent orchestration.

**Safety:** Reject invalid/negative prices and zero divisions; prevent incompatible-unit comparisons, stale/unverified data misuse, nonexistent-inventory pricing, historical overwrite, prompt injection from market reports, and bulk changes without approval. Keep approval separate from recommendation and preserve history.

**AI readiness:** Add validated deterministic tool interfaces for product pricing, benchmarks, seasonal pricing, target-margin price, simulation, recommendations, scenario comparison, alerts, and approved-price retrieval. Do not build the full Pricing Agent yet.

**Required validation/evidence:** Safe migrations, idempotent synthetic pricing seed data, known-answer formula tests, unit compatibility tests, conflict/missing-data tests, scenario isolation, approval/history tests, finance reconciliation, crop/dairy differences, external-data validation, frontend build, existing-function regression, README/PROJECT_PLAN updates, and honest reporting of blocked USDA/browser integrations.

## Entry 9 — Step 6: Inventory, dairy operations, animal profiles, and spoilage rescue

**Request:** Implement a persistent, auditable inventory and dairy management system while preserving all previous FarmTwin functionality, database records, finance, pricing, weather, crop calendar, Farm Time Machine, missions, capital simulator, and original pixel-art design.

**Inventory scope:** Add storage facilities, inventory lots, movement ledger, reservations, sale fulfillment, release, adjustments, spoilage/disposal/donation, physical on-hand versus available stock, future harvest projections, and transaction-safe validation. Prevent negative inventory, over-reservation, duplicate fulfillment, incompatible units, orphaned records, and silent historical edits.

**Dairy scope:** Add named synthetic animal profiles with original sprites, milk-production records, milk inventory lots, production and processing distinctions, feed/veterinary context, individual history, and a dedicated interactive Dairy Operations page. Health claims and unsupported veterinary observations must remain `NOT_RECORDED`.

**Traceability and spoilage:** Trace crop and dairy lots to plots/facilities and movement histories. Add deterministic product-specific age-based spoilage risk, predicted-versus-actual waste separation, gross sales value at risk, conservative expired-product handling, and owner-review-only rescue recommendations. Do not change approved prices, send outreach, or sell expired products automatically.

**AI-ready tools and integration:** Prepare structured inventory, lot, dairy, spoilage, approved-price, and forecast-harvest interfaces without activating AI agents or allowing LLM-generated quantities. Reuse existing finance and pricing identifiers and formulas.

**Explicitly deferred:** Buyer CRM/matching, email, autonomous orders, direct sales automation, food-safety certification, complex processing workflows, game-engine behavior, and Step 7 functionality.

**Required validation/evidence:** Safe idempotent migration and seed checks; known-answer movement, reservation/release/fulfillment, over-reservation, unit mismatch, traceability, spoilage, dairy unit/profile, forecast-versus-actual, persistence, API validation, frontend build, and no-regression tests. Update README and PROJECT_PLAN and report browser limitations honestly.

## Entry 10 — Step 7: Wholesale buyer CRM, smart matching, sales pipeline, and AI outreach

**Request:** Implement a persistent, owner-controlled wholesale sales system that connects synthetic/owner-entered buyer records with Step 6 physical inventory and Step 5 approved prices while preserving all prior FarmTwin functionality.

**CRM scope:** Add buyers, preferences, contact verification/source fields, suppression and opt-out records, activities, opportunities, search/filtering, archive state, and synthetic Connecticut buyer profiles using safe `example.com` addresses. Do not fabricate contacts, demand, or relationships; live discovery remains optional/manual.

**Matching and offers:** Deterministically match only on stored product preferences, buyer category, quantity thresholds, physical available inventory, units, approved price range, sell-by timing, and suppression state. Explain score components and label results as potential opportunities. Create nonbinding offers with validated lot/product/unit references, approved prices or explicit owner overrides, price floors, deterministic totals, delivery dates, and source records. Creating an offer must not reserve inventory.

**Outreach safety:** Provide deterministic template email drafting from verified/stored fields. Support edit/preview/copy/export/mail-client-compatible workflow only. Never send email, never mark a draft sent because it was copied/exported/opened, include compliance placeholders and opt-out language, and treat buyer notes/imported text as untrusted.

**Pipeline and orders:** Add database-backed opportunity stages, order confirmation from an offer, transactional inventory reservations, cancellation/release, fulfillment, duplicate-fulfillment prevention, and status distinctions between potential value, draft offers, confirmed orders, and fulfilled sales. Do not process payments or duplicate finance revenue automatically.

**Explicitly deferred:** Direct email providers, OAuth, web scraping, payment processing, invoice/payment claims, autonomous outreach/orders, and full Sales Agent orchestration for Step 8.

**Required validation/evidence:** Idempotent seed/migration, buyer CRUD and suppression, matching explanations, offer totals and inventory validation, draft-not-sent safety, pipeline transitions, order reservation/fulfillment/cancellation, duplicate prevention, prompt-injection-safe buyer text handling, API validation, frontend build, regression tests, and honest browser/evidence reporting.

## Entry 11 — Step 8: Real AI agents, tool orchestration, and execution observability

**Request:** Convert FarmTwin AI into a bounded, owner-controlled AI application while preserving the deterministic weather, production, finance, pricing, inventory, dairy, and sales engines. Use either the verified course Portkey configuration or a personal OpenAI key; never invent gateway details, expose credentials, or present scripted output as a live model result.

**Implemented scope:** Add a Farm Manager model call for specialist-role selection and a model synthesis call around allowlisted deterministic specialist tools. Persist agent runs, model-call usage, tool events, latency, status, warnings, and sanitized export data. Add provider status, tokenomics aggregation, cost-unavailable handling when official rates are not verified, bounded execution, and a pixel-art AI Farm Advisor trace UI.

**Safety boundary:** AI tools are read-only in this phase. Deterministic services remain authoritative for arithmetic and provenance. No model can execute arbitrary Python, SQL, shell, or HTTP; send email; approve prices; reserve inventory; change financial records; or alter farm plans. Buyer notes, market observations, and weather text remain untrusted evidence.

**Validation:** Add mocked tests for provider/no-key behavior, role selection and synthesis, persistent calls/tool events, token aggregation, invalid structured output, allowlist enforcement, and no fabricated answer in unavailable mode. Report live provider calls, tokens, costs, browser checks, and course-gateway status only when actually observed.

