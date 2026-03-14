# Task 41 — Worker/runtime monitoring gaps

Observed from current files:

1. `scripts/run_worker.py`
   - only infinite loop + basic start log
   - no heartbeat/state file
   - no per-cycle timing
   - no consecutive failure tracking
   - no machine-readable runtime status

2. `app/services/worker.py`
   - logs per batch and per publication
   - returns only processed count
   - no summary object with seen/dispatchable/processed/failed/duration

3. `tests/test_worker.py`
   - validates dispatch and failure continuation
   - does not validate monitoring/heartbeat/status outputs

Practical slice for task 41:
- add structured worker cycle summary
- add machine-readable runtime state file for ops
- add heartbeat timestamps + consecutive failure count
- add worker healthcheck script based on heartbeat freshness
- add tests for runtime state + healthcheck behavior
