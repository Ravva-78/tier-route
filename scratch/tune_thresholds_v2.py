import json
import numpy as np
from tierroute.analyzer import analyze

def tune_thresholds(dev_profile_path="results/benchmark_v2_dev_profile.json"):
    with open(dev_profile_path, "r", encoding="utf-8") as f:
        dev_profile = json.load(f)

    items = []
    for tid, data in dev_profile.items():
        feat = analyze(data["prompt"])
        items.append({
            "id": tid,
            "category": data["category"],
            "score": feat["score"],
            "oracle_tier": data["oracle_tier"]
        })

    print(f"Loaded {len(items)} dev items for threshold tuning.")

    # Grid search for best threshold pair (T1, T2)
    # T1 separates Tier 0 and Tier 1
    # T2 separates Tier 1 and Tier 2
    best_acc = -1.0
    best_pair = None
    results = []

    for t1 in np.linspace(0.15, 0.50, 36):
        for t2 in np.linspace(0.55, 0.85, 31):
            if t1 >= t2:
                continue
            correct = 0
            for item in items:
                s = item["score"]
                if s < t1:
                    pred_tier = 0
                elif s < t2:
                    pred_tier = 1
                else:
                    pred_tier = 2
                if pred_tier == item["oracle_tier"]:
                    correct += 1
            acc = correct / len(items)
            results.append((acc, round(t1, 3), round(t2, 3)))
            if acc > best_acc:
                best_acc = acc
                best_pair = (round(t1, 3), round(t2, 3))

    results.sort(key=lambda x: x[0], reverse=True)
    print(f"Top 5 threshold pairs on Dev Set:")
    for acc, t1, t2 in results[:5]:
        print(f"  T1={t1:.3f}, T2={t2:.3f} -> Dev Accuracy = {acc*100:.2f}%")

    print(f"\nOptimal Tuned Thresholds for V2: T1={best_pair[0]}, T2={best_pair[1]} (Acc: {best_acc*100:.2f}%)")
    return best_pair, best_acc

if __name__ == "__main__":
    tune_thresholds()
