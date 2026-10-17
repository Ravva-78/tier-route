"""Sanity checks on v3 BEFORE any model sees it: reference solutions pass their own graders, leakage check, hash."""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.grading_v2 import grade_task_v2
from tierroute.classifier import SEED_TRAINING_DATA
from tierroute.classifier_v2 import check_no_leakage_v2

tasks = json.load(open("benchmark/tasks_v3.json", encoding="utf-8"))
sha = hashlib.sha256(Path("benchmark/tasks_v3.json").read_bytes()).hexdigest()
v2 = json.load(open("benchmark/tasks_v2.json", encoding="utf-8"))
prof = json.load(open("results/benchmark_v2_dev_profile.json", encoding="utf-8"))
lines, bad = [], 0
for t in tasks:
    g = t["grader"]["type"]
    if t["dataset"] == "HumanEval":
        resp = "```python\n" + re.search(r"```python\n(.*?)\n```", t["prompt"], re.S).group(1) + "\n" + t["answer"] + "\n```"
    elif g == "code":
        resp = "```python\n" + t["answer"] + "\n```"
    else:
        resp = f"Answer: {t['answer']}"
    ok, why = grade_task_v2(t, resp)
    bad += not ok
    if not ok:
        lines.append(f"- REFERENCE FAILS {t['id']} {t['sample_id']}: {why}")
train = [x[0] for x in SEED_TRAINING_DATA] + [d["prompt"] for d in prof.values()]
check_no_leakage_v2(train, [t["prompt"] for t in tasks], 0.80)           # seeds + v2 DEV (classifier training data)
check_no_leakage_v2([t["prompt"] for t in v2], [t["prompt"] for t in tasks], 0.80)  # all of v2 (dev + test)
v2_ids = {t["sample_id"] for t in v2}
overlap = v2_ids & {t["sample_id"] for t in tasks}
md = ["# v3 pre-run validation (no model was called)", "", f"- file: benchmark/tasks_v3.json, SHA-256 `{sha}`",
      f"- tasks: {len(tasks)}; sample_id overlap with v2: {len(overlap)}",
      f"- reference answers/solutions passing their own grader: {len(tasks) - bad}/{len(tasks)}",
      "- near-duplicate check (SequenceMatcher >= 0.80 after boilerplate stripping) vs classifier training data "
      "(seed set + v2 DEV) and vs all v2 tasks: passed", *lines]
Path("results/final").mkdir(exist_ok=True)
Path("results/final/v3_validation.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md))
assert not bad and not overlap
