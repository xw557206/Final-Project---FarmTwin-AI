# FarmTwin AI threat model

Collected: 2026-10-22. Results below are deterministic or mocked unless explicitly marked live. All records are synthetic.

| Threat | Component / consequence | Defense | Test / result | Remaining risk |
|---|---|---|---|---|
| Buyer/market/weather text injection | Agent context could disclose secrets or mutate records | Source tools expose bounded fields; tools are read-only; no secret fields | Safety lab simulated malicious buyer text: passed | Live-model behavior not tested; prompt defense should remain layered. |
| Unauthorized email | Buyer harm / compliance breach | No SMTP/send route; export contract returns `sent=false` | Safety lab: passed | A future sender needs auth, opt-out, and provider confirmation. |
| Unauthorized price change | Incorrect commercial terms | Price floor and explicit approval route | Existing pricing tests: passed | No authentication layer verifies the claimed owner identity. |
| Over-reservation / duplicate fulfillment | Negative or double-counted stock | Transactional availability checks and reservation status | Safety lab: passed | Concurrent production deployment is outside local SQLite scope. |
| Hallucinated farm facts | Bad decisions | Deterministic tools own arithmetic and source labels; no-key mode gives no fake answer | Mock synthesis uses tool evidence only: passed | Genuine model provenance still requires live evidence. |
| Infinite loops / spend | Excess API cost | Model/tool/token/time budgets; bounded two-call workflow | Budget checks are backend-enforced; unit coverage exists for no-key and invalid output | No daily account-level cap is implemented. |
| Credential/data leakage | Secret or unnecessary PII exposure | Keys remain server-side; buyer tool summaries omit contact details | Registry and sanitized export inspection: passed | Server logs should still be reviewed before submission. |
| Retry duplicates | Repeated state change | Step 8 tools are read-only; Step 7 mutations retain their own validation | No mutation is reachable from agent registry: passed | Future mutating tools require idempotency keys and approval records. |
