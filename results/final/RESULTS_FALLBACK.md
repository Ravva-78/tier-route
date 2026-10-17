# TierRoute fallback results (v2 audit data only)

> **The v3 run is INCOMPLETE. No v3 numbers exist.** `benchmark/run_final.py` has not finished (Groq `openai/gpt-oss-120b` free tier: 200,000 tokens per rolling 24 h; the run is waiting and retrying). Nothing in this file comes from v3. Nothing was estimated or filled in: every number below is copied or recomputed from `results/v2_audit/` (replay of real model responses with a gold-free verifier), `results/benchmark_v2_dev_profile.json` and `config/models.yaml`.

## Findings

1. The earlier v2 router results were leaked: routers escalated on `grade_task_v2` (gold answers and unit tests). Replayed with a gold-free verifier, router quality is far below the published 48/60 (Table 2).
2. The deployable-verifier routers are cheap mainly because they accept wrong answers: the verifier accepts most wrong answers from the local and mid tiers (Table 4). Those cost savings are not free savings.
3. A true cost-minimising oracle (unsolved tasks go to the cheapest tier) costs far less than the earlier oracle (Table 3), because the earlier one paid the strong tier for tasks no model solves.
4. Everything is a single sample per (task, tier, config) on 60 tasks (52 after excluding the MBPP NameError tasks). Differences of 1-2 tasks are within run-to-run noise; no confidence intervals are computed in this fallback.

## Prices (config/models.yaml, USD per 1M tokens) and how costs are computed

| model | in | out |
|---|---|---|
| local-small (`llama3.2:3b`) | 0.0 | 0.0 |
| hosted-mid (`openai/gpt-oss-20b`) | 0.075 | 0.3 |
| hosted-strong (`openai/gpt-oss-120b`) | 0.15 | 0.6 |

Cost of one call = (tokens_in x price_in + tokens_out x price_out) / 1,000,000, with the token counts returned by the API. `results/v2_audit/analyze.py` computes every cost below through `ModelSpec.cost` from `tierroute/config.py`, which reads exactly these prices. The audit verifier makes no extra model calls, so no verifier cost is added.

## Table 1 - Configurations (hosted calls identical within a configuration)

| config | hosted max_tokens | hosted reasoning_effort | source of responses |
|---|---|---|---|
| A_1024_default | 1024 | default | original v2 run cache (`results/benchmark_v2_call_cache.json`) |
| B_4096_default | 4096 | default | live audit calls (`results/v2_audit/responses_B_4096_default.json`) |
| C_4096_low | 4096 | low | live audit calls (`results/v2_audit/responses_C_4096_low.json`) |

The local tier (Ollama `llama3.2:3b`, 1024 tokens) is the same cached response set in all three. Task set: v2 TEST (60 tasks).

## Table 2 - Deployable-verifier results on the v2 TEST tasks (rows copied from `results/v2_audit/tables.md`)

Escalation signal `leaky` = the original grader (gold + unit tests); shown only to reproduce the invalid published numbers. `deploy` = the gold-free verifier in `results/v2_audit/audit_lib.py` (empty output, `finish_reason=length`, uncertainty phrase, Python parse failure, missing `Answer:` format). Quality is given under the original grader and the formatting-robust grader (they differ only on extraction tasks). Saving is vs `always_strong` in the same configuration.

##### A_1024_default - all 60 tasks

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

##### B_4096_default - all 60 tasks

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

##### C_4096_low - all 60 tasks

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

##### A_1024_default - 52 tasks (excl. MBPP NameError)

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

##### C_4096_low - 52 tasks (excl. MBPP NameError)

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

Complete tables for every configuration and subset, including both oracle definitions under the robust grader, are in `results/v2_audit/tables.md` and `results/v2_audit/AUDIT.md`.

## Table 3 - Oracles (config A, 60 tasks, from `results/v2_audit/tables.md`)

| oracle | quality (orig grader) | cost $ | saving vs always_strong | workload L/M/S |
|---|---|---|---|---|
| previous oracle (unsolved->tier2) | 48/60 | 0.007897 | 46.8% | 34/13/13 |
| TRUE cost-min oracle (unsolved->cheapest) | 48/60 | 0.001711 | 88.5% | 46/13/1 |

The earlier oracle sends tasks that no model solves to the strong tier. The true cost-minimising oracle sends them to the cheapest tier and, for solved tasks, picks the cheapest passing tier. Both are post-hoc (they use the test outputs), so neither is deployable.

## Table 4 - How well the gold-free verifier catches wrong answers (from `results/v2_audit/tables.md`)


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

`pass & WRONG` = the verifier accepted an answer the grader marks wrong (a missed error).

## Table 5 - Escalations vs under-routed (config A)


| router | escalation signal | escalations | under-routed | sets identical |
|---|---|---|---|---|
| rules | leaky | 19 | 19 | True |
| rules | deploy | 1 | 19 | False |
| classifier | leaky | 15 | 15 | True |
| classifier | deploy | 1 | 15 | False |
| cascade | leaky | 26 | 26 | True |
| cascade | deploy | 1 | 26 | False |

## Table 6 - v2 DEV profile (`results/benchmark_v2_dev_profile.json`: 60 DEV tasks, 1024 tokens, default effort)

Per-model outcomes on the DEV tasks and the oracle tier used as classifier training labels (lowest tier that passed the grader; tasks no model solved are labelled tier 2).

| oracle tier | tasks |
|---|---|
| 0 | 41 |
| 1 | 10 |
| 2 | 9 |

| model | DEV tasks passed (of 60) |
|---|---|
| local-small | 41 |
| hosted-mid | 48 |
| hosted-strong | 52 |

| dataset | oracle tier 0 | tier 1 | tier 2 |
|---|---|---|---|
| ARC-Challenge | 13 | 4 | 0 |
| GSM8K | 13 | 4 | 0 |
| HumanEval | 7 | 0 | 1 |
| MBPP | 0 | 0 | 8 |
| MessyExtraction-v2 | 8 | 2 | 0 |

These labels came from the grader on DEV tasks only, which is legitimate as training data; the profile holds 60 DEV ids and no TEST ids (checked in the audit).

## Methodology lesson: leaked escalation

**What it was.** In the original `scratch/run_benchmark_v2.py`, each router called a model, then called `grade_task_v2(task, output)` and escalated to the next tier whenever the grader said the answer was wrong. That grader compares against the gold answer and runs the task's unit tests, so the router was told after every attempt whether it was right. A real deployment has no such signal.

**How it was found.** The published results showed, for all three routers, escalations exactly equal to the number of under-routed tasks and quality exactly equal to the oracle (48/60). That is suspicious because the routers start from very different places. Reading the code showed escalation depended on `grade_task_v2`. Replaying the saved responses confirmed that the escalated task sets equal the under-routed sets exactly (Table 5, `sets identical = True`): both are defined by the same grader on the same outputs. With a gold-free verifier the identity disappears.

**How it was fixed.** (1) Graders moved into a separate `evaluation/` package; `tierroute/strategies.py` and `tierroute/verifiers.py` take only the prompt and the model output. (2) `tests/test_no_leak.py` fails if a `tierroute/` module imports grading code or uses gold/test identifiers, and runs every strategy and verifier with the graders replaced by objects that raise when touched. (3) `scratch/run_benchmark_v2.py` was rewritten to escalate only on a gold-free verifier and to grade after routing. (4) Old outputs are labelled invalid in `results/README.md`. (5) A fresh held-out set (v3) was frozen with a SHA-256 before any model saw it. Step 5 is built, but its model run is incomplete.

## Limitations

* **No v3 results.** Everything here is on the v2 TEST tasks, which were visible during earlier development (thresholds were tuned on DEV and the classifier trains on DEV), so this is not a fresh held-out measurement.
* One real response per (task, tier, config). Groq output is not deterministic at temperature 0 (the audit saw different token counts on 28 of 60 tasks between two runs), so +-1-2 tasks is noise. No confidence intervals here.
* n = 60 (52 after removing the 8 MBPP tasks whose prompts omit the function name and fail with NameError at one or more tiers).
* The audit's gold-free verifier is one fixed design (phrase list reused from `tierroute/verifier.py`; the code check is `ast.parse` only). Other verifiers (self-consistency, LLM judge) were implemented later and are not evaluated in this file.
* Config A responses come from the original 1024-token run; the local tier is reused in all configs; hosted configs differ in token budget and reasoning effort.
* Cost uses API-reported token counts and the yaml prices; the local tier is counted as $0 (electricity and hardware ignored).
* Oracles are post-hoc upper bounds, not deployable systems.
* Earlier reports contain wrong price prose (0.59/0.79) and a wrong truncation count (`results/v2_audit/AUDIT.md`). The Docker image build was not tested (the Docker engine was not running).

## Reproduction commands

```bash
# regenerate the audit tables from the saved real responses (no API calls)
python results/v2_audit/analyze.py

# regenerate this file
python results/final/make_fallback.py

# optional: re-collect the audit responses live (needs GROQ_API_KEY in .env and Ollama running; Groq rate limits apply)
python results/v2_audit/collect.py

# offline tests including the no-leak guards
python -m pytest tests -q

# DEV profile statistics (Table 6, tier counts)
python -c "import json,collections;d=json.load(open('results/benchmark_v2_dev_profile.json',encoding='utf-8'));print(collections.Counter(v['oracle_tier'] for v in d.values()))"

# the final held-out v3 run (still incomplete; do not start a second copy while one is running)
python benchmark/run_final.py
```
