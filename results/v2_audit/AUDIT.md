# TierRoute v2 audit

Scope: independent re-check of `results/RESULTS_v2.md` and `results/v2_followup/RESULTS_followup.md` from code and raw CSV/JSON. All numbers below come from real responses (original cache plus live Groq/Ollama calls); no mock data. Test tasks, split, thresholds and classifier training data were not touched; `.env` was never printed.

## Findings (read this first)

1. **The headline router results are leaked.** In `scratch/run_benchmark_v2.py` all three routers decide to escalate using the *grader*, which sees the gold answer and runs the unit tests:
   - `:155  ok, why = grade_task_v2(t, res.text)`
   - `:175  can_escalate = (not ok) and (strat_name in ("cascade", "rules", "classifier")) and (curr_tier < 2)`
   - `tierroute/grading_v2.py:111  gold = task.get("answer", "")` and `:118  test_code = grader.get("test_code", "")` (executed in `grade_code`, `:81-88`).
   - First-tier choice is *not* leaked: rules use `analyze(prompt)` (`:131`), classifier uses `clf_v2.predict(prompt)` (`:137`), cascade always starts at tier 0 (`:128`). `results/benchmark_v2_dev_profile.json` has 60 entries, all dev ids, 0 test ids.
   - The repo's own gold-free verifier (`tierroute/verifier.py`, called from `tierroute/router.py`) is **never used by the benchmark**. `RESULTS_v2.md` (item on `finish_reason: length`) says truncation was "handled naturally by the verifier"; that is false for the benchmark run.
2. **"Escalations == under-routed == 48/60" is not a coincidence; it is a mechanical identity caused by (1).** Escalation = "model at current tier fails the grader". Under-routed = first tier < oracle tier, and the oracle tier = lowest tier that passes the *same grader on the same cached outputs*. Replaying on the real responses, the escalated task *sets* equal the under-routed sets exactly (rules 19, classifier 15, cascade 26; `sets identical = True`). Quality then equals the oracle's 48/60 because every router keeps climbing until the grader says pass. With a deployable verifier the identity disappears (1 escalation vs 15-26 under-routed).
3. **With a gold-free verifier the routers lose most of their quality.** Verifier = empty output, `finish_reason=length`, uncertainty phrase (the existing `UNSURE` list, unchanged), Python `ast.parse` failure, missing `Answer:` when the prompt asks for it. On the real outputs it fires on only 1-7 responses per tier, while 25 of 60 tier-0 answers, 9-13 tier-1 and 7-11 tier-2 answers are wrong yet pass it. Result (60 tasks, original grader, config 1024/default; same pattern in the other configs):

   | router | leaky (as published) | deployable verifier | always_strong |
   |---|---|---|---|
   | cascade | 48/60, $0.010386 (-30.1%) | **35/60**, $0.000046 (-99.7%) | 46/60, $0.014849 |
   | rules | 48/60, $0.011629 (-21.7%) | **42/60**, $0.002265 (-84.7%) | |
   | classifier | 48/60, $0.008970 (-39.6%) | **38/60**, $0.004932 (-66.8%) | |

   The cost "savings" under the deployable verifier are almost entirely lost quality (-4 to -11 tasks vs always_strong), not free savings. The claim "routers beat always_strong on quality at lower cost" does **not** survive.
4. **Prices.** `config/models.yaml`: mid 0.075 in / 0.30 out, strong 0.15 in / 0.60 out USD per 1M tokens, local 0/0. CSV costs match these exactly (674 single-attempt rows, 0 mismatches). `RESULTS_followup.md` section 3 *prose* states different prices (mid `$0.000100`/`$0.30`, strong `$0.59`/`$0.79`); `report_pack/test_cases.md:44` also uses 0.59/0.79. The followup *totals* (e.g. oracle $0.007897) were computed with the yaml prices, so the prose is wrong but the totals are not. At 0.59/0.79 always_strong would cost $0.023220, not $0.014849.
5. **Identical settings** (hosted tiers all run with the same `max_tokens` / `reasoning_effort`; tier 0 reused at 1024):
   - always_strong: 1024/default 46/60 $0.014849 (6 truncated); 4096/default 46/60 $0.015110 (0 truncated); 4096/low 47/60 $0.010194.
   - Leaky router savings vs always_strong (60 tasks), 1024-default / 4096-default / 4096-low: classifier 39.6% / 31.2% / 39.8%, rules 21.7% / 12.4% / 23.1%, cascade 30.1% / 20.6% / 32.1%. Deployable-verifier numbers are in the tables below.
6. **True cost-minimising oracle.** The previous oracle sends the 12 tasks nobody solves to the strong tier; that costs $0.006186 of its $0.007897 (78%). Sending them to the cheapest tier (local, $0) and choosing the cheapest passing tier otherwise gives **$0.001711 at 48/60** (88.5% saving) vs previous $0.007897 (46.8%). The classifier's "84.6% of max saving" becomes 44.7% against the true oracle. Both oracles are post-hoc and use test outputs; neither is deployable.
7. **Formatting-robust grader** (extraction tasks only: strip markdown `*`, edge underscores, NFKC/Unicode spaces, all dash variants, curly quotes). It lifts always_strong (46 -> 48 at 1024, 46 -> 49 at 4096-default, 47 -> 48 at 4096-low) and random by 1 in config B; routers are unchanged. So the "routers beat always_strong by 2 tasks" gap is a grader-formatting artifact (V2-107 `**...**`, V2-108 U+202F): under the robust grader leaky routers tie always_strong in configs A and B (48 vs 48, 49 vs 49) and lead by 1 in C (49 vs 48).
8. **MBPP NameError.** All 8 MBPP test tasks (V2-071..076, 079, 080) show `NameError` at >=1 tier (the prompt omits the required function name); only V2-071 and V2-080 fail with NameError at every tier. Excluding all 8 leaves 52 tasks; tables show both 60 and 52. On 52 the leaky savings are larger (classifier 57.0% at config A) because the unsolved MBPP tasks were costing strong-tier calls.
9. **Run-to-run noise is large relative to the claimed gaps.** At temperature 0, Groq `gpt-oss-120b` gave a different token count on 28 of 60 tasks between the followup 4096/default run and my rerun, and the score moved 47 -> 46 (cost $0.016180 -> $0.015110). The followup states 10 truncations for the 1024 baseline; the raw CSV and my replay show **6**. The followup's "-28.48%" and "34.4%" for the low-effort cost cut use different baselines (1024 vs 4096) without saying so.

## Problem log

| # | problem | where | effect |
|---|---|---|---|
| P1 | escalation uses gold/unit-test grader | `run_benchmark_v2.py:155,175` | headline quality/cost invalid as a deployable result |
| P2 | repo's gold-free `verify()` unused by benchmark; report claims it was | `RESULTS_v2.md`, `router.py` | misleading |
| P3 | wrong prices in prose | `RESULTS_followup.md` sec. 3, `report_pack/test_cases.md:44` | prose only; totals use yaml |
| P4 | 10 truncations claimed, CSV has 6 | `RESULTS_followup.md` sec. 2 | misreport |
| P5 | `reasoning_effort` never set in the main benchmark; followup reran only `always_strong` at 4096 | `run_benchmark_v2.py:84` | routers vs baseline compared under different settings |
| P6 | MBPP prompts omit function name -> NameError | tasks_v2.json (MBPP) | 8 tasks unfair; not modified, reported at 60 and 52 |
| P7 | strict extraction grader penalises `**` / U+202F | `grading_v2.py:54-67` | strong penalised on 2-3 tasks; original kept, robust added |
| P8 | previous oracle sends unsolved tasks to strong | `run_benchmark_v2.py:297-298` | oracle cost inflated 4.6x |
| P9 | Groq HTTP 429 / connection failures during this audit (7 in config B, 38 in config C on first pass) | `collect*.log` | retried with 30 s waits until 0 errors; nothing dropped or imputed |
| P10 | outputs not deterministic at temperature 0 | Groq | +-1-2 task noise; no CIs computed |

## Method notes and limits

- One real response per (task, tier, config) is stored (`responses_*.json`); every router is *replayed* over that matrix, so all routers see the same sample. Config A responses are the original run's cache (1024, default effort); B and C are fresh live calls; tier 0 (Ollama llama3.2:3b, 1024 tokens) is reused in all three configs.
- First-tier logic is imported unchanged (`analyze`, `ComplexityClassifierV2`, thresholds 0.50/0.74, bias 0.5; random uses seed 42 in the original order). Leaky replay on config A reproduces the original CSV exactly (48/48/48; $0.010386 / $0.011629 / $0.008970).
- The deployable verifier was fixed before looking at results (phrase list reused unchanged from `tierroute/verifier.py`). "empty" is checked before `finish_reason=length`, so truncated responses with empty content count as `empty`. It has no access to gold, grader or tests.
- The code check is `ast.parse` only; it cannot see wrong-but-valid code, which is why most failures pass.
- n = 60 (52); no confidence intervals computed; differences of 1-2 tasks are within the noise in finding 9.

## Reproduce

```bash
python results/v2_audit/collect.py   # live calls, resumable (needs GROQ_API_KEY in .env, Ollama running)
python results/v2_audit/analyze.py   # replays routers/oracles; writes tables.md, per_task_rows.csv
```

Files: `audit_lib.py` (robust grader + deployable verifier), `responses_*.json` (raw outputs), `per_task_rows.csv` (task x config x strategy x escalation), `nameerror_tasks.json`.

## Tables (generated by analyze.py; "orig" = original grader, "robust" = formatting-robust variant)

Escalation signal: `none` = baseline, `leaky` = original grader (gold + unit tests), `deploy` = gold-free verifier. Oracle rows are post-hoc, not deployable.


#### A_1024_default - all 60 tasks

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/60 | 48/60 | 0.014849 | 0.0% | - | 0/0/60 |
| always_cheap | none | 34/60 | 34/60 | 0.000000 | 100.0% | - | 60/0/0 |
| random | none | 41/60 | 41/60 | 0.005299 | 64.3% | - | 25/15/20 |
| cascade | leaky | 48/60 | 48/60 | 0.010386 | 30.1% | 26 | 34/13/13 |
| cascade | deploy | 35/60 | 35/60 | 0.000046 | 99.7% | 1 | 59/1/0 |
| rules | leaky | 48/60 | 48/60 | 0.011629 | 21.7% | 19 | 26/19/15 |
| rules | deploy | 42/60 | 42/60 | 0.002265 | 84.7% | 1 | 43/15/2 |
| classifier | leaky | 48/60 | 48/60 | 0.008970 | 39.6% | 15 | 34/13/13 |
| classifier | deploy | 38/60 | 38/60 | 0.004932 | 66.8% | 1 | 48/4/8 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 48/60 | 48/60 | 0.007897 | 46.8% | - | 34/13/13 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/60 | 48/60 | 0.001711 | 88.5% | - | 46/13/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 48/60 | 48/60 | 0.007897 | 46.8% | - | 34/13/13 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/60 | 48/60 | 0.001711 | 88.5% | - | 46/13/1 |

#### A_1024_default - 52 tasks (excl. MBPP NameError)

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/52 | 48/52 | 0.010315 | 0.0% | - | 0/0/52 |
| always_cheap | none | 34/52 | 34/52 | 0.000000 | 100.0% | - | 52/0/0 |
| random | none | 41/52 | 41/52 | 0.004043 | 60.8% | - | 22/11/19 |
| cascade | leaky | 48/52 | 48/52 | 0.004436 | 57.0% | 18 | 34/13/5 |
| cascade | deploy | 35/52 | 35/52 | 0.000046 | 99.6% | 1 | 51/1/0 |
| rules | leaky | 48/52 | 48/52 | 0.005678 | 45.0% | 11 | 26/19/7 |
| rules | deploy | 42/52 | 42/52 | 0.002265 | 78.0% | 1 | 35/15/2 |
| classifier | leaky | 48/52 | 48/52 | 0.004436 | 57.0% | 15 | 34/13/5 |
| classifier | deploy | 38/52 | 38/52 | 0.000398 | 96.1% | 1 | 48/4/0 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 48/52 | 48/52 | 0.003362 | 67.4% | - | 34/13/5 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/52 | 48/52 | 0.001711 | 83.4% | - | 38/13/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 48/52 | 48/52 | 0.003362 | 67.4% | - | 34/13/5 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/52 | 48/52 | 0.001711 | 83.4% | - | 38/13/1 |

#### B_4096_default - all 60 tasks

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/60 | 49/60 | 0.015110 | 0.0% | - | 0/0/60 |
| always_cheap | none | 34/60 | 34/60 | 0.000000 | 100.0% | - | 60/0/0 |
| random | none | 40/60 | 41/60 | 0.006276 | 58.5% | - | 25/15/20 |
| cascade | leaky | 49/60 | 49/60 | 0.011991 | 20.6% | 26 | 34/14/12 |
| cascade | deploy | 35/60 | 35/60 | 0.000046 | 99.7% | 1 | 59/1/0 |
| rules | leaky | 49/60 | 49/60 | 0.013233 | 12.4% | 19 | 26/20/14 |
| rules | deploy | 42/60 | 42/60 | 0.002258 | 85.1% | 1 | 43/15/2 |
| classifier | leaky | 49/60 | 49/60 | 0.010401 | 31.2% | 15 | 34/14/12 |
| classifier | deploy | 38/60 | 38/60 | 0.005117 | 66.1% | 1 | 48/4/8 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.007802 | 48.4% | - | 34/14/12 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.002120 | 86.0% | - | 45/14/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.007802 | 48.4% | - | 34/14/12 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.002120 | 86.0% | - | 45/14/1 |

#### B_4096_default - 52 tasks (excl. MBPP NameError)

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/52 | 49/52 | 0.010391 | 0.0% | - | 0/0/52 |
| always_cheap | none | 34/52 | 34/52 | 0.000000 | 100.0% | - | 52/0/0 |
| random | none | 40/52 | 41/52 | 0.004960 | 52.3% | - | 22/11/19 |
| cascade | leaky | 49/52 | 49/52 | 0.005682 | 45.3% | 18 | 34/14/4 |
| cascade | deploy | 35/52 | 35/52 | 0.000046 | 99.6% | 1 | 51/1/0 |
| rules | leaky | 49/52 | 49/52 | 0.006925 | 33.4% | 11 | 26/20/6 |
| rules | deploy | 42/52 | 42/52 | 0.002258 | 78.3% | 1 | 35/15/2 |
| classifier | leaky | 49/52 | 49/52 | 0.005682 | 45.3% | 15 | 34/14/4 |
| classifier | deploy | 38/52 | 38/52 | 0.000398 | 96.2% | 1 | 48/4/0 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.003083 | 70.3% | - | 34/14/4 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.002120 | 79.6% | - | 37/14/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.003083 | 70.3% | - | 34/14/4 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.002120 | 79.6% | - | 37/14/1 |

#### C_4096_low - all 60 tasks

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 47/60 | 48/60 | 0.010194 | 0.0% | - | 0/0/60 |
| always_cheap | none | 34/60 | 34/60 | 0.000000 | 100.0% | - | 60/0/0 |
| random | none | 39/60 | 39/60 | 0.003319 | 67.4% | - | 25/15/20 |
| cascade | leaky | 49/60 | 49/60 | 0.006920 | 32.1% | 26 | 34/13/13 |
| cascade | deploy | 35/60 | 35/60 | 0.000023 | 99.8% | 1 | 59/1/0 |
| rules | leaky | 49/60 | 49/60 | 0.007841 | 23.1% | 19 | 26/19/15 |
| rules | deploy | 42/60 | 42/60 | 0.001555 | 84.8% | 1 | 43/15/2 |
| classifier | leaky | 49/60 | 49/60 | 0.006136 | 39.8% | 15 | 34/13/13 |
| classifier | deploy | 38/60 | 38/60 | 0.003869 | 62.0% | 1 | 48/4/8 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.005573 | 45.3% | - | 34/13/13 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.001221 | 88.0% | - | 45/13/2 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.005573 | 45.3% | - | 34/13/13 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.001221 | 88.0% | - | 45/13/2 |

#### C_4096_low - 52 tasks (excl. MBPP NameError)

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 47/52 | 48/52 | 0.006609 | 0.0% | - | 0/0/52 |
| always_cheap | none | 34/52 | 34/52 | 0.000000 | 100.0% | - | 52/0/0 |
| random | none | 39/52 | 39/52 | 0.002493 | 62.3% | - | 22/11/19 |
| cascade | leaky | 49/52 | 49/52 | 0.002551 | 61.4% | 18 | 34/13/5 |
| cascade | deploy | 35/52 | 35/52 | 0.000023 | 99.6% | 1 | 51/1/0 |
| rules | leaky | 49/52 | 49/52 | 0.003472 | 47.5% | 11 | 26/19/7 |
| rules | deploy | 42/52 | 42/52 | 0.001555 | 76.5% | 1 | 35/15/2 |
| classifier | leaky | 49/52 | 49/52 | 0.002551 | 61.4% | 15 | 34/13/5 |
| classifier | deploy | 38/52 | 38/52 | 0.000283 | 95.7% | 1 | 48/4/0 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.001988 | 69.9% | - | 34/13/5 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.001221 | 81.5% | - | 37/13/2 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.001988 | 69.9% | - | 34/13/5 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.001221 | 81.5% | - | 37/13/2 |

#### Escalations vs under-routed (cfg A; under-routed = first tier < previous-oracle tier)

| router | escalation signal | escalations | under-routed | sets identical |
|---|---|---|---|---|
| rules | leaky | 19 | 19 | True |
| rules | deploy | 1 | 19 | False |
| classifier | leaky | 15 | 15 | True |
| classifier | deploy | 1 | 15 | False |
| cascade | leaky | 26 | 26 | True |
| cascade | deploy | 1 | 26 | False |

#### Deployable-verifier outcomes on every response

| config | tier | verifier reasons |
|---|---|---|
| A_1024_default | 0 | {'ok': 59, 'missing_Answer_format': 1} |
| A_1024_default | 1 | {'ok': 56, 'empty': 3, 'finish_reason=length': 1} |
| A_1024_default | 2 | {'ok': 53, 'finish_reason=length': 6, 'python_parse_failure': 1} |
| B_4096_default | 0 | {'ok': 59, 'missing_Answer_format': 1} |
| B_4096_default | 1 | {'ok': 58, 'empty': 2} |
| B_4096_default | 2 | {'ok': 56, 'python_parse_failure': 4} |
| C_4096_low | 0 | {'ok': 59, 'missing_Answer_format': 1} |
| C_4096_low | 1 | {'ok': 60} |
| C_4096_low | 2 | {'ok': 58, 'python_parse_failure': 2} |

#### Verifier vs original grader (all responses)

| config | tier | pass & correct | pass & WRONG (missed) | fail & correct (wasted esc.) | fail & wrong |
|---|---|---|---|---|---|
| A_1024_default | 0 | 34 | 25 | 0 | 1 |
| A_1024_default | 1 | 47 | 9 | 0 | 4 |
| A_1024_default | 2 | 46 | 7 | 0 | 7 |
| B_4096_default | 0 | 34 | 25 | 0 | 1 |
| B_4096_default | 1 | 48 | 10 | 0 | 2 |
| B_4096_default | 2 | 46 | 10 | 0 | 4 |
| C_4096_low | 0 | 34 | 25 | 0 | 1 |
| C_4096_low | 1 | 47 | 13 | 0 | 0 |
| C_4096_low | 2 | 47 | 11 | 0 | 2 |

#### Per-tier standalone quality (60 tasks)

| config | tier | orig | robust | cost $ | finish=length |
|---|---|---|---|---|---|
| A_1024_default | 0 | 34 | 34 | 0.000000 | 0 |
| A_1024_default | 1 | 47 | 47 | 0.006847 | 4 |
| A_1024_default | 2 | 46 | 48 | 0.014849 | 6 |
| B_4096_default | 0 | 34 | 34 | 0.000000 | 0 |
| B_4096_default | 1 | 48 | 48 | 0.008955 | 2 |
| B_4096_default | 2 | 46 | 49 | 0.015110 | 0 |
| C_4096_low | 0 | 34 | 34 | 0.000000 | 0 |
| C_4096_low | 1 | 47 | 47 | 0.003883 | 0 |
| C_4096_low | 2 | 47 | 48 | 0.010194 | 0 |
