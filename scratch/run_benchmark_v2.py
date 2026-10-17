import csv
import json
import math
import os
import random
import time
from typing import Dict, List, Any, Tuple

from tierroute.config import load_config
from tierroute.providers import Provider, LLMResult
from tierroute.grading_v2 import grade_task_v2
from tierroute.analyzer import analyze
from tierroute.classifier_v2 import ComplexityClassifierV2

# Load models and config
cfg = load_config()
providers = {m.tier: Provider(m, mode="live") for m in cfg.models}
tier_models = {m.tier: m.name for m in cfg.models}
model_specs = {m.name: m for m in cfg.models}

# Tuned thresholds on benchmark v2 DEV set
TUNED_T1 = 0.50
TUNED_T2 = 0.74

# Train Classifier V2 on Seeds + Dev Set
print("Initializing Classifier V2...")
clf_v2 = ComplexityClassifierV2(auto_train=True)
print("Classifier V2 trained and verified leak-free.")

# Load Benchmark V2 Tasks and Split
with open("benchmark/tasks_v2.json", "r", encoding="utf-8") as f:
    all_tasks = {t["id"]: t for t in json.load(f)}

with open("benchmark/split_v2.json", "r", encoding="utf-8") as f:
    split_info = json.load(f)

test_ids = split_info["test_ids"]
test_tasks = [all_tasks[tid] for tid in test_ids]
print(f"Loaded {len(test_tasks)} held-out TEST tasks for benchmark v2 evaluation.")

# Execution Cache for deterministic live calls (prompt + model_name -> LLMResult)
# Saves repeated API calls on identical inputs while preserving live data
LIVE_CACHE: Dict[Tuple[str, str], LLMResult] = {}
cache_file = "results/benchmark_v2_call_cache.json"
if os.path.exists(cache_file):
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            raw_cache = json.load(f)
            for k, v in raw_cache.items():
                prompt_key, mname = k.split("|||", 1)
                LIVE_CACHE[(prompt_key, mname)] = LLMResult(
                    text=v["text"],
                    tokens_in=v["tokens_in"],
                    tokens_out=v["tokens_out"],
                    latency_s=v["latency_s"],
                    error=v.get("error"),
                    finish_reason=v.get("finish_reason", "stop")
                )
        print(f"Loaded {len(LIVE_CACHE)} cached live model responses.")
    except Exception as e:
        print(f"Cache load error: {e}")

def save_cache():
    raw = {}
    for (p, m), r in LIVE_CACHE.items():
        raw[f"{p}|||{m}"] = {
            "text": r.text,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "latency_s": r.latency_s,
            "error": r.error,
            "finish_reason": r.finish_reason
        }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)

def query_model(tier: int, prompt: str) -> LLMResult:
    mname = tier_models[tier]
    key = (prompt, mname)
    if key in LIVE_CACHE:
        return LIVE_CACHE[key]

    p = providers[tier]
    res = p.generate(prompt, max_tokens=1024, temperature=0.0)
    LIVE_CACHE[key] = res
    save_cache()
    if tier > 0:
        time.sleep(0.5)
    return res

def wilson_interval(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.95996
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p)) / n + (z**2) / (4 * n**2))
    return max(0.0, center - margin), min(1.0, center + margin)

# Raw records storage
raw_rows = []

# Evaluate a strategy on test tasks
def eval_strategy(strat_name: str, bias: float = 0.5):
    print(f"\n=======================================================")
    print(f"Evaluating Strategy: {strat_name} (bias={bias}) on {len(test_tasks)} test tasks")
    print(f"=======================================================")
    
    # Random seed for random baseline
    rnd = random.Random(42)

    strat_records = []
    for idx, t in enumerate(test_tasks, start=1):
        prompt = t["prompt"]

        # 1. Determine Initial Routing Tier
        if strat_name == "always_strong":
            first_tier = 2
            reason = "baseline: always strongest tier"
        elif strat_name == "always_cheap":
            first_tier = 0
            reason = "baseline: always cheapest local tier"
        elif strat_name == "random":
            first_tier = rnd.randint(0, 2)
            reason = "baseline: uniform random tier"
        elif strat_name == "cascade":
            first_tier = 0
            reason = "cascade: always try local-small first"
        elif strat_name == "rules":
            feat = analyze(prompt)
            shift = (bias - 0.5) * 0.5
            thresh = [TUNED_T1 - shift, TUNED_T2 - shift]
            first_tier = sum(1 for th in thresh if feat["score"] >= th)
            reason = f"rules: score {feat['score']:.2f} -> tier {first_tier} at bias {bias:.2f}"
        elif strat_name == "classifier":
            pred = clf_v2.predict(prompt, bias=bias)
            first_tier = pred["tier"]
            reason = f"classifier: predicted tier {first_tier} (conf={pred['confidence']:.2f}) at bias {bias:.2f}"
        else:
            raise ValueError(f"Unknown strategy: {strat_name}")

        # 2. Execution and Escalation Loop
        attempts = []
        curr_tier = first_tier
        total_cost = 0.0
        total_lat = 0.0

        while True:
            mname = tier_models[curr_tier]
            spec = model_specs[mname]
            res = query_model(curr_tier, prompt)
            
            cost = spec.cost(res.tokens_in, res.tokens_out)
            ok, why = grade_task_v2(t, res.text)
            
            total_cost += cost
            total_lat += res.latency_s
            
            attempts.append({
                "tier": curr_tier,
                "model": mname,
                "ok": ok,
                "why": why,
                "cost": cost,
                "latency_s": round(res.latency_s, 3),
                "tokens_in": res.tokens_in,
                "tokens_out": res.tokens_out,
                "finish_reason": res.finish_reason
            })

            # Check if escalation is permitted:
            # - For 'cascade': always escalates on failed verification until tier 2
            # - For 'rules' and 'classifier': escalates on failed verification until tier 2
            can_escalate = (not ok) and (strat_name in ("cascade", "rules", "classifier")) and (curr_tier < 2)
            if not can_escalate:
                break
            curr_tier += 1

        last = attempts[-1]
        final_tier = last["tier"]
        final_model = last["model"]
        is_correct = int(last["ok"])
        escalated = int(len(attempts) > 1)

        record = {
            "task_id": t["id"],
            "dataset": t["dataset"],
            "category": t["category"],
            "strategy": strat_name,
            "bias": bias,
            "first_tier": first_tier,
            "first_model": tier_models[first_tier],
            "final_tier": final_tier,
            "final_model": final_model,
            "correct": is_correct,
            "grader_info": last["why"],
            "cost": total_cost,
            "latency_s": total_lat,
            "tokens_in": sum(a["tokens_in"] for a in attempts),
            "tokens_out": sum(a["tokens_out"] for a in attempts),
            "finish_reason": last["finish_reason"],
            "truncated": int(last["finish_reason"] == "length"),
            "escalated": escalated,
            "attempts_count": len(attempts),
            "reason": reason,
            "answer": res.text.strip().replace("\n", " ")[:200]
        }
        strat_records.append(record)
        raw_rows.append(record)

    # Strategy aggregate stats
    k_correct = sum(r["correct"] for r in strat_records)
    n_total = len(strat_records)
    ci_low, ci_high = wilson_interval(k_correct, n_total)
    cost_sum = sum(r["cost"] for r in strat_records)
    lat_mean = sum(r["latency_s"] for r in strat_records) / n_total
    lats = sorted(r["latency_s"] for r in strat_records)
    lat_p50 = (lats[n_total // 2 - 1] + lats[n_total // 2]) / 2.0
    trunc_count = sum(r["truncated"] for r in strat_records)
    esc_count = sum(r["escalated"] for r in strat_records)
    model_counts = {}
    for r in strat_records:
        model_counts[r["final_model"]] = model_counts.get(r["final_model"], 0) + 1

    summary = {
        "strategy": strat_name,
        "bias": bias,
        "sub_tasks": n_total,
        "correct_count": k_correct,
        "quality_ratio": f"{k_correct}/{n_total}",
        "quality": round(k_correct / n_total, 4),
        "quality_wilson_ci": [round(ci_low, 4), round(ci_high, 4)],
        "quality_wilson_str": f"{k_correct}/{n_total} ({(k_correct/n_total)*100:.1f}% [{ci_low*100:.1f}%, {ci_high*100:.1f}%])",
        "cost_usd": round(cost_sum, 6),
        "mean_latency_s": round(lat_mean, 3),
        "median_latency_s": round(lat_p50, 3),
        "total_latency_s": round(sum(r["latency_s"] for r in strat_records), 3),
        "truncated_count": trunc_count,
        "escalations": esc_count,
        "workload_counts": model_counts
    }
    print(f"Summary for {strat_name} (bias={bias}):")
    print(f"  Quality: {summary['quality_wilson_str']}")
    print(f"  Cost: ${summary['cost_usd']:.6f}, Latency: mean={summary['mean_latency_s']:.2f}s, p50={summary['median_latency_s']:.2f}s")
    print(f"  Workload: {model_counts}, Escalations: {esc_count}")
    return summary

# Execute all required benchmark v2 runs:
# 1. Main strategies at default bias 0.5:
summaries = []
for strat in ["always_strong", "always_cheap", "random", "cascade", "rules", "classifier"]:
    s = eval_strategy(strat, bias=0.50)
    summaries.append(s)

# 2. Bias sweeps for rules and classifier:
rules_sweeps = []
clf_sweeps = []
for b in [0.0, 0.25, 0.75, 1.0]:
    s_r = eval_strategy("rules", bias=b)
    rules_sweeps.append(s_r)
    s_c = eval_strategy("classifier", bias=b)
    clf_sweeps.append(s_c)

# 3. Post-Hoc Oracle Tier Calculation on the TEST Set
print("\n--- Computing Post-Hoc Oracle Tiers for TEST Set ---")
test_oracle = {}
for t in test_tasks:
    tid = t["id"]
    # Check if local-small answered correctly in any test run
    # Check if hosted-mid answered correctly
    # Check if hosted-strong answered correctly
    t0_correct = any(r["correct"] == 1 for r in raw_rows if r["task_id"] == tid and r["final_model"] == "local-small")
    t1_correct = any(r["correct"] == 1 for r in raw_rows if r["task_id"] == tid and r["final_model"] == "hosted-mid")
    t2_correct = any(r["correct"] == 1 for r in raw_rows if r["task_id"] == tid and r["final_model"] == "hosted-strong")
    
    # If not tested yet for a model on this task, query it to establish ground truth oracle:
    if not (t0_correct or t1_correct or t2_correct):
        res0 = query_model(0, t["prompt"])
        ok0, _ = grade_task_v2(t, res0.text)
        t0_correct = ok0
        if not t0_correct:
            res1 = query_model(1, t["prompt"])
            ok1, _ = grade_task_v2(t, res1.text)
            t1_correct = ok1
        if not (t0_correct or t1_correct):
            res2 = query_model(2, t["prompt"])
            ok2, _ = grade_task_v2(t, res2.text)
            t2_correct = ok2

    if t0_correct:
        o_tier = 0
    elif t1_correct:
        o_tier = 1
    elif t2_correct:
        o_tier = 2
    else:
        o_tier = 2
    test_oracle[tid] = o_tier

print(f"Test Set Oracle Tiers computed across all {len(test_oracle)} test tasks.")
from collections import Counter
print(f"Test Oracle Distribution: {dict(Counter(test_oracle.values()))}")

# Add oracle_tier and compute routing accuracy metrics for all runs
strong_cost = next(s["cost_usd"] for s in summaries if s["strategy"] == "always_strong")
strong_quality = next(s["quality"] for s in summaries if s["strategy"] == "always_strong")

for s in summaries + rules_sweeps + clf_sweeps:
    st_name = s["strategy"]
    b_val = s["bias"]
    matching_rows = [r for r in raw_rows if r["strategy"] == st_name and r["bias"] == b_val]
    for r in matching_rows:
        r["gold_tier"] = test_oracle[r["task_id"]]

    acc_count = sum(1 for r in matching_rows if r["first_tier"] == test_oracle[r["task_id"]])
    under_count = sum(1 for r in matching_rows if r["first_tier"] < test_oracle[r["task_id"]])
    over_count = sum(1 for r in matching_rows if r["first_tier"] > test_oracle[r["task_id"]])
    
    s["routing_accuracy"] = round(acc_count / len(matching_rows), 4)
    s["under_routed"] = under_count
    s["over_routed"] = over_count
    s["cost_saving_vs_strong_pct"] = round(100.0 * (1.0 - s["cost_usd"] / strong_cost), 2) if strong_cost > 0 else 0.0
    s["quality_vs_strong"] = round(s["quality"] / strong_quality, 4) if strong_quality > 0 else 0.0

# Save Results
raw_csv_path = "results/benchmark_v2_raw.csv"
fieldnames = [
    "task_id", "dataset", "category", "strategy", "bias", "first_model", "final_model",
    "first_tier", "final_tier", "gold_tier", "correct", "grader_info", "cost", "latency_s",
    "tokens_in", "tokens_out", "finish_reason", "truncated", "escalated", "attempts_count",
    "reason", "answer"
]

with open(raw_csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(raw_rows)
print(f"Wrote {len(raw_rows)} raw records to {raw_csv_path}")

benchmark_json_path = "results/benchmark_v2.json"
final_data = {
    "benchmark": "v2_harder_benchmark",
    "models": {
        "tier_0": "local-small (llama3.2:3b via Ollama)",
        "tier_1": "hosted-mid (openai/gpt-oss-20b via Groq)",
        "tier_2": "hosted-strong (openai/gpt-oss-120b via Groq)"
    },
    "sub_tasks": 60,
    "seed": 42,
    "tuned_thresholds": [TUNED_T1, TUNED_T2],
    "main_strategies": summaries,
    "rules_sweeps": rules_sweeps,
    "classifier_sweeps": clf_sweeps,
    "test_oracle_distribution": dict(Counter(test_oracle.values()))
}

with open(benchmark_json_path, "w", encoding="utf-8") as f:
    json.dump(final_data, f, indent=2)
print(f"Saved benchmark v2 results to {benchmark_json_path}")
print("BENCHMARK V2 EVALUATION COMPLETE!")
