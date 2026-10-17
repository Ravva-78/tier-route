"""v2 TEST benchmark, FIXED: no gold/grader/unit-test signal reaches routing or escalation.

The original version of this script escalated on grade_task_v2() (gold answers + unit tests) and is invalid
(see results/v2_audit/AUDIT.md). Here routers escalate only on a gold-free verifier (tierroute/verifiers.py);
grading happens afterwards, for reporting only. Calls use the cached 1024-token/default-effort responses
(results/benchmark_v2_call_cache.json) and go live on cache misses. Outputs go to results/final/ (never over the
old invalid files).
"""
import csv
import json
import os
import random
import sys
import time

sys.path.insert(0, ".")
from tierroute.classifier_v2 import ComplexityClassifierV2
from tierroute.config import load_config
from tierroute.providers import LLMResult, Provider
from tierroute.strategies import run_strategy
from tierroute.verifiers import Ctx, HeuristicVerifier
from evaluation.grading_robust import grade_robust  # evaluation only: used after routing is finished
from evaluation.grading_v2 import grade_task_v2

cfg = load_config()
specs = {m.tier: m for m in cfg.models}
providers = {t: Provider(m, mode="live") for t, m in specs.items()}
clf = ComplexityClassifierV2(auto_train=True)
tasks = {t["id"]: t for t in json.load(open("benchmark/tasks_v2.json", encoding="utf-8"))}
test_ids = json.load(open("benchmark/split_v2.json"))["test_ids"]

CACHE_FILE = "results/benchmark_v2_call_cache.json"
cache = {}
for k, v in json.load(open(CACHE_FILE, encoding="utf-8")).items():
    p, m = k.split("|||", 1)
    cache[(p, m)] = LLMResult(v["text"], v["tokens_in"], v["tokens_out"], v["latency_s"], v.get("error"),
                              v.get("finish_reason", "stop"))


def generate(tier, prompt, sample=0, temperature=0.0, judge=False):
    if sample or judge:
        raise NotImplementedError("heuristic verifier makes no extra calls")
    key = (prompt, specs[tier].name)
    if key not in cache:
        cache[key] = providers[tier].generate(prompt, max_tokens=1024, temperature=0.0)
        time.sleep(0.5)
    return cache[key]


ctx = Ctx(generate, lambda tier, r: specs[tier].cost(r.tokens_in, r.tokens_out))
verifier = HeuristicVerifier()
rows = []
os.makedirs("results/final", exist_ok=True)
for strat in ["always_strong", "always_cheap", "random", "cascade", "rules", "classifier"]:
    rnd = random.Random(42)
    for tid in test_ids:
        t = tasks[tid]
        # routing sees ONLY the prompt
        out = run_strategy(strat, t["prompt"], ctx, verifier, rnd=rnd, classifier=clf)
        text = out.final.res.text
        rows.append(dict(task_id=tid, strategy=strat, first_tier=out.first_tier, final_tier=out.final.tier,
                         escalated=int(out.escalated), cost=out.cost, latency_s=out.latency_s,
                         correct_orig=int(grade_task_v2(t, text)[0]), correct_robust=int(grade_robust(t, text)[0])))
with open("results/final/v2_noleak_raw.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for s in dict.fromkeys(r["strategy"] for r in rows):
    x = [r for r in rows if r["strategy"] == s]
    print(f"{s:14s} orig {sum(r['correct_orig'] for r in x)}/60 robust {sum(r['correct_robust'] for r in x)}/60 "
          f"cost ${sum(r['cost'] for r in x):.6f} escalations {sum(r['escalated'] for r in x)}")
