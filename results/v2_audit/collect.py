"""Collect real per-(task, tier) responses for 3 hosted configs. Resumable. Never prints env/keys.
Configs: A=1024/default, B=4096/default, C=4096/reasoning_effort=low (hosted tiers only).
A reuses the original run's cache (same settings); tier 0 (local) is config-independent and reused from cache."""
import json, os, sys, time
sys.path.insert(0, ".")
from tierroute.config import load_config
from tierroute.providers import Provider

CACHE = "results/benchmark_v2_call_cache.json"
OUT = "results/v2_audit/responses_{}.json"
CFGS = {"A_1024_default": (1024, None), "B_4096_default": (4096, None), "C_4096_low": (4096, {"reasoning_effort": "low"})}

cfg = load_config()
specs = {m.tier: m for m in cfg.models}
prov = {t: Provider(m, mode="live") for t, m in specs.items()}
tasks = {t["id"]: t for t in json.load(open("benchmark/tasks_v2.json", encoding="utf-8"))}
test_ids = json.load(open("benchmark/split_v2.json"))["test_ids"]
cache = {}
for k, v in json.load(open(CACHE, encoding="utf-8")).items():
    p, m = k.split("|||", 1)
    cache[(p, m)] = v

def rec(res):
    return dict(text=res.text, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                latency_s=res.latency_s, error=res.error, finish_reason=res.finish_reason)

for name, (mt, extra) in CFGS.items():
    path = OUT.format(name)
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for tid in test_ids:
        for tier in (0, 1, 2):
            key = f"{tid}|{tier}"
            if key in data and not data[key].get("error"):
                continue
            prompt, mname = tasks[tid]["prompt"], specs[tier].name
            if (tier == 0 or name.startswith("A")) and (prompt, mname) in cache:
                r = dict(cache[(prompt, mname)]); r["source"] = "original_cache"
            else:
                for _try in range(8):  # patient retry on 429 (provider's own backoff is only ~15s)
                    res = prov[tier].generate(prompt, max_tokens=(1024 if tier == 0 else mt), temperature=0.0,
                                              extra_body=(extra if tier > 0 else None))
                    if not (res.error and "429" in res.error):
                        break
                    time.sleep(30)
                r = rec(res); r["source"] = "live_audit"
                time.sleep(0.5)
            data[key] = r
            json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    errs = [k for k, v in data.items() if v.get("error")]
    print(name, "entries", len(data), "errors", len(errs), errs[:5], flush=True)
