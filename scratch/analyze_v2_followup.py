import csv
import json
import math
import sys
import numpy as np
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 1. Load benchmark v2 raw records
raw_rows = []
with open("results/benchmark_v2_raw.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        raw_rows.append(r)

with open("benchmark/tasks_v2.json", "r", encoding="utf-8") as f:
    all_tasks = {t["id"]: t for t in json.load(f)}

with open("benchmark/split_v2.json", "r", encoding="utf-8") as f:
    split_info = json.load(f)

test_ids = split_info["test_ids"]
print(f"Loaded {len(raw_rows)} raw benchmark v2 rows for {len(test_ids)} test tasks.")

# Group records by (strategy, bias)
strat_runs = defaultdict(dict)
for r in raw_rows:
    key = (r["strategy"], float(r["bias"]))
    strat_runs[key][r["task_id"]] = r

# ---------------------------------------------------------
# TASK 2: Oracle Router Row
# For each test task, cheapest model that passed in the existing per-model results.
# ---------------------------------------------------------
task_tested_models = defaultdict(dict)
for r in raw_rows:
    tid = r["task_id"]
    m = r["final_model"]
    # If not recorded or if this call was correct, store
    if m not in task_tested_models[tid] or int(r["correct"]) == 1:
        task_tested_models[tid][m] = {
            "correct": int(r["correct"]),
            "cost": float(r["cost"]),
            "latency_s": float(r["latency_s"]),
            "grader_info": r["grader_info"],
            "finish_reason": r["finish_reason"]
        }

oracle_records = []
tier_order = ["local-small", "hosted-mid", "hosted-strong"]
for tid in test_ids:
    models_dict = task_tested_models[tid]
    # Find cheapest model that passed
    passed_models = [m for m in tier_order if m in models_dict and models_dict[m]["correct"] == 1]
    if passed_models:
        chosen_m = passed_models[0]
        chosen_data = models_dict[chosen_m]
        oracle_records.append({
            "task_id": tid,
            "chosen_model": chosen_m,
            "correct": 1,
            "cost": chosen_data["cost"],
            "latency_s": chosen_data["latency_s"]
        })
    else:
        # None passed in tested models
        # For cost/latency, take strong model (or local if strong not tested)
        chosen_m = "hosted-strong" if "hosted-strong" in models_dict else list(models_dict.keys())[0]
        chosen_data = models_dict[chosen_m]
        oracle_records.append({
            "task_id": tid,
            "chosen_model": chosen_m,
            "correct": 0,
            "cost": chosen_data["cost"],
            "latency_s": chosen_data["latency_s"]
        })

oracle_k = sum(r["correct"] for r in oracle_records)
oracle_n = len(oracle_records)
oracle_cost = sum(r["cost"] for r in oracle_records)
oracle_lat = sum(r["latency_s"] for r in oracle_records) / oracle_n

strong_rows = [strat_runs[("always_strong", 0.5)][tid] for tid in test_ids]
strong_cost = sum(float(r["cost"]) for r in strong_rows)
oracle_saving = 100.0 * (1.0 - oracle_cost / strong_cost)

print("\n=== TASK 2: ORACLE ROUTER (UPPER BOUND) ===")
print(f"Oracle Quality: {oracle_k}/{oracle_n} ({oracle_k/oracle_n*100:.1f}%)")
print(f"Oracle Cost: ${oracle_cost:.6f} ({oracle_saving:.1f}% saving vs always_strong)")
print(f"Oracle Mean Latency: {oracle_lat:.2f}s")
oracle_models = defaultdict(int)
for r in oracle_records:
    if r["correct"] == 1:
        oracle_models[r["chosen_model"]] += 1
    else:
        oracle_models["unsolved"] += 1
print(f"Oracle Workload Breakdown: {dict(oracle_models)}")

# ---------------------------------------------------------
# TASK 3: Paired Comparisons
# ---------------------------------------------------------
print("\n=== TASK 3: PAIRED COMPARISON (always_strong vs classifier) ===")
strong_vs_clf_discordant = []
for tid in test_ids:
    s_rec = strat_runs[("always_strong", 0.5)][tid]
    c_rec = strat_runs[("classifier", 0.5)][tid]
    s_corr = int(s_rec["correct"])
    c_corr = int(c_rec["correct"])
    
    if s_corr != c_corr:
        t_meta = all_tasks[tid]
        # Categorize strong failure if strong failed
        fail_type = "N/A (strong passed)"
        if s_corr == 0:
            if s_rec["finish_reason"] == "length":
                fail_type = "token truncation (finish_reason=length)"
            elif t_meta["category"] == "code":
                fail_type = f"code failure ({s_rec['grader_info'][:40]})"
            else:
                fail_type = f"wrong answer ({s_rec['grader_info'][:40]})"
                
        strong_vs_clf_discordant.append({
            "task_id": tid,
            "category": t_meta["category"],
            "dataset": t_meta["dataset"],
            "prompt": t_meta["prompt"][:80].replace("\n", " "),
            "strong_correct": s_corr,
            "strong_model": s_rec["final_model"],
            "strong_fail_type": fail_type,
            "classifier_correct": c_corr,
            "classifier_model": c_rec["final_model"],
            "classifier_info": c_rec["grader_info"][:40]
        })

print(f"Discordant tasks (always_strong vs classifier): {len(strong_vs_clf_discordant)}")
for d in strong_vs_clf_discordant:
    print(f"Task {d['task_id']} ({d['category']}): Strong={d['strong_correct']} ({d['strong_fail_type']}) vs Clf={d['classifier_correct']} ({d['classifier_model']}, {d['classifier_info']})")

print("\n=== TASK 3: PAIRED COMPARISON (always_strong vs cascade) ===")
strong_vs_casc_discordant = []
for tid in test_ids:
    s_rec = strat_runs[("always_strong", 0.5)][tid]
    c_rec = strat_runs[("cascade", 0.5)][tid]
    s_corr = int(s_rec["correct"])
    c_corr = int(c_rec["correct"])
    
    if s_corr != c_corr:
        t_meta = all_tasks[tid]
        fail_type = "N/A (strong passed)"
        if s_corr == 0:
            if s_rec["finish_reason"] == "length":
                fail_type = "token truncation (finish_reason=length)"
            elif t_meta["category"] == "code":
                fail_type = f"code failure ({s_rec['grader_info'][:40]})"
            else:
                fail_type = f"wrong answer ({s_rec['grader_info'][:40]})"
                
        strong_vs_casc_discordant.append({
            "task_id": tid,
            "category": t_meta["category"],
            "dataset": t_meta["dataset"],
            "prompt": t_meta["prompt"][:80].replace("\n", " "),
            "strong_correct": s_corr,
            "strong_model": s_rec["final_model"],
            "strong_fail_type": fail_type,
            "cascade_correct": c_corr,
            "cascade_model": c_rec["final_model"],
            "cascade_info": c_rec["grader_info"][:40]
        })

print(f"Discordant tasks (always_strong vs cascade): {len(strong_vs_casc_discordant)}")
for d in strong_vs_casc_discordant:
    print(f"Task {d['task_id']} ({d['category']}): Strong={d['strong_correct']} ({d['strong_fail_type']}) vs Casc={d['cascade_correct']} ({d['cascade_model']}, {d['cascade_info']})")

# ---------------------------------------------------------
# TASK 4: Tasks No Model Solved
# ---------------------------------------------------------
print("\n=== TASK 4: TASKS NO MODEL SOLVED ===")
unsolved_tasks = []
for tid in test_ids:
    models_dict = task_tested_models[tid]
    any_pass = any(m["correct"] == 1 for m in models_dict.values())
    if not any_pass:
        t_meta = all_tasks[tid]
        unsolved_tasks.append({
            "task_id": tid,
            "category": t_meta["category"],
            "dataset": t_meta["dataset"],
            "prompt": t_meta["prompt"][:100].replace("\n", " "),
            "gold_answer": str(t_meta["answer"])[:50],
            "models_tested": {m: data["grader_info"] for m, data in models_dict.items()},
            "oracle_label": 2 # labeled as ceiling tier 2 in benchmark v2
        })

print(f"Total unsolved test tasks: {len(unsolved_tasks)} / {len(test_ids)}")
for u in unsolved_tasks:
    print(f"- {u['task_id']} ({u['category']}, {u['dataset']}): {u['prompt']}")
    for m, info in u['models_tested'].items():
        print(f"    {m}: {info}")

# ---------------------------------------------------------
# TASK 5: Bootstrap 95% Confidence Intervals (1000 resamples)
# ---------------------------------------------------------
print("\n=== TASK 5: BOOTSTRAP 95% CONFIDENCE INTERVALS (1000 RESAMPLES) ===")
np.random.seed(42)
N = len(test_ids)
B = 1000

# Resample indices
boot_indices = [np.random.choice(N, size=N, replace=True) for _ in range(B)]

def run_bootstrap_for_strategy(strat_key, strat_name):
    strat_dict = strat_runs[strat_key] if strat_key in strat_runs else None
    
    # Pre-extract arrays for speed
    if strat_key == "oracle":
        c_costs = np.array([r["cost"] for r in oracle_records])
        c_corrs = np.array([r["correct"] for r in oracle_records])
    else:
        c_costs = np.array([float(strat_dict[tid]["cost"]) for tid in test_ids])
        c_corrs = np.array([int(strat_dict[tid]["correct"]) for tid in test_ids])

    s_costs = np.array([float(strat_runs[("always_strong", 0.5)][tid]["cost"]) for tid in test_ids])
    s_corrs = np.array([int(strat_runs[("always_strong", 0.5)][tid]["correct"]) for tid in test_ids])

    savings = []
    qual_diffs = []

    for b in range(B):
        idx = boot_indices[b]
        b_c_cost = c_costs[idx].sum()
        b_s_cost = s_costs[idx].sum()
        
        # Cost saving %
        if b_s_cost > 0:
            sav = 100.0 * (1.0 - b_c_cost / b_s_cost)
        else:
            sav = 0.0
        savings.append(sav)

        # Quality diff: Quality(strat) - Quality(strong)
        q_diff = (c_corrs[idx].sum() - s_corrs[idx].sum()) / N
        qual_diffs.append(q_diff)

    sav_low, sav_high = np.percentile(savings, [2.5, 97.5])
    q_low, q_high = np.percentile(qual_diffs, [2.5, 97.5])
    
    return {
        "strategy": strat_name,
        "mean_saving": round(float(np.mean(savings)), 2),
        "saving_ci_95": [round(float(sav_low), 2), round(float(sav_high), 2)],
        "mean_qual_diff": round(float(np.mean(qual_diffs)), 4),
        "qual_diff_ci_95": [round(float(q_low), 4), round(float(q_high), 4)]
    }

boot_results = []
for skey, sname in [
    (("classifier", 0.5), "classifier"),
    (("rules", 0.5), "rules"),
    (("cascade", 0.5), "cascade"),
    (("random", 0.5), "random"),
    (("always_cheap", 0.5), "always_cheap"),
    ("oracle", "oracle_router")
]:
    res = run_bootstrap_for_strategy(skey, sname)
    boot_results.append(res)
    print(f"Strategy: {sname:15s} | Cost Saving 95% CI: [{res['saving_ci_95'][0]:.1f}%, {res['saving_ci_95'][1]:.1f}%] (mean: {res['mean_saving']:.1f}%) | Quality Diff 95% CI: [{res['qual_diff_ci_95'][0]*100:+.1f}%, {res['qual_diff_ci_95'][1]*100:+.1f}%] (mean: {res['mean_qual_diff']*100:+.1f}%)")

# ---------------------------------------------------------
# TASK 6: Mean Cost per 1,000 Requests
# ---------------------------------------------------------
print("\n=== TASK 6: MEAN COST PER 1,000 REQUESTS ===")
cost_1k_results = {}
for skey, sname in [
    (("always_strong", 0.5), "always_strong"),
    (("always_cheap", 0.5), "always_cheap"),
    (("random", 0.5), "random"),
    (("cascade", 0.5), "cascade"),
    (("rules", 0.5), "rules"),
    (("classifier", 0.5), "classifier"),
    ("oracle", "oracle_router")
]:
    if skey == "oracle":
        tot_c = sum(r["cost"] for r in oracle_records)
    else:
        tot_c = sum(float(strat_runs[skey][tid]["cost"]) for tid in test_ids)
    
    cost_per_1k = (tot_c / len(test_ids)) * 1000.0
    cost_1k_results[sname] = {
        "total_cost_60": round(tot_c, 6),
        "cost_per_1k": round(cost_per_1k, 4)
    }
    print(f"{sname:15s} | Total (60 tasks): ${tot_c:.6f} | Cost per 1,000 requests: ${cost_per_1k:.4f}")

# Save all results to results/v2_followup/analysis_data.json
out_data = {
    "oracle_router": {
        "quality_ratio": f"{oracle_k}/{oracle_n}",
        "quality_pct": round(oracle_k / oracle_n * 100, 2),
        "total_cost": round(oracle_cost, 6),
        "cost_saving_pct": round(oracle_saving, 2),
        "mean_latency_s": round(oracle_lat, 3),
        "workload_breakdown": dict(oracle_models)
    },
    "paired_comparison_strong_vs_classifier": strong_vs_clf_discordant,
    "paired_comparison_strong_vs_cascade": strong_vs_casc_discordant,
    "unsolved_tasks": unsolved_tasks,
    "bootstrap_intervals": boot_results,
    "cost_per_1000_requests": cost_1k_results
}

with open("results/v2_followup/analysis_data.json", "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2, ensure_ascii=False)
print("\nSaved full analysis data to results/v2_followup/analysis_data.json")
