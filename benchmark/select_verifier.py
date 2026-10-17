"""Phase 2: choose the escalation verifier (and its threshold) on the v2 DEV set ONLY.

Selection rule (fixed before any DEV run): over the three escalating routers (cascade, rules, classifier) take the mean
DEV quality under the formatting-robust grader. A candidate is feasible if its mean router cost is <= 80% of the
always_strong cost on DEV (>= 20% saving). Pick the feasible candidate with the highest mean quality; ties -> lowest
mean cost. The classifier is evaluated with 5-fold cross-validation on DEV (trained on seeds + the other 4 folds) so it
is never scored on tasks it was trained on. The v2 TEST split and v3 are not touched here.
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmark.live_ctx import CachedLive  # noqa: E402
from benchmark.run_eval import evaluate, summarize  # noqa: E402
from tierroute.classifier import SEED_TRAINING_DATA  # noqa: E402
from tierroute.classifier_v2 import ComplexityClassifierV2  # noqa: E402
from tierroute.config import load_config  # noqa: E402
from tierroute.verifiers import (HeuristicVerifier, JudgeVerifier, SelfConsistencyVerifier,  # noqa: E402
                                 StrictFormatVerifier)

OUT = Path("results/final")
OUT.mkdir(parents=True, exist_ok=True)
cfg = load_config()
tasks = {t["id"]: t for t in json.load(open("benchmark/tasks_v2.json", encoding="utf-8"))}
dev_ids = json.load(open("benchmark/split_v2.json"))["dev_ids"]
dev = [tasks[i] for i in dev_ids]
prof = json.load(open("results/benchmark_v2_dev_profile.json", encoding="utf-8"))
assert set(prof) == set(dev_ids)

live = CachedLive(cfg, OUT / "cache_dev.json", hosted_max_tokens=4096, hosted_extra={"reasoning_effort": "low"})
ctx = live.ctx()


class FoldClassifier:
    """Out-of-fold predictions: each DEV prompt is scored by a model that did not train on it."""

    def __init__(self, k=5, seed=7):
        ids = list(dev_ids)
        random.Random(seed).shuffle(ids)
        self.pred = {}
        for f in range(k):
            held = set(ids[f::k])
            tr = [(prof[i]["prompt"], prof[i]["oracle_tier"]) for i in dev_ids if i not in held]
            texts = [x[0] for x in SEED_TRAINING_DATA] + [p for p, _ in tr]
            labels = [x[1] for x in SEED_TRAINING_DATA] + [l for _, l in tr]
            c = ComplexityClassifierV2()
            c.pipeline.fit(texts, labels)
            c.is_trained = True
            for i in held:
                self.pred[prof[i]["prompt"]] = c.predict(prof[i]["prompt"], bias=0.5)

    def predict(self, prompt, bias=0.5):
        return self.pred[prompt]


clf = FoldClassifier()
CANDS = [("heuristic", HeuristicVerifier(), {}), ("strict", StrictFormatVerifier(), {}),
         ("self_consistency", SelfConsistencyVerifier(min_agree=2), {"min_agree": 2}),
         ("self_consistency", SelfConsistencyVerifier(min_agree=3), {"min_agree": 3})]
CANDS += [("judge", JudgeVerifier(threshold=t), {"threshold": t}) for t in (0.5, 0.6, 0.7, 0.8, 0.9)]

t0 = time.time()
strong = summarize(evaluate(dev, "always_strong", None, ctx))
base = {s: summarize(evaluate(dev, s, None, ctx, classifier=clf)) for s in ("always_cheap", "random")}
print("always_strong", strong, flush=True)
results = []
for name, ver, params in CANDS:
    per = {}
    for s in ("cascade", "rules", "classifier"):
        per[s] = summarize(evaluate(dev, s, ver, ctx, classifier=clf))
        per[s]["quality_orig"] = summarize(evaluate(dev, s, ver, ctx, classifier=clf), "correct_orig")["quality"]
    mq = sum(p["quality"] for p in per.values()) / 3
    mc = sum(p["cost"] for p in per.values()) / 3
    row = dict(verifier=name, params=params, mean_quality=mq, mean_cost=mc, feasible=mc <= 0.8 * strong["cost"],
               mean_escalations=sum(p["escalations"] for p in per.values()) / 3,
               mean_latency=sum(p["mean_latency"] for p in per.values()) / 3, per_router=per)
    results.append(row)
    print(f"{name} {params}: Q={mq:.2f}/60 cost=${mc:.6f} (strong ${strong['cost']:.6f}) esc={row['mean_escalations']:.1f} "
          f"feasible={row['feasible']}", flush=True)

feas = [r for r in results if r["feasible"]] or results
best = sorted(feas, key=lambda r: (-r["mean_quality"], r["mean_cost"]))[0]
json.dump(dict(always_strong=strong, baselines=base, candidates=results, selected=dict(verifier=best["verifier"], params=best["params"])),
          open(OUT / "dev_verifier_results.json", "w"), indent=1)
json.dump(dict(verifier=best["verifier"], params=best["params"]), open(OUT / "selected_verifier.json", "w"))

L = ["# Verifier selection (v2 DEV set only, 60 tasks)", "",
     "Rule fixed before running: maximise mean DEV quality (formatting-robust grader) over the cascade, rules and "
     "classifier routers, subject to mean router cost <= 80% of DEV always_strong cost; ties -> lowest cost. "
     "Classifier scored with 5-fold cross-validation on DEV. Hosted calls: max_tokens=4096, reasoning_effort=low; "
     "local: max_tokens=1024. Test split and v3 were not used.", "",
     f"always_strong on DEV: {strong['quality']}/60 (robust grader), cost ${strong['cost']:.6f}, mean latency {strong['mean_latency']:.2f}s. "
     f"always_cheap: {base['always_cheap']['quality']}/60; random: {base['random']['quality']}/60.", "",
     "| verifier | params | mean quality /60 | mean cost $ | saving vs strong | mean escalations | mean latency s | feasible |",
     "|---|---|---|---|---|---|---|---|"]
for r in results:
    L.append(f"| {r['verifier']} | {r['params']} | {r['mean_quality']:.2f} | {r['mean_cost']:.6f} | "
             f"{100 * (1 - r['mean_cost'] / strong['cost']):.1f}% | {r['mean_escalations']:.1f} | {r['mean_latency']:.2f} | {r['feasible']} |")
L += ["", "Per-router DEV detail (quality robust / original, cost, escalations):", "",
      "| verifier | params | cascade | rules | classifier(CV) |", "|---|---|---|---|---|"]
for r in results:
    cells = [f"{r['per_router'][s]['quality']}/{r['per_router'][s]['quality_orig']}, ${r['per_router'][s]['cost']:.5f}, {r['per_router'][s]['escalations']} esc" for s in ("cascade", "rules", "classifier")]
    L.append(f"| {r['verifier']} | {r['params']} | " + " | ".join(cells) + " |")
L += ["", f"**Selected: `{best['verifier']}` {best['params']}**", "",
      "Option (e), Jev (OpenRouter `typesafe/jev-1.13`, Decisions API): **not run** - no `OPENROUTER_API_KEY` is configured, "
      "so the optional flag-gated verifier was skipped.", "",
      f"Live API calls made in this stage: {live.live_calls}; wall time {time.time() - t0:.0f}s."]
(OUT / "verifier_selection.md").write_text("\n".join(L), encoding="utf-8")
print("selected", best["verifier"], best["params"])
