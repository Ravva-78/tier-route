import csv
import json
from collections import defaultdict

# Read raw records
rows = []
with open('results/benchmark_v2_raw.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

test_ids = sorted(list(set(r['task_id'] for r in rows)))
print(f"Total unique test task IDs in raw CSV: {len(test_ids)}")

# Track model outcomes per task
# {task_id: {model_name: {'correct': int, 'cost': float, 'latency_s': float, 'grader_info': str, 'finish_reason': str}}}
task_models = defaultdict(dict)
for r in rows:
    tid = r['task_id']
    m = r['final_model']
    # If not yet recorded or if it passed, record
    if m not in task_models[tid] or int(r['correct']) == 1:
        task_models[tid][m] = {
            'correct': int(r['correct']),
            'cost': float(r['cost']),
            'latency_s': float(r['latency_s']),
            'grader_info': r['grader_info'],
            'finish_reason': r['finish_reason']
        }

# Check coverage per task
print("\nModel coverage across 60 test tasks:")
for tid in test_ids[:5]:
    print(f"Task {tid}: models tested = {list(task_models[tid].keys())}")

# Check how many tasks have all 3 models tested
full_cov = sum(1 for tid in test_ids if len(task_models[tid]) == 3)
two_cov = sum(1 for tid in test_ids if len(task_models[tid]) == 2)
one_cov = sum(1 for tid in test_ids if len(task_models[tid]) == 1)
print(f"Tasks with 3 models: {full_cov}, 2 models: {two_cov}, 1 model: {one_cov}")
