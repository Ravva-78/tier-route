"""Generates results/final/RESULTS_FALLBACK.md from real files only:
results/v2_audit/tables.md (replay of real responses), results/benchmark_v2_dev_profile.json, config/models.yaml."""
import collections
import json
import re
import sys

sys.path.insert(0, ".")
from tierroute.config import load_config

cfg = load_config()
T = open("results/v2_audit/tables.md", encoding="utf-8").read()


def section(prefix):
    m = re.search(r"#### " + re.escape(prefix) + r".*?(?=\n#### |\Z)", T, re.S)
    return m.group(0).replace("#### ", "##### ", 1).strip()


def rows(prefix, keep):
    lines = section(prefix).splitlines()  # title, blank, header, separator, body...
    body = [l for l in lines[4:] if any(k in l for k in keep)]
    return "\n".join(lines[:4] + body)


KEEP = ("always_strong", "always_cheap", "| random", "| cascade | leaky", "| cascade | deploy", "| rules | leaky",
        "| rules | deploy", "| classifier | leaky", "| classifier | deploy", "ORACLE[orig-pass]")
prof = json.load(open("results/benchmark_v2_dev_profile.json", encoding="utf-8"))
dist = collections.Counter(int(v["oracle_tier"]) for v in prof.values())
by_ds = collections.Counter((v["dataset"], int(v["oracle_tier"])) for v in prof.values())
passed = collections.Counter()
for v in prof.values():
    for m, r in v["models"].items():
        passed[m] += bool(r["ok"])

L = []
A = L.append
A("# TierRoute fallback results (v2 audit data only)\n")
A("> **The v3 run is INCOMPLETE. No v3 numbers exist.** `benchmark/run_final.py` has not finished (Groq `openai/gpt-oss-120b` free tier: 200,000 tokens per rolling 24 h; the run is waiting and retrying). Nothing in this file comes from v3. Nothing was estimated or filled in: every number below is copied or recomputed from `results/v2_audit/` (replay of real model responses with a gold-free verifier), `results/benchmark_v2_dev_profile.json` and `config/models.yaml`.\n")
A("## Findings\n")
A("1. The earlier v2 router results were leaked: routers escalated on `grade_task_v2` (gold answers and unit tests). Replayed with a gold-free verifier, router quality is far below the published 48/60 (Table 2).")
A("2. The deployable-verifier routers are cheap mainly because they accept wrong answers: the verifier accepts most wrong answers from the local and mid tiers (Table 4). Those cost savings are not free savings.")
A("3. A true cost-minimising oracle (unsolved tasks go to the cheapest tier) costs far less than the earlier oracle (Table 3), because the earlier one paid the strong tier for tasks no model solves.")
A("4. Everything is a single sample per (task, tier, config) on 60 tasks (52 after excluding the MBPP NameError tasks). Differences of 1-2 tasks are within run-to-run noise; no confidence intervals are computed in this fallback.\n")
A("## Prices (config/models.yaml, USD per 1M tokens) and how costs are computed\n")
A("| model | in | out |\n|---|---|---|")
for m in cfg.models:
    A(f"| {m.name} (`{m.model}`) | {m.price_in_per_m} | {m.price_out_per_m} |")
A("\nCost of one call = (tokens_in x price_in + tokens_out x price_out) / 1,000,000, with the token counts returned by the API. `results/v2_audit/analyze.py` computes every cost below through `ModelSpec.cost` from `tierroute/config.py`, which reads exactly these prices. The audit verifier makes no extra model calls, so no verifier cost is added.\n")
A("## Table 1 - Configurations (hosted calls identical within a configuration)\n")
A("| config | hosted max_tokens | hosted reasoning_effort | source of responses |\n|---|---|---|---|")
A("| A_1024_default | 1024 | default | original v2 run cache (`results/benchmark_v2_call_cache.json`) |")
A("| B_4096_default | 4096 | default | live audit calls (`results/v2_audit/responses_B_4096_default.json`) |")
A("| C_4096_low | 4096 | low | live audit calls (`results/v2_audit/responses_C_4096_low.json`) |")
A("\nThe local tier (Ollama `llama3.2:3b`, 1024 tokens) is the same cached response set in all three. Task set: v2 TEST (60 tasks).\n")
A("## Table 2 - Deployable-verifier results on the v2 TEST tasks (rows copied from `results/v2_audit/tables.md`)\n")
A("Escalation signal `leaky` = the original grader (gold + unit tests); shown only to reproduce the invalid published numbers. `deploy` = the gold-free verifier in `results/v2_audit/audit_lib.py` (empty output, `finish_reason=length`, uncertainty phrase, Python parse failure, missing `Answer:` format). Quality is given under the original grader and the formatting-robust grader (they differ only on extraction tasks). Saving is vs `always_strong` in the same configuration.\n")
for t in ("A_1024_default - all 60", "B_4096_default - all 60", "C_4096_low - all 60", "A_1024_default - 52", "C_4096_low - 52"):
    A(rows(t, KEEP) + "\n")
A("Complete tables for every configuration and subset, including both oracle definitions under the robust grader, are in `results/v2_audit/tables.md` and `results/v2_audit/AUDIT.md`.\n")
A("## Table 3 - Oracles (config A, 60 tasks, from `results/v2_audit/tables.md`)\n")
A("| oracle | quality (orig grader) | cost $ | saving vs always_strong | workload L/M/S |\n|---|---|---|---|---|")
for l in section("A_1024_default - all 60").splitlines():
    if l.startswith("| ORACLE[orig-pass]"):
        c = [x.strip() for x in l.strip("|").split("|")]
        A(f"| {c[0].replace('ORACLE[orig-pass] ', '')} | {c[2]} | {c[4]} | {c[5]} | {c[7]} |")
A("\nThe earlier oracle sends tasks that no model solves to the strong tier. The true cost-minimising oracle sends them to the cheapest tier and, for solved tasks, picks the cheapest passing tier. Both are post-hoc (they use the test outputs), so neither is deployable.\n")
A("## Table 4 - How well the gold-free verifier catches wrong answers (from `results/v2_audit/tables.md`)\n")
A("\n".join(section("Verifier vs original grader").splitlines()[1:]))
A("\n`pass & WRONG` = the verifier accepted an answer the grader marks wrong (a missed error).\n")
A("## Table 5 - Escalations vs under-routed (config A)\n")
A("\n".join(section("Escalations vs under-routed").splitlines()[1:]))
A("\n## Table 6 - v2 DEV profile (`results/benchmark_v2_dev_profile.json`: 60 DEV tasks, 1024 tokens, default effort)\n")
A("Per-model outcomes on the DEV tasks and the oracle tier used as classifier training labels (lowest tier that passed the grader; tasks no model solved are labelled tier 2).\n")
A("| oracle tier | tasks |\n|---|---|")
for k in (0, 1, 2):
    A(f"| {k} | {dist[k]} |")
A(f"\n| model | DEV tasks passed (of {len(prof)}) |\n|---|---|")
for m in ("local-small", "hosted-mid", "hosted-strong"):
    A(f"| {m} | {passed[m]} |")
A("\n| dataset | oracle tier 0 | tier 1 | tier 2 |\n|---|---|---|---|")
for d in sorted({k[0] for k in by_ds}):
    A(f"| {d} | {by_ds[(d, 0)]} | {by_ds[(d, 1)]} | {by_ds[(d, 2)]} |")
A("\nThese labels came from the grader on DEV tasks only, which is legitimate as training data; the profile holds 60 DEV ids and no TEST ids (checked in the audit).\n")
A("## Methodology lesson: leaked escalation\n")
A("**What it was.** In the original `scratch/run_benchmark_v2.py`, each router called a model, then called `grade_task_v2(task, output)` and escalated to the next tier whenever the grader said the answer was wrong. That grader compares against the gold answer and runs the task's unit tests, so the router was told after every attempt whether it was right. A real deployment has no such signal.\n")
A("**How it was found.** The published results showed, for all three routers, escalations exactly equal to the number of under-routed tasks and quality exactly equal to the oracle (48/60). That is suspicious because the routers start from very different places. Reading the code showed escalation depended on `grade_task_v2`. Replaying the saved responses confirmed that the escalated task sets equal the under-routed sets exactly (Table 5, `sets identical = True`): both are defined by the same grader on the same outputs. With a gold-free verifier the identity disappears.\n")
A("**How it was fixed.** (1) Graders moved into a separate `evaluation/` package; `tierroute/strategies.py` and `tierroute/verifiers.py` take only the prompt and the model output. (2) `tests/test_no_leak.py` fails if a `tierroute/` module imports grading code or uses gold/test identifiers, and runs every strategy and verifier with the graders replaced by objects that raise when touched. (3) `scratch/run_benchmark_v2.py` was rewritten to escalate only on a gold-free verifier and to grade after routing. (4) Old outputs are labelled invalid in `results/README.md`. (5) A fresh held-out set (v3) was frozen with a SHA-256 before any model saw it. Step 5 is built, but its model run is incomplete.\n")
A("## Limitations\n")
A("* **No v3 results.** Everything here is on the v2 TEST tasks, which were visible during earlier development (thresholds were tuned on DEV and the classifier trains on DEV), so this is not a fresh held-out measurement.")
A("* One real response per (task, tier, config). Groq output is not deterministic at temperature 0 (the audit saw different token counts on 28 of 60 tasks between two runs), so +-1-2 tasks is noise. No confidence intervals here.")
A("* n = 60 (52 after removing the 8 MBPP tasks whose prompts omit the function name and fail with NameError at one or more tiers).")
A("* The audit's gold-free verifier is one fixed design (phrase list reused from `tierroute/verifier.py`; the code check is `ast.parse` only). Other verifiers (self-consistency, LLM judge) were implemented later and are not evaluated in this file.")
A("* Config A responses come from the original 1024-token run; the local tier is reused in all configs; hosted configs differ in token budget and reasoning effort.")
A("* Cost uses API-reported token counts and the yaml prices; the local tier is counted as $0 (electricity and hardware ignored).")
A("* Oracles are post-hoc upper bounds, not deployable systems.")
A("* Earlier reports contain wrong price prose (0.59/0.79) and a wrong truncation count (`results/v2_audit/AUDIT.md`). The Docker image build was not tested (the Docker engine was not running).\n")
A("## Reproduction commands\n")
A("""```bash
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
""")
open("results/final/RESULTS_FALLBACK.md", "w", encoding="utf-8").write("\n".join(L))
print("written")
