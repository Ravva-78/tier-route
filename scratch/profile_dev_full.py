import json
import os
import time
from tierroute.config import load_config
from tierroute.providers import Provider
from evaluation.grading_v2 import grade_task_v2

cfg = load_config()
providers = {m.tier: Provider(m, mode="live") for m in cfg.models}

with open("benchmark/tasks_v2.json", "r", encoding="utf-8") as f:
    all_tasks = {t["id"]: t for t in json.load(f)}

with open("benchmark/split_v2.json", "r", encoding="utf-8") as f:
    split = json.load(f)

dev_ids = split["dev_ids"]
out_path = "results/benchmark_v2_dev_profile.json"

profile_data = {}
if os.path.exists(out_path):
    try:
        with open(out_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        print(f"Resuming dev profile: already completed {len(profile_data)} / {len(dev_ids)} tasks.")
    except Exception as e:
        print(f"Could not load existing profile: {e}")

tier_names = {0: "local-small", 1: "hosted-mid", 2: "hosted-strong"}

for idx, tid in enumerate(dev_ids, start=1):
    if tid in profile_data:
        continue
    t = all_tasks[tid]
    print(f"\n[{idx}/{len(dev_ids)}] Profiling {tid} ({t['category']}) from {t['dataset']}...")
    task_res = {
        "id": tid,
        "dataset": t["dataset"],
        "category": t["category"],
        "prompt": t["prompt"],
        "gold_answer": t["answer"],
        "models": {}
    }

    for tier in [0, 1, 2]:
        mname = tier_names[tier]
        p = providers[tier]
        t0 = time.time()
        res = p.generate(t["prompt"], max_tokens=1024, temperature=0.0)
        dur = time.time() - t0
        ok, why = grade_task_v2(t, res.text)
        task_res["models"][mname] = {
            "tier": tier,
            "ok": ok,
            "why": why,
            "tokens_in": res.tokens_in,
            "tokens_out": res.tokens_out,
            "latency_s": round(res.latency_s, 3),
            "finish_reason": res.finish_reason,
            "error": res.error,
            "text": res.text
        }
        print(f"   Tier {tier} ({mname}): ok={ok} ({why[:30]}), lat={res.latency_s:.2f}s, out={res.tokens_out}")
        # Brief throttle between cloud calls
        if tier > 0:
            time.sleep(0.6)

    # Determine oracle tier (cheapest model that answers correctly)
    t0_ok = task_res["models"]["local-small"]["ok"]
    t1_ok = task_res["models"]["hosted-mid"]["ok"]
    t2_ok = task_res["models"]["hosted-strong"]["ok"]

    if t0_ok:
        oracle_tier = 0
    elif t1_ok:
        oracle_tier = 1
    elif t2_ok:
        oracle_tier = 2
    else:
        # None answered correctly; assign highest tier
        oracle_tier = 2

    task_res["oracle_tier"] = oracle_tier
    task_res["oracle_model"] = tier_names[oracle_tier]
    print(f"   => Oracle Tier: {oracle_tier} ({tier_names[oracle_tier]}) [T0={t0_ok}, T1={t1_ok}, T2={t2_ok}]")

    profile_data[tid] = task_res
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2, ensure_ascii=False)

print(f"\nDev profiling complete! Saved {len(profile_data)} tasks to {out_path}.")
