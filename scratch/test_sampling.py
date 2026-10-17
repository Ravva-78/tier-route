import csv
import json
import random
from pathlib import Path

ROOT = Path(".")
tasks = json.load(open(ROOT / "benchmark" / "tasks.json", encoding="utf-8"))
task_map = {}
for t in tasks:
    if "parts" in t:
        for i, p in enumerate(t["parts"]):
            task_map[f"{t['id']}_p{i}"] = (p["tier"], p["prompt"], p["answer"], p["check"])
    else:
        task_map[t["id"]] = (t["tier"], t["prompt"], t["answer"], t["check"])

raw_rows = list(csv.DictReader(open(ROOT / "results" / "benchmark_live_raw.csv", encoding="utf-8")))
cheap_rows = [r for r in raw_rows if r["strategy"] == "always_cheap"]

by_tier = {0: [], 1: [], 2: []}
for r in cheap_rows:
    tier = int(r["gold_tier"])
    by_tier[tier].append(r)

print("Counts by tier in always_cheap:", {k: len(v) for k, v in by_tier.items()})

# Fixed seed 42 sampling
rng = random.Random(42)
# Sample 5 from tier 0, 5 from tier 1, 5 from tier 2 (total 15, exactly 5 tier-2)
sample_t0 = rng.sample(by_tier[0], 5)
sample_t1 = rng.sample(by_tier[1], 5)
sample_t2 = rng.sample(by_tier[2], 5)

sample_15 = sample_t0 + sample_t1 + sample_t2
print("\nSampled 15 tasks (seed=42):")
for r in sample_15:
    tid = r["task_id"]
    tier, prompt, gold, check_spec = task_map[tid]
    print(f"Task: {tid:6} | Tier: {tier} | AutoCheck: {r['correct']} | Prompt: {prompt[:40]}... | Ans: {r['answer'][:30]}")
