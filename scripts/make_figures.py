#!/usr/bin/env python3
"""Figures for the report/PPT, drawn ONLY from real result files (run after benchmark/run_final.py).
Writes PNGs to results/final/figures/. Inputs: results/final/v3_rows.csv, results/final/dev_verifier_results.json."""
import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("results/final/figures")
OUT.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(open("results/final/v3_rows.csv", encoding="utf-8")))
for r in rows:
    for k in ("cost", "latency_s", "correct_orig", "correct_robust", "first_tier", "final_tier", "bias"):
        r[k] = float(r[k])


def pick(strategy, run="main", bias=0.5):
    return [r for r in rows if r["strategy"] == strategy and r["run"] == run and r["bias"] == bias]


names = ["always_strong", "always_strong_4096_default", "always_cheap", "random", "cascade", "rules", "classifier",
         "oracle_robust"]
# 1. cost vs quality
fig, ax = plt.subplots(figsize=(7, 4.5))
for s in names:
    rs = pick(s)
    ax.scatter(sum(r["cost"] for r in rs), sum(r["correct_robust"] for r in rs), s=60)
    ax.annotate(s, (sum(r["cost"] for r in rs), sum(r["correct_robust"] for r in rs)), fontsize=7, xytext=(4, 4),
                textcoords="offset points")
ax.set_xlabel("total cost on 60 v3 tasks (USD)")
ax.set_ylabel("correct /60 (formatting-robust grader)")
ax.set_title("Quality vs cost, v3 held-out set")
fig.tight_layout()
fig.savefig(OUT / "cost_quality.png", dpi=200)

# 2. bias sweep
fig, ax = plt.subplots(figsize=(7, 4.5))
for s in ("rules", "classifier"):
    pts = []
    for b in (0.0, 0.25, 0.5, 0.75, 1.0):
        rs = pick(s, "main", 0.5) if b == 0.5 else pick(s, "sweep", b)
        pts.append((sum(r["cost"] for r in rs), sum(r["correct_robust"] for r in rs), b))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=s)
    for c, q, b in pts:
        ax.annotate(f"b={b}", (c, q), fontsize=7, xytext=(3, 3), textcoords="offset points")
ax.set_xlabel("total cost (USD)")
ax.set_ylabel("correct /60 (robust grader)")
ax.set_title("Bias sweep")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "bias_sweep.png", dpi=200)

# 3. classifier first tier vs oracle tier (confusion matrix; oracle = cheapest passing tier, robust grader)
orc = {r["task_id"]: int(r["final_tier"]) for r in pick("oracle_robust")}
cm = Counter((int(r["first_tier"]), orc[r["task_id"]]) for r in pick("classifier"))
fig, ax = plt.subplots(figsize=(4.5, 4))
mat = [[cm[(p, o)] for o in (0, 1, 2)] for p in (0, 1, 2)]
ax.imshow(mat, cmap="Blues")
for i in range(3):
    for j in range(3):
        ax.text(j, i, mat[i][j], ha="center", va="center")
ax.set_xticks(range(3))
ax.set_yticks(range(3))
ax.set_xlabel("oracle tier (cheapest passing; unsolved -> cheapest)")
ax.set_ylabel("classifier first tier")
ax.set_title("Router first-tier vs oracle (v3)")
fig.tight_layout()
fig.savefig(OUT / "classifier_confusion.png", dpi=200)

# 4. DEV verifier comparison
dev = json.load(open("results/final/dev_verifier_results.json", encoding="utf-8"))
labels = [f"{c['verifier']}\n{c['params'] or ''}" for c in dev["candidates"]]
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.bar(range(len(labels)), [c["mean_quality"] for c in dev["candidates"]])
ax.axhline(dev["always_strong"]["quality"], color="r", ls="--", label="always_strong (DEV)")
ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels, fontsize=6)
ax.set_ylabel("mean DEV quality /60 (3 routers)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "dev_verifiers.png", dpi=200)
print("wrote", sorted(p.name for p in OUT.glob("*.png")))
