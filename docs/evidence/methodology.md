# Evaluation methodology

All seeded farm records are synthetic. `backend.benchmarks` prints five offline benchmark prompts and can run them only with explicit `--live`. `backend.safety_lab` creates an isolated temporary SQLite fixture and runs deterministic safety checks without model calls or outbound communication.

The mock agent tests validate persistence and token-field aggregation with known fixture values; they are not evidence of model quality. Live token/cost/latency, optimization comparisons, and user impact remain `NOT_RUN` until an authorized provider and real participant are available. A future evidence capture should include the provider/model, UTC timestamp, sanitized run export, tool coverage, correctness checks, and approval status.
