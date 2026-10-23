# Report evidence audit

Collected: 2026-10-23. This audit maps material claims in `report.html` to repository evidence. It does not create new measurements.

| Claim or metric in report | Supporting source | Verification status | Caveat |
|---|---|---|---|
| FarmTwin is a local FastAPI + React/Vite + SQLite application | `README.md`, `PROJECT_PLAN.md`, `backend/`, `frontend/` | Verified implementation | Local application; no deployed URL claimed. |
| 41 backend tests passed | `docs/evidence/poultry_operations_verification.md` | Verified recorded run | Result was collected on 2026-10-23; warnings were reported separately. |
| Frontend build transformed 1,945 modules | `docs/evidence/poultry_operations_verification.md` | Verified recorded build | Build success is not browser click-through or user-impact evidence. |
| Live weather request succeeded | `docs/evidence/weather_live_request.md`, `weather_connectivity_diagnostics.md` | Verified external request | Runtime network permission is required; weather is model forecast data, not farm sensor data. |
| Weather used New Haven coordinates 41.3083, -72.9279 | `docs/evidence/weather_live_request.md` | Verified | Approximate city-center demonstration coordinates. |
| Weather returned seven-day forecast and zero active NWS alerts | `docs/evidence/weather_live_request.md` | Verified recorded response | Status can change on later requests. |
| Weather cache followed live response | `docs/evidence/weather_live_request.md` | Verified recorded response | Preserved cache age was approximately 5.8 seconds in that run. |
| Eight crop records in weather intelligence | `docs/evidence/weather_connectivity_diagnostics.md` | Verified recorded API response | Seeded database records; not a claim about a real farm. |
| Six dairy animals, 30-day history | `docs/evidence/dairy_operations_verification.md`, `README.md` | Verified local synthetic dataset | Records are synthetic and the persistent database was not reset. |
| Forty laying hens, three flocks, 33 eggs today, 30 loose available | `docs/evidence/poultry_operations_verification.md` | Verified local synthetic smoke check | Demonstration values; not farm observations. |
| Five specialist domains coordinated by Farm Manager | `AGENTS.md`, `PROJECT_PLAN.md`, `backend/agents.py`, `IMPLEMENTATION_AUDIT.md` | Verified architecture | Dairy and poultry are tool groups, not separately claimed autonomous model loops. |
| Agent registry contains deterministic read tools | `backend/agents.py`, `IMPLEMENTATION_AUDIT.md` | Verified implementation | Live model selection and synthesis remain unverified. |
| Model limits are 3 calls, 32 tools, 900 output tokens, 5,000 total tokens, 60 seconds | `backend/agents.py` | Verified code constants | Limits do not equal provider account-level daily caps. |
| Live AI run was not completed | `token_usage.csv`, `benchmark_results.csv`, `IMPLEMENTATION_AUDIT.md` | Verified not-run status | No live model claim is made. |
| Mock fixture has 2 calls, 20 input, 4 cached input, 16 output, 36 total tokens | `docs/evidence/token_usage.csv` | Verified mock record | Mock fixture is not live usage, quality evidence, or billed cost. |
| Cost is unavailable | `token_usage.csv`, `cost_optimization.csv`, `IMPLEMENTATION_AUDIT.md` | Verified status | No verified model rate or actual bill was available. |
| Safety lab has five recorded passing checks | `docs/evidence/safety_test_results.json` | Verified deterministic/simulated lab | Not live-model adversarial evidence; no credentials or recipients were used. |
| Prompt-injection buyer-note test blocked malicious text from model-facing summary | `safety_test_results.json`, `THREAT_MODEL.md` | Verified simulated result | The model itself was not live in this test. |
| No outbound email capability in MVP | `AGENTS.md`, `README.md`, `backend/main.py`, safety artifact | Verified implementation/test boundary | Future sender would require new authentication and safety controls. |
| User impact is not measured | `impact_evaluation.csv`, `methodology.md` | Verified not-run template | No participant, timing, revenue, or waste result is claimed. |
| No browser screenshots are included | workspace image inventory; dairy/poultry verification notes | Verified repository state | The report uses labeled inline illustrations instead of pretending they are screenshots. |
| Competitor comparison is qualified | official URL references in report | Partially verified reference list | External requests were unavailable during this run; exact product-plan feature scope should be checked before submission. |

## Consistency notes

- `report.html` and `slides.html` both state that the provider, live token/cost, impact, and screenshot evidence gaps remain.
- Both artifacts describe five specialist domains rather than claiming six autonomous model agents.
- Both use 41 backend tests, 1,945 frontend modules, seven forecast days, and zero active NWS alerts consistently.
- Synthetic records are not described as real farm observations.
