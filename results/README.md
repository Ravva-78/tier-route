# results/ index

Status of every output. **Invalid** = produced by (or derived from) the leaked-escalation bug: routers escalated
on `grade_task_v2`, i.e. on gold answers and unit-test outcomes (see `v2_audit/AUDIT.md`). Do not cite these numbers.

| path | status |
|---|---|
| `RESULTS_v2.md` | **invalid: leaked escalation** (router quality/cost/oracle-match claims) |
| `benchmark_v2.json`, `benchmark_v2_raw.csv`, `benchmark_v2_dev_profile.json` (as router evidence) | **invalid: leaked escalation** (raw model outputs in `benchmark_v2_call_cache.json` are real and reused by the audit; the dev profile's oracle tiers are still valid classifier training labels) |
| `v2_followup/` (`RESULTS_followup.md`, `analysis_data.json`, ...) | **invalid: leaked escalation** for router/oracle/bootstrap claims; also contains wrong prices in prose and a wrong truncation count (see audit). The always_strong 4096 runs are real single samples |
| `v2_audit/` | valid: audit of the above; routers there are replayed with a gold-free verifier |
| `RESULTS.md`, `benchmark_live*.json/csv`, `benchmark_mock.json`, `report_pack/` (v1) | v1 benchmark: escalation used the heuristic `verify()` (not graders), but v1 tasks/splits predate the audit and were not re-audited; mock numbers are simulated |
| `final/` | current, deployable results (see `final/RESULTS_FINAL.md`) |
