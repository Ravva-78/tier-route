"""Benchmark: Compares routing strategies on held-out tasks and sweeps the cost/quality dial.
Academic rigour requirements:
  - Held-out test set evaluation with zero evaluation leakage
  - 3 repeated runs at temperature 0 with mean and standard deviation
  - 95% Wilson score confidence intervals for quality ratios (x/n)
  - Explicit note: temperature-0 repeats are not independent samples
  - Raw per-task CSV logs including finish_reason and truncated flag
  - Per-model final workload distribution table (showing local tier share)
  - Abort on tier failure via --require-all-tiers
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tierroute.classifier import classifier
from tierroute.config import load_config
from tierroute.router import Overrides, Router
from tierroute.store import Store

DIFFICULTY = {0: 0.2, 1: 0.5, 2: 0.85}


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """Calculates 95% Wilson score confidence interval for binomial success count k/n."""
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963984540054  # 95% two-sided normal quantile
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z * z) / (4.0 * (n * n)))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return p, lower, upper


def check(answer: str, spec: dict) -> bool:
    a = (answer or "").strip()
    t, v = spec["type"], spec.get("value")
    fl = re.I | re.S
    if t == "exact":
        return a.lower() == str(v).lower()
    if t == "contains_any":
        return any(x.lower() in a.lower() for x in v)
    if t == "contains_all":
        return all(x.lower() in a.lower() for x in v)
    if t == "regex":
        return re.search(v, a, fl) is not None
    if t == "regex_all":
        return all(re.search(x, a, fl) for x in v)
    if t == "number":
        nums = re.findall(r"-?\d+(?:\.\d+)?", a.replace(",", ""))
        return bool(nums) and abs(float(nums[-1]) - float(v)) < 1e-6
    raise ValueError(f"Unknown check type: {t}")


def load_dataset(split: str = "test"):
    tasks_file = ROOT / "benchmark" / "tasks.json"
    split_file = ROOT / "benchmark" / "split.json"
    all_tasks = json.loads(tasks_file.read_text(encoding="utf-8"))

    for t in all_tasks:
        if "parts" in t:
            t["prompt"] = "\n".join(f"{i}. {p['prompt']}" for i, p in enumerate(t["parts"], 1))

    if split == "full":
        total_subtasks = sum(len(t.get("parts", [1])) for t in all_tasks)
        return all_tasks, f"full ({len(all_tasks)} tasks, {total_subtasks} subtasks, not held-out)"

    if split_file.exists():
        split_data = json.loads(split_file.read_text(encoding="utf-8"))
        dev_ids = set(split_data.get("dev_task_ids", []))
        test_ids = set(split_data.get("test_task_ids", []))
        if split == "dev":
            filtered = [t for t in all_tasks if t["id"] in dev_ids]
            total_subtasks = sum(len(t.get("parts", [1])) for t in filtered)
            return filtered, f"dev set ({len(filtered)} tasks, {total_subtasks} subtasks)"
        else:
            filtered = [t for t in all_tasks if t["id"] in test_ids]
            total_subtasks = sum(len(t.get("parts", [1])) for t in filtered)
            return filtered, f"held-out test set ({len(filtered)} tasks, {total_subtasks} subtasks)"

    return all_tasks, "full (unsplit)"


def run_single_pass(router, tasks, strategy, bias=0.5, temperature=0.0):
    tot = {
        "cost": 0.0, "strong": 0.0, "lat": 0.0, "correct": 0, "parts": 0,
        "route_ok": 0, "under": 0, "over": 0, "esc": 0, "unverified": 0, "truncated": 0
    }
    per_model = {}
    subtask_rows = []

    for t in tasks:
        specs = t["parts"] if "parts" in t else [t]
        meta = [{"difficulty": DIFFICULTY[s["tier"]], "answer": s["answer"]} for s in specs]
        out = router.route(
            t["prompt"],
            bias=bias,
            strategy=strategy,
            meta=meta,
            split=("parts" in t),
            log=False,
            temperature=temperature,
            max_tokens=1024
        )

        tot["cost"] += out["total_cost"]
        tot["strong"] += out["est_strong_cost"]
        tot["lat"] += out["total_latency_s"]
        aligned = len(out["parts"]) == len(specs)

        for k, s in enumerate(specs):
            ans = out["parts"][k]["answer"] if aligned else out["answer"]
            tot["parts"] += 1
            is_corr = int(check(ans, s["check"]))
            tot["correct"] += is_corr

            p = out["parts"][k] if aligned else out["parts"][0]
            ft = p["first_tier"]
            tot["route_ok"] += int(ft == s["tier"])
            tot["under"] += int(ft < s["tier"])
            tot["over"] += int(ft > s["tier"])
            tot["esc"] += p["escalated"]
            tot["unverified"] += int(not p["verified"])
            tot["truncated"] += p.get("truncated", 0)
            per_model[p["final_model"]] = per_model.get(p["final_model"], 0) + 1

            subtask_id = f"{t['id']}_p{k}" if "parts" in t else t["id"]
            subtask_rows.append({
                "task_id": subtask_id,
                "strategy": strategy,
                "bias": bias,
                "first_model": p["first_model"],
                "final_model": p["final_model"],
                "tier": p["tier"],
                "gold_tier": s["tier"],
                "correct": is_corr,
                "cost": p["cost"],
                "latency_s": round(p["latency_s"], 4),
                "tokens": p["tokens_in"] + p["tokens_out"],
                "finish_reason": p.get("finish_reason", "stop"),
                "truncated": p.get("truncated", 0),
                "escalated": p["escalated"],
                "verified": p["verified"],
                "answer": ans[:80].replace("\n", " "),
                "check_type": s["check"]["type"],
            })

    n = tot["parts"]
    k = tot["correct"]
    q, low, high = wilson_score_interval(k, n)
    summary = {
        "strategy": strategy,
        "bias": bias,
        "sub_tasks": n,
        "correct_count": k,
        "quality_ratio": f"{k}/{n}",
        "wilson_ci_95": [round(low, 4), round(high, 4)],
        "wilson_ci_str": f"{k}/{n} ({q*100:.1f}% [{low*100:.1f}%, {high*100:.1f}%])",
        "truncated_count": tot["truncated"],
        "cost_usd": tot["cost"],
        "latency_s": round(tot["lat"], 3),
        "quality": round(q, 4),
        "routing_accuracy": round(tot["route_ok"] / n, 4) if n else 0.0,
        "under_routed": tot["under"],
        "over_routed": tot["over"],
        "escalations": tot["esc"],
        "final_model_counts": per_model
    }
    return summary, subtask_rows


def mean_std(values):
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    if len(values) == 1:
        return m, 0.0
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return m, math.sqrt(var)


def run_benchmark_replicates(router, tasks, strategy, bias=0.5, n_runs=3, temperature=0.0):
    runs_data = []
    all_raw_rows = []

    for r_idx in range(n_runs):
        summary, raw_rows = run_single_pass(router, tasks, strategy, bias=bias, temperature=temperature)
        for row in raw_rows:
            row["run_idx"] = r_idx + 1
            all_raw_rows.append(row)
        runs_data.append(summary)

    cost_m, cost_s = mean_std([d["cost_usd"] for d in runs_data])
    qual_m, qual_s = mean_std([d["quality"] for d in runs_data])
    lat_m, lat_s = mean_std([d["latency_s"] for d in runs_data])
    acc_m, acc_s = mean_std([d["routing_accuracy"] for d in runs_data])
    esc_m, esc_s = mean_std([d["escalations"] for d in runs_data])
    trunc_m, trunc_s = mean_std([d["truncated_count"] for d in runs_data])

    last = runs_data[-1]
    n = last["sub_tasks"]
    k = int(round(qual_m * n))
    q, low, high = wilson_score_interval(k, n)

    agg = {
        "strategy": strategy,
        "bias": bias,
        "sub_tasks": n,
        "n_runs": n_runs,
        "correct_count": k,
        "quality_ratio": f"{k}/{n}",
        "quality_wilson_ci": [round(low, 4), round(high, 4)],
        "quality_wilson_str": f"{k}/{n} ({q*100:.1f}% [{low*100:.1f}%, {high*100:.1f}%])",
        "truncated_count": int(trunc_m),
        "cost_usd": round(cost_m, 6),
        "cost_usd_std": round(cost_s, 6),
        "quality": round(qual_m, 4),
        "quality_std": round(qual_s, 4),
        "latency_s": round(lat_m, 3),
        "latency_s_std": round(lat_s, 3),
        "routing_accuracy": round(acc_m, 4),
        "routing_accuracy_std": round(acc_s, 4),
        "escalations": round(esc_m, 2),
        "escalations_std": round(esc_s, 2),
        "under_routed": last["under_routed"],
        "over_routed": last["over_routed"],
        "final_model_counts": last["final_model_counts"],
        "replicates": runs_data
    }
    return agg, all_raw_rows


def main():
    parser = argparse.ArgumentParser(description="TierRoute Benchmark Harness")
    parser.add_argument("--split", choices=["test", "dev", "full"], default="test",
                        help="Data split to evaluate on (default: held-out 'test')")
    parser.add_argument("--runs", type=int, default=3, help="Number of repetitions (default: 3)")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature (default: 0.0)")
    parser.add_argument("--no-sweep", action="store_true", help="Skip bias sweeps (evaluate main strategies only)")
    parser.add_argument("--require-all-tiers", action="store_true",
                        help="Abort run if any model tier fails health check instead of failing over")
    args = parser.parse_args()

    cfg = load_config()

    if args.require_all_tiers:
        print("[Health Check] Validating all model tiers before run (--require-all-tiers)...")
        from scripts.health_check import check_models
        healthy = check_models()
        if not healthy:
            print("\nFATAL: --require-all-tiers was specified and at least one model tier failed health check!")
            print("Aborting live benchmark run.")
            sys.exit(1)
        print("[Health Check] All tiers verified healthy!\n")

    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    bench_db = results_dir / f"bench_{cfg.mode}_{args.split}.db"
    bench_db.unlink(missing_ok=True)

    overrides_file = results_dir / "bench_overrides.json"
    router = Router(cfg, Store(bench_db), Overrides(overrides_file))
    router.overrides.update({"global_pin": None, "task_rules": {}, "bias": None})

    tasks, split_desc = load_dataset(args.split)

    # Train classifier strictly on seed prompts + dev set tasks with zero leakage check
    classifier.train_on_split(ROOT)

    print("=" * 80)
    print(f"TierRoute Benchmark | Mode: {cfg.mode.upper()} | Split: {split_desc.upper()}")
    print(f"Replicates: {args.runs} runs | Temperature: {args.temperature} | Max Tokens: 1024")
    print("=" * 80)

    strategies = ["always_strong", "always_cheap", "random", "rules", "classifier"]
    strategy_results = []
    all_raw_csv_rows = []

    for strat in strategies:
        print(f"-> Running strategy: {strat} (x{args.runs} runs)...", end="", flush=True)
        agg, raw_rows = run_benchmark_replicates(router, tasks, strat, bias=0.5,
                                                 n_runs=args.runs, temperature=args.temperature)
        strategy_results.append(agg)
        all_raw_csv_rows.extend(raw_rows)
        print(f" Done! Cost: ${agg['cost_usd']:.5f} | Quality: {agg['quality_wilson_str']} | Truncated: {agg['truncated_count']}")

    base = strategy_results[0]
    for r in strategy_results:
        saving = 100.0 * (1.0 - r["cost_usd"] / base["cost_usd"]) if base["cost_usd"] > 0 else 0.0
        retention = (r["quality"] / base["quality"]) if base["quality"] > 0 else 0.0
        r["cost_saving_vs_strong_pct"] = round(saving, 1)
        r["quality_vs_strong"] = round(retention, 3)

    # Quality-bias sweep for rules AND classifier
    bias_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    rules_sweep = []
    clf_sweep = []

    print("\n-> Running quality-bias sweep for rules router...")
    if not args.no_sweep:
        for b in bias_values:
            print(f"   Rules bias {b:.2f} (x{args.runs})...", end="", flush=True)
            agg, raw_rows = run_benchmark_replicates(router, tasks, "rules", bias=b,
                                                     n_runs=args.runs, temperature=args.temperature)
            saving = 100.0 * (1.0 - agg["cost_usd"] / base["cost_usd"]) if base["cost_usd"] > 0 else 0.0
            agg["cost_saving_vs_strong_pct"] = round(saving, 1)
            rules_sweep.append(agg)
            all_raw_csv_rows.extend(raw_rows)
            print(f" Done! Cost: ${agg['cost_usd']:.5f} | Quality: {agg['quality_wilson_str']}")

        print("\n-> Running quality-bias sweep for ML classifier router...")
        for b in bias_values:
            print(f"   Classifier bias {b:.2f} (x{args.runs})...", end="", flush=True)
            agg, raw_rows = run_benchmark_replicates(router, tasks, "classifier", bias=b,
                                                     n_runs=args.runs, temperature=args.temperature)
            saving = 100.0 * (1.0 - agg["cost_usd"] / base["cost_usd"]) if base["cost_usd"] > 0 else 0.0
            agg["cost_saving_vs_strong_pct"] = round(saving, 1)
            clf_sweep.append(agg)
            all_raw_csv_rows.extend(raw_rows)
            print(f" Done! Cost: ${agg['cost_usd']:.5f} | Quality: {agg['quality_wilson_str']}")
    else:
        print("   (Skipped via --no-sweep)")

    # Save raw CSV
    csv_filename = f"benchmark_{cfg.mode}_{args.split}_raw.csv"
    csv_path = results_dir / csv_filename
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "task_id", "strategy", "bias", "run_idx", "first_model", "final_model",
            "tier", "gold_tier", "correct", "cost", "latency_s", "tokens",
            "finish_reason", "truncated", "escalated", "verified", "answer", "check_type"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_raw_csv_rows)

    # Primary raw CSV alias
    if cfg.mode == "live" and args.split == "test":
        (results_dir / "benchmark_live_raw.csv").write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Save summary JSON
    out_data = {
        "mode": cfg.mode,
        "split": args.split,
        "split_description": split_desc,
        "n_runs": args.runs,
        "temperature": args.temperature,
        "max_tokens": 1024,
        "independence_note": "Temperature-0 repeats evaluate deterministic model outputs and are not independent random samples; Wilson 95% confidence intervals are computed over the N test items evaluated per run.",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": [{"name": m.name, "tier": m.tier, "model": m.model,
                    "price_in_per_m": m.price_in_per_m, "price_out_per_m": m.price_out_per_m}
                   for m in cfg.models],
        "strategies": strategy_results,
        "rules_bias_sweep": rules_sweep,
        "classifier_bias_sweep": clf_sweep
    }
    json_path = results_dir / f"benchmark_{cfg.mode}_{args.split}.json"
    json_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")
    if cfg.mode == "live" and args.split == "test":
        (results_dir / "benchmark_live.json").write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    # Print Summary Table 1: Main Strategy Comparison
    print("\n" + "=" * 115)
    print(f"MAIN STRATEGY COMPARISON ({args.runs}-run mean ± std | Quality: 95% Wilson CI):")
    print(f"Note: Temperature-0 repeats evaluate deterministic model outputs and are not independent random samples.")
    print("-" * 115)
    print(f"{'Strategy':16}{'Cost ($)':>14}{'Cost Save %':>13}{'Quality (x/n [95% CI])':>32}{'Q/Strong':>10}{'Routing Acc':>13}{'Truncated':>11}")
    print("-" * 115)
    for r in strategy_results:
        c_str = f"${r['cost_usd']:.5f}±{r['cost_usd_std']:.5f}"
        q_str = r['quality_wilson_str']
        a_str = f"{r['routing_accuracy']*100:.1f}%"
        print(f"{r['strategy']:16}{c_str:>14}{r['cost_saving_vs_strong_pct']:>12.1f}%{q_str:>32}{r['quality_vs_strong']:>10.3f}{a_str:>13}{r['truncated_count']:>11}")

    # Print Summary Table 2: Per-Model Final Workload Distribution Table (Item 6)
    print("\n" + "=" * 105)
    print("PER-MODEL FINAL WORKLOAD DISTRIBUTION (Sub-tasks handled per model out of N):")
    print("-" * 105)
    print(f"{'Strategy':18}{'local-small (T0)':>22}{'hosted-mid (T1)':>22}{'hosted-strong (T2)':>22}{'Local Share %':>18}")
    print("-" * 105)
    for r in strategy_results:
        fmc = r["final_model_counts"]
        n_tot = r["sub_tasks"]
        t0_c = fmc.get("local-small", 0)
        t1_c = fmc.get("hosted-mid", 0)
        t2_c = fmc.get("hosted-strong", 0)
        loc_share = (t0_c / n_tot * 100) if n_tot > 0 else 0.0
        t0_str = f"{t0_c} ({t0_c/n_tot*100:.1f}%)"
        t1_str = f"{t1_c} ({t1_c/n_tot*100:.1f}%)"
        t2_str = f"{t2_c} ({t2_c/n_tot*100:.1f}%)"
        print(f"{r['strategy']:18}{t0_str:>22}{t1_str:>22}{t2_str:>22}{loc_share:>17.1f}%")
    print("=" * 105)

    # Print Summary Table 3: Quality-Bias Sweep Comparison
    print("\n" + "=" * 105)
    print("QUALITY-BIAS SWEEP COMPARISON:")
    print(f"{'Bias':>6}{'Rules Cost':>14}{'Rules Save%':>13}{'Rules Quality':>24} | {'Clf Cost':>14}{'Clf Save%':>12}{'Clf Quality':>24}")
    print("-" * 105)
    for rw, cw in zip(rules_sweep, clf_sweep):
        print(f"{rw['bias']:>6.2f}"
              f"${rw['cost_usd']:>13.5f}{rw['cost_saving_vs_strong_pct']:>12.1f}%{rw['quality_wilson_str']:>24} | "
              f"${cw['cost_usd']:>13.5f}{cw['cost_saving_vs_strong_pct']:>11.1f}%{cw['quality_wilson_str']:>24}")

    # Generate Publication Plots
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Plot 1: Cost vs Quality Curve (Pareto frontier)
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=180)
        ax.plot([r["cost_usd"] for r in rules_sweep], [r["quality"] * 100 for r in rules_sweep],
                "o-", color="#1f77b4", label="Rules Router (Bias Sweep)", linewidth=2, markersize=6)
        ax.plot([r["cost_usd"] for r in clf_sweep], [r["quality"] * 100 for r in clf_sweep],
                "s--", color="#2ca02c", label="Classifier Router (Bias Sweep)", linewidth=2, markersize=6)

        for r in strategy_results:
            if r["strategy"] in ("always_strong", "always_cheap", "random"):
                m = "^" if r["strategy"] == "always_strong" else ("v" if r["strategy"] == "always_cheap" else "D")
                c = "#d62728" if r["strategy"] == "always_strong" else ("#7f7f7f" if r["strategy"] == "always_cheap" else "#ff7f0e")
                ax.scatter(r["cost_usd"], r["quality"] * 100, marker=m, color=c, s=90, zorder=5, label=f"Baseline: {r['strategy']}")

        ax.set_xlabel("Total Cost (USD)", fontsize=11, fontweight="bold")
        ax.set_ylabel("Quality / Task Accuracy (%)", fontsize=11, fontweight="bold")
        title_suffix = " [SIMULATED]" if cfg.mode == "mock" else f" ({args.split.upper()} set, N={tasks[0]['parts'].__len__() if 'parts' in tasks[0] else len(tasks)})"
        ax.set_title(f"TierRoute: Cost vs Quality Trade-off Curve{title_suffix}", fontsize=12, pad=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(fontsize=9, loc="lower right")
        fig.tight_layout()
        plot_path = results_dir / f"cost_quality_{cfg.mode}.png"
        fig.savefig(plot_path)
        plt.close(fig)

        # Plot 2: Bar Chart - Cost Saving vs Quality Retention
        fig2, ax2 = plt.subplots(figsize=(8, 4.5), dpi=180)
        names = [r["strategy"].replace("_", " ").title() for r in strategy_results]
        savings = [max(0.0, r["cost_saving_vs_strong_pct"]) for r in strategy_results]
        retentions = [r["quality_vs_strong"] * 100 for r in strategy_results]

        x = range(len(names))
        width = 0.35
        ax2.bar([i - width/2 for i in x], savings, width=width, label="Cost Saving vs Strong (%)", color="#10b981")
        ax2.bar([i + width/2 for i in x], retentions, width=width, label="Quality Retention vs Strong (%)", color="#6366f1")

        ax2.set_xticks(list(x))
        ax2.set_xticklabels(names, fontsize=10, fontweight="bold")
        ax2.set_ylabel("Percentage (%)", fontsize=11, fontweight="bold")
        ax2.set_title(f"Cost Savings vs Quality Retention Across Strategies ({cfg.mode.upper()} mode)", fontsize=12, pad=10)
        ax2.set_ylim(0, 115)
        ax2.grid(True, axis="y", linestyle="--", alpha=0.5)
        ax2.legend(fontsize=9, loc="upper right")
        fig2.tight_layout()
        bar_plot_path = results_dir / f"savings_retention_{cfg.mode}.png"
        fig2.savefig(bar_plot_path)
        plt.close(fig2)

        print(f"\n[Artifacts Generated]")
        print(f"  Plots: {plot_path.name}, {bar_plot_path.name}")
        print(f"  CSV:   {csv_path.name}")
        print(f"  JSON:  {json_path.name}")
    except Exception as e:  # noqa: BLE001
        print("Plot generation error:", e)


if __name__ == "__main__":
    main()
