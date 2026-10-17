"""Generates results/final/PROJECT_STATUS.md from real files only (facts + live-check outputs recorded by hand below
from this session's runs). No report prose is written here."""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, ".")
from tierroute.classifier import SEED_TRAINING_DATA
from tierroute.config import load_config

cfg = load_config()
rows = json.load(open(sys.argv[1], encoding="utf-8"))
cnt = {}
for r in rows:
    cnt[r["base"]] = cnt.get(r["base"], 0) + 1
cache = json.load(open("results/final/cache_v3_main.json", encoding="utf-8"))
mt = datetime.datetime.fromtimestamp(os.path.getmtime("results/final/cache_v3_main.json")).strftime("%Y-%m-%d %H:%M:%S")
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST")
L = []
A = L.append
A(f"# TierRoute project status (generated {now})\n")
A("No report text here: verdicts, facts and open items only.\n")
A("## VERDICT\n")
A("* **Software complete: yes** (caveats in 'Open problems': strong-tier routing in the live app not re-verified after the last config change; Docker image build untested; Jev verifier not implemented, it was optional).")
A("* **Safe to start report writing: yes**, for every section that does not need v3 numbers (list below). Sections that need results must wait.")
A("* **Final v3 results available: no.** `results/final/v3_tables.md` does not exist; no v3 number exists. `results/final/RESULTS_FALLBACK.md` holds only v2-audit data.\n")
A("## Checks run in this session (all real, no strong-tier call after the first item's slip)\n")
A("| # | Check | Result |\n|---|---|---|")
A("| 1 | `python -m pytest tests -q` | **46 passed, 0 failed** (includes `tests/test_no_leak.py` guards) |")
A("| 2 | `python scripts/health_check.py` local + mid | local-small OK (Ollama running, `llama3.2:3b` present); hosted-mid OK. **Slip:** my first `--tiers 0,1` run did not skip the strong tier because the skip edit had not applied; one 64-token ping (about 120 tokens) reached hosted-strong and returned OK. The script was then fixed and verified with a mock that raises if tier 2 is called (tiers called: [0, 1]). |")
A("| 3 | Live smoke test, local + mid only, `results/final/smoke_live_partial.txt` | 5 of 5 run cases behaved as intended: easy -> local; medium -> hosted-mid; multi-part (3 easy parts) -> all local; forced escalation `local-small [judge_conf=0.00] -> hosted-mid (ok)`; user override -> hosted-mid; admin rule translation -> hosted-mid. **Skipped (need hosted-strong):** the hard prompt and the override to hosted-strong. Guard used: server on :8001 with hosted-strong's base_url pointed at a closed local port. |")
A("| 4 | Secrets | `.env` is git-ignored (`.gitignore:13`) and untracked; never added in any of the 10 commits; `.env.example` exists and is tracked; the key prefix `gsk_` and the exact key value appear in 0 working-tree files (excluding `.env`) and 0 files in all git history. |")
A("| 5 | `.\\run_dashboard.bat` | Server starts; `GET /` -> 200 (10,718 bytes, title `TierRoute`), `/api/models` -> 200, `/api/stats` -> 200, about 6 s after launch. In PowerShell the leading `.\\` is required (QUICKSTART/README corrected). |")
A("| 6 | v3 run status | see section below |")
A("| 7 | Checklist counts | see section below |\n")
A("## Git working tree\n")
A("Uncommitted at the time of writing: `results/final/cache_v3_main.json` and `results/final/problems.log` (written continuously by the running v3 job; intentionally not committed mid-run), plus this session's edits (`scripts/health_check.py`, `scripts/smoke_test.py`, `QUICKSTART.md`, `README.md`) and new files (`results/final/smoke_live_partial.txt`, `dashboard_bat*.log`, `uvicorn_guard.log`, this file). Code edits are committed after this file is written; the two job files stay uncommitted.\n")
A("## v3 run status (from files only)\n")
A("| item | value |\n|---|---|")
A(f"| process | `python benchmark/run_final.py` alive, PID 16548, started 2026-10-17 19:57:47 |")
A(f"| cached calls `results/final/cache_v3_main.json` | {len(cache)} entries, last modified {mt} |")
A("| of which | 31 of the 60 strong-tier (low effort) drafts for `always_strong`; 0 local, 0 mid, 0 judge entries yet |")
A("| `cache_v3_default.json` (always_strong 4096/default baseline) | not created yet (0 of 60) |")
A("| `results/final/run_final.log` | 0 bytes (output only at the end) |")
A("| `results/final/v3_tables.md`, `v3_rows.csv` | do not exist |")
A("| last `problems.log` lines | 20:37-20:47 IST: `tier 2 call failed (attempt 1): HTTP 429: Rate limit exceeded after 4 attempts` roughly every 2 minutes |")
A("| cause | Groq `openai/gpt-oss-120b` free tier: 200,000 tokens per rolling 24 h (response text: `Used 199720` at 20:14 IST) |")
A("| rate observed | cache grew 14 -> 31 entries between 20:18 and 20:48 (about 0.6 strong calls per minute) |")
A("| remaining strong-tier calls | 29 (low) + 60 (default baseline) = 89; local and mid calls are not limited |")
A("| **ESTIMATE (not a measurement)** | If the current trickle rate holds, about 89 calls / 0.6 per minute is roughly 2.5 hours; the rate is set by when earlier Groq usage ages past 24 h, so it may be slower. The large audit batch (Oct 17 about 14:00-16:30 IST) frees from about Oct 18 14:00 IST. Plan for completion between tonight and the afternoon of Oct 18, and do not rely on it. |\n")
A("## What can be written now vs what must wait\n")
A("**Can be written now (no v3 numbers needed):** front page; 1 Introduction (1.1-1.4); 2 Topic overview (2.1-2.4); 3 Application/API (3.1-3.5, facts below); 4 Model/architecture study (4.1-4.6; diagram `results/final/architecture.mmd`); 5 Dataset and preprocessing (5.1-5.5; `results/final/dataset_composition.md`, `v3_validation.md`); 6 Implementation methodology (6.1-6.5); 8.3 challenges and 8.4 dataset quality (from `results/v2_audit/AUDIT.md`); 9.2 learnings and 9.4 future work (the leaked-escalation lesson); 10 references; all PPT slides except results ones.")
A("**Must wait for v3 numbers:** 7.1 metrics, 7.2 figures (`scripts/make_figures.py` after `v3_rows.csv`), 7.3-7.5 analysis and comparison, 8.1 interpretation, 8.2 strengths/weaknesses with numbers, 9.1 summary of results, the Results slide(s). Until then use only labelled v2-audit numbers from `results/final/RESULTS_FALLBACK.md`.\n")
A("## Checklist counts (`docs/aat_requirements/CHECKLIST.md`, tables B-E)\n")
A(f"{len(rows)} status-bearing rows: **done {cnt.get('done', 0)}, partial {cnt.get('partial', 0)}, missing {cnt.get('missing', 0)}, ambiguous {cnt.get('ambiguous', 0)}**. Ten faculty questions (Q1-Q10) are listed in section A of that file.\n")
A("### Open items (every row not 'done')\n")
A("| section | item | status | action needed |\n|---|---|---|---|")
for r in rows:
    if r["base"] != "done":
        A(f"| {r['section'].split('.')[0]} | {r['item']} | {r['status']} | {r['action']} |")
A("")
A("## Facts sheet (facts only)\n")
A("### Models, tiers, prices (`config/models.yaml`, USD per 1M tokens)\n")
A("| tier | name | model id | endpoint | in | out |\n|---|---|---|---|---|---|")
for m in cfg.models:
    A(f"| {m.tier} | {m.name} | `{m.model}` | {m.base_url} | {m.price_in_per_m} | {m.price_out_per_m} |")
A(f"\nDefault quality bias {cfg.default_bias}; mode `{cfg.mode}`; configured verifier `{cfg.verifier}` (chosen on v2 DEV, `results/final/verifier_selection.md`). Cost per call = (tokens_in x price_in + tokens_out x price_out) / 1,000,000.\n")
A("### Components\n")
A("| component | file |\n|---|---|")
for a, b in [("Gateway/API + dashboard host", "app.py"), ("Dashboard UI", "static/index.html"), ("Router core (override, split, choose, ladder, merge, log)", "tierroute/router.py"),
             ("Strategies (choose_first_tier, run_ladder)", "tierroute/strategies.py"), ("Verifiers: heuristic, strict-format, self-consistency, LLM-judge", "tierroute/verifiers.py"),
             ("Original heuristic check", "tierroute/verifier.py"), ("Answer/example extraction helpers", "tierroute/answers.py"),
             ("Rule analyzer (task type, complexity score)", "tierroute/analyzer.py"), ("Request splitter", "tierroute/splitter.py"), ("Merger", "tierroute/merger.py"),
             ("Classifier v1 (used by the live app)", "tierroute/classifier.py"), ("Classifier v2 (used by the benchmark)", "tierroute/classifier_v2.py"),
             ("Provider (OpenAI-compatible HTTP, retries on 429)", "tierroute/providers.py"), ("Config/prices loader", "tierroute/config.py"), ("Decision log (SQLite)", "tierroute/store.py"),
             ("Graders (evaluation only)", "evaluation/grading_v2.py, evaluation/grading_robust.py"), ("No-leak tests", "tests/test_no_leak.py"),
             ("Cached live access + patient retry", "benchmark/live_ctx.py"), ("Strategy evaluation core", "benchmark/run_eval.py"), ("DEV verifier selection", "benchmark/select_verifier.py"),
             ("Final v3 evaluation", "benchmark/run_final.py"), ("Stats (Wilson, paired bootstrap)", "benchmark/stats.py"), ("v3 builder / validator", "benchmark/build_v3.py, benchmark/validate_v3.py"),
             ("Health check / smoke test / figures", "scripts/health_check.py, scripts/smoke_test.py, scripts/make_figures.py"), ("Architecture diagram (current)", "results/final/architecture.mmd"),
             ("Audit of earlier results", "results/v2_audit/AUDIT.md")]:
    A(f"| {a} | `{b}` |")
A("\n### Endpoints (`app.py`)\n")
A("`GET /` dashboard; `POST /api/route` (prompt, bias, force_model, split, strategy, verifier); `POST /v1/chat/completions` (OpenAI-compatible; strategy `rules`); `GET /api/models`; `GET /api/logs`; `GET /api/stats`; `GET|POST /api/overrides` (global_pin, task_rules, bias); `POST /api/reset`.\n")
A("### Strategies and settings\n")
A("always_strong, always_cheap, random (seed 42), cascade (start tier 0), rules (thresholds 0.50 / 0.74 in benchmark; 0.14 / 0.32 in the live app, shifted by (bias - 0.5) x 0.5), classifier (TF-IDF word 1-2 grams, max 1,500 features, LogisticRegression C=2.0, class_weight balanced). "
  f"Classifier v2 training data: {len(SEED_TRAINING_DATA)} seed prompts + 60 v2 DEV prompts with oracle-tier labels. Benchmark hosted calls: temperature 0, max_tokens 4096, reasoning_effort low; local max_tokens 1024. Bias sweep: 0, 0.25, 0.5, 0.75, 1.0.\n")
A("### Datasets, sources, licences, splits\n")
A("| set | dataset | source | licence | tasks |\n|---|---|---|---|---|")
A("| v2 DEV / v2 TEST (60 + 60) | GSM8K, ARC-Challenge, MBPP, HumanEval, MessyExtraction-v2 | public benchmarks + hand-written extraction (source URLs for v2 are not recorded in the repo; sample ids are in `benchmark/tasks_v2.json`) | MIT, CC BY-SA 4.0, CC-BY-4.0, MIT, CC0-1.0 | 17 / 17 / 8 / 8 / 10 per split |")
A("| v3 TEST (60, frozen, SHA-256 `4a5af81ef68c2003bd4f85978f09af00cb03297c08489d8cad2733282026606c`) | GSM8K (`openai/gsm8k`), ARC-Challenge (`allenai/ai2_arc`), MBPP (`google-research-datasets/mbpp`), HumanEval (`openai/openai_humaneval`) via HuggingFace datasets-server; MessyExtraction-v3 hand-written | seed 7, excludes all v2 ids | MIT, CC BY-SA 4.0, CC-BY-4.0, MIT, CC0-1.0 | 17 / 17 / 8 / 8 / 10 |")
A("\nv3 MBPP prompts include one example assert (function name known). Graders: numeric, multiple choice, code unit tests (subprocess, 5 s timeout), normalised extraction. v3 passed a near-duplicate check (SequenceMatcher >= 0.80) against seeds, v2 DEV and all v2; 60/60 reference solutions pass their own graders (`results/final/v3_validation.md`).\n")
A("### Metric definitions\n")
A("* Quality = number of tasks whose final answer passes the grader, out of 60 (original grader: strict; robust grader: extraction tasks only, strips markdown emphasis, normalises Unicode spaces, hyphens, quotes). Wilson 95% interval on the proportion.")
A("* Cost = sum over all attempts (and verifier model calls) of the per-call formula above; $/1000 requests = total / 60 x 1000.")
A("* Saving vs baseline = 1 - cost(strategy) / cost(baseline); baselines always_strong (4096 low) and always_strong (4096 default).")
A("* Paired bootstrap 95% CI = 10,000 resamples of the 60 tasks, seed 7, percentile interval.")
A("* Escalations = tasks that used more than one attempt; workload = final model per task; latency = sum of attempt latencies (mean and median).")
A("* Oracle = per task, the cheapest tier whose answer passes; unsolved tasks go to the cheapest tier. 'Previous oracle' (v2) sent unsolved tasks to the strong tier.")
A("* Exclusion view = results restricted to tasks that at least one tier solves.\n")
A("## Open problems and limitations (all known)\n")
for t in [
    "v3 run incomplete (strong-tier daily token cap); no v3 numbers. Expected completion: see estimate above.",
    "Deadline conflict: course plan says 18 October 2026, not Oct 30 (Q1 in CHECKLIST.md).",
    "The live app and the benchmark use different routing components: the app's `rules` uses thresholds 0.14/0.32 and the `classifier` strategy uses classifier v1 (`tierroute/classifier.py`), while the benchmark uses thresholds 0.50/0.74 and classifier v2. The benchmark therefore evaluates the benchmark configuration, not the exact live-app routing for those two strategies.",
    "Strong-tier routing in the live app was not re-verified after the defaults changed to max_tokens 4096 + reasoning_effort low (it would use the capped token budget). Earlier live runs showed rate-limit and truncation failures on the strong tier (`results/final/smoke_live.txt`, `smoke_live_run1_contended.txt`).",
    "LLM-judge verifier adds a mid-model call per local draft: in the live smoke run the total cost of several short requests was higher than the all-strong estimate (cases 1, 3 and 4 in `smoke_live_partial.txt`: e.g. case 1 total $0.000041 vs all-strong estimate $0.000008). On the v2 DEV set the selected judge saved 31.6% on average (`verifier_selection.md`), far less than the heuristic verifiers; threshold values 0.5-0.9 made almost no difference.",
    "With the judge verifier an answer 'I'm not sure' is accepted when the prompt asks for those words (judge rates instruction-following, not uncertainty); the heuristic verifier rejects it.",
    "Jev verifier (option e) not run/implemented: no `OPENROUTER_API_KEY`; health check lists it as skipped.",
    "Docker: Docker Desktop engine was not running, so the image was never built; `docker compose config` validates. Compose points the gateway at the `local-ollama` container; the model must be pulled inside it.",
    "Single sample per task and tier; Groq output varies between runs at temperature 0; n = 60; differences of 1-2 tasks are noise.",
    "v2 TEST tasks were visible during development; only v3 is a fresh held-out set. The 8 MBPP v2 TEST tasks have NameError issues at one or more tiers (prompts omit the function name); v3 fixes this by including one example assert.",
    "Self-consistency is not evaluated beyond DEV; code samples are compared by AST equality (almost always disagree).",
    "Strict-format code check runs only example asserts found in the prompt (subprocess + timeout, no memory/filesystem sandbox).",
    "Local tier cost is counted as $0 (electricity/hardware ignored); local latency depends on the laptop GPU.",
    "`results/report_pack/` (v1) contains stale material: the architecture diagram names old models/prices/thresholds; `test_cases.md` mentions gold-label checks from the v1 benchmark. Older results are indexed in `results/README.md` (several invalid).",
    "Prices were recorded as verified on 2026-10-16 in `config/models.yaml`; Groq pricing may change.",
    "Documentation fix made this session: PowerShell needs `.\\run_dashboard.bat` (docs corrected).",
    "No figures for the final run exist yet (`scripts/make_figures.py` needs `v3_rows.csv`); screenshots S1-S11 in `docs/aat_requirements/EVIDENCE_PACK.md` must be taken by hand.",
    "Students' personal details (names, USNs, section) and all report/PPT prose are not in the repo (by design).",
]:
    A(f"* {t}")
open("results/final/PROJECT_STATUS.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("written", len(L))
