import csv
import statistics
from collections import defaultdict
from pathlib import Path

raw_rows = list(csv.DictReader(open("results/benchmark_live_raw.csv", encoding="utf-8")))

# The 5 primary strategies evaluated at bias 0.5
strategies = ["always_strong", "always_cheap", "random", "rules", "classifier"]

print(f"Total rows in CSV: {len(raw_rows)}")

# Filter to primary strategy runs (bias 0.5)
strat_rows = {s: [] for s in strategies}
for r in raw_rows:
    s = r["strategy"]
    b = float(r["bias"])
    if s in strat_rows and b == 0.5:
        strat_rows[s].append(r)

print("Rows per strategy at bias 0.5:")
for s, rows in strat_rows.items():
    print(f"  {s:15}: {len(rows)} rows")

print("\n--- Latency summary ---")
for s in strategies:
    rows = strat_rows[s]
    lats = [float(r["latency_s"]) for r in rows]
    total_time = sum(lats)
    mean_lat = statistics.mean(lats)
    median_lat = statistics.median(lats)
    
    # Split by model
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["final_model"]].append(float(r["latency_s"]))
        
    print(f"\nStrategy: {s} (N={len(rows)})")
    print(f"  Overall: Mean = {mean_lat:.3f}s, Median = {median_lat:.3f}s, Total = {total_time:.3f}s")
    for m in ["local-small", "hosted-mid", "hosted-strong"]:
        m_lats = by_model[m]
        if m_lats:
            print(f"    {m:15}: n={len(m_lats):2}, Mean = {statistics.mean(m_lats):.3f}s, Median = {statistics.median(m_lats):.3f}s, Total = {sum(m_lats):.3f}s")
        else:
            print(f"    {m:15}: n= 0, Mean = N/A, Median = N/A, Total = 0.000s")
