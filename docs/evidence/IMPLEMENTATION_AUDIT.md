# FarmTwin AI Step 9 implementation audit

Collected: 2026-10-22. Code under audit: local workspace, synthetic Green Valley Farm database. No API key or live provider call was used.

| Capability | Classification | Evidence / limitation |
|---|---|---|
| OpenAI Responses provider adapter | Implemented but unverified | Code exists in `backend/agents.py`; no authorized successful call was available. |
| Portkey course adapter | Blocked | Exact course gateway URL/model mapping is not present; the app refuses to invent one. |
| Farm Manager role selection | Implemented but unverified live | Mock test selects specialist roles and persists the call; live selection is not evidenced. |
| Deterministic specialist tools | Verified working | Nine allowlisted read-only tools execute existing database-backed functions; regression tests pass. |
| Tool argument/schema boundary | Partially implemented | Registry exposes closed empty-object schemas because current tools are bounded fixtures; full model-supplied typed arguments are not yet routed. |
| Agent traces | Verified working | `agent_runs`, `agent_calls`, and `agent_tool_events` persist mock and unavailable runs. |
| Provider token capture | Implemented but unverified live | Provider response fields are normalized; mocked known-answer usage is tested. |
| Tokenomics cost calculation | Blocked | No verified rate for the configured course model; API reports `UNAVAILABLE` rather than inventing cost. |
| Email safety | Verified working | No send route/provider exists; export returns `sent: false`. |
| Inventory/order safety | Verified working | Existing API tests and isolated safety lab cover over-reservation and duplicate fulfillment. |
| Price approval identity | Partially implemented | Explicit owner fields and minimum-price rules exist, but there is no authentication/authorization layer. |
| Live browser end-to-end workflow | Blocked | Port 8000 was occupied by another process during validation; no genuine model run or browser evidence was available. |

Highest-priority remaining items are obtaining the authorized course provider configuration, executing one genuine bounded tomato workflow, and capturing its sanitized trace and provider-reported usage. Do not report the mock run as live evidence.
