import json
import os
import time
from tierroute.config import load_config
from tierroute.providers import Provider
from tierroute.grading_v2 import grade_task_v2

cfg = load_config()
spec_strong = next(m for m in cfg.models if m.name == "hosted-strong")
provider_strong = Provider(spec_strong, mode="live")

with open("benchmark/tasks_v2.json", "r", encoding="utf-8") as f:
    all_tasks = {t["id"]: t for t in json.load(f)}

with open("benchmark/split_v2.json", "r", encoding="utf-8") as f:
    split_info = json.load(f)

test_ids = split_info["test_ids"]
test_tasks = [all_tasks[tid] for tid in test_ids]

print(f"Loaded {len(test_tasks)} test tasks for followup evaluations.")

# Function to run an evaluation set
def run_strong_eval(eval_name: str, max_tokens: int, extra_body=None, out_file: str = None):
    print(f"\n=======================================================")
    print(f"Running: {eval_name} (max_tokens={max_tokens}, extra_body={extra_body})")
    print(f"=======================================================")
    
    results = []
    # If partially complete, resume
    if out_file and os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"Resuming {eval_name}: already completed {len(results)} tasks.")
        except Exception:
            results = []

    done_ids = {r["task_id"] for r in results}

    for idx, t in enumerate(test_tasks, start=1):
        tid = t["id"]
        if tid in done_ids:
            continue
        
        prompt = t["prompt"]
        t0 = time.time()
        res = provider_strong.generate(prompt, max_tokens=max_tokens, temperature=0.0, extra_body=extra_body)
        cost = spec_strong.cost(res.tokens_in, res.tokens_out)
        ok, why = grade_task_v2(t, res.text)
        
        rec = {
            "task_id": tid,
            "category": t["category"],
            "dataset": t["dataset"],
            "max_tokens": max_tokens,
            "extra_body": extra_body,
            "tokens_in": res.tokens_in,
            "tokens_out": res.tokens_out,
            "cost": cost,
            "latency_s": round(res.latency_s, 3),
            "finish_reason": res.finish_reason,
            "truncated": int(res.finish_reason == "length"),
            "correct": int(ok),
            "grader_info": why,
            "error": res.error,
            "answer_preview": res.text.strip().replace("\n", " ")[:160]
        }
        results.append(rec)
        print(f"[{idx}/{len(test_tasks)}] {tid} ({t['category']}): ok={ok} ({why[:25]}), finish={res.finish_reason}, lat={res.latency_s:.2f}s, out={res.tokens_out}")
        
        if out_file:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        
        time.sleep(0.5)

    # Compute summary
    k = sum(r["correct"] for r in results)
    n = len(results)
    cost_total = sum(r["cost"] for r in results)
    lat_mean = sum(r["latency_s"] for r in results) / n
    lats = sorted(r["latency_s"] for r in results)
    lat_p50 = (lats[n//2 - 1] + lats[n//2]) / 2.0
    trunc_cnt = sum(r["truncated"] for r in results)
    
    summary = {
        "eval_name": eval_name,
        "max_tokens": max_tokens,
        "extra_body": extra_body,
        "tasks": n,
        "correct": k,
        "quality_ratio": f"{k}/{n}",
        "quality_pct": round(k / n * 100, 2),
        "cost_total": round(cost_total, 6),
        "mean_latency_s": round(lat_mean, 3),
        "median_latency_s": round(lat_p50, 3),
        "total_latency_s": round(sum(r["latency_s"] for r in results), 3),
        "truncated_count": trunc_cnt
    }
    print(f"\n--- Summary for {eval_name} ---")
    print(f"Quality: {k}/{n} ({summary['quality_pct']}%), Truncated: {trunc_cnt}")
    print(f"Cost: ${cost_total:.6f}, Latency: mean={lat_mean:.2f}s, median={lat_p50:.2f}s")
    return summary, results

if __name__ == "__main__":
    # 1. Rerun always_strong with max_tokens=4096 (default reasoning effort)
    sum_4096, res_4096 = run_strong_eval(
        eval_name="always_strong_4096",
        max_tokens=4096,
        extra_body=None,
        out_file="results/v2_followup/always_strong_4096_raw.json"
    )

    # 2. Rerun always_strong with max_tokens=4096 and reasoning_effort='low'
    sum_low, res_low = run_strong_eval(
        eval_name="always_strong_4096_low_reasoning",
        max_tokens=4096,
        extra_body={"reasoning_effort": "low"},
        out_file="results/v2_followup/always_strong_4096_low_raw.json"
    )

    # Save summary comparison
    with open("results/v2_followup/strong_token_comparison.json", "w", encoding="utf-8") as f:
        json.dump({
            "always_strong_4096": sum_4096,
            "always_strong_4096_low": sum_low
        }, f, indent=2)
    print("\nSaved strong token comparison to results/v2_followup/strong_token_comparison.json")
