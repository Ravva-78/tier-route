#!/usr/bin/env python3
"""Smoke test against a RUNNING gateway (default http://localhost:8000): 6 prompts, prints each routing decision.
Usage: python scripts/smoke_test.py [base_url]. Restores admin overrides when done."""
import sys

import httpx

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
NO_STRONG = "--no-strong" in sys.argv  # only local/mid prompts: never touches hosted-strong
BASE = (ARGS[0] if ARGS else "http://localhost:8000").rstrip("/")
C = httpx.Client(timeout=180)


def show(title, out):
    print(f"\n=== {title} ===")
    for p in out["parts"]:
        chain = " -> ".join(a["model"] + ("" if a["ok"] else f" [{a['check']}]") for a in p["attempts"])
        print(f"  part {p['part_idx']}: first={p['first_model']} final={p['final_model']} escalated={bool(p['escalated'])} "
              f"override={p['override_by']} cost=${p['cost']:.6f} latency={p['latency_s']:.2f}s")
        print(f"    chain : {chain}")
        print(f"    reason: {p['reason'][:150]}")
        print(f"    answer: {p['answer'].strip()[:100]!r}")
    print(f"  total cost ${out['total_cost']:.6f} (all-strong estimate ${out['est_strong_cost']:.6f})")


def route(**kw):
    r = C.post(BASE + "/api/route", json=kw)
    r.raise_for_status()
    return r.json()


try:
    models = C.get(BASE + "/api/models").json()
except Exception as e:  # noqa: BLE001
    sys.exit(f"Gateway not reachable at {BASE} ({type(e).__name__}). Start it with run_dashboard.bat")
print("mode:", models["mode"], "| models:", ", ".join(m["name"] for m in models["models"]))
saved = C.get(BASE + "/api/overrides").json()
C.post(BASE + "/api/overrides", json={"global_pin": None, "task_rules": {}, "bias": None})
try:
    show("1. easy", route(prompt="What is the capital of France?", split=False))
    if NO_STRONG:
        show("2. medium (routes to hosted-mid)", route(prompt="Summarize in one sentence why the sky is blue.", split=False))
        show("3. multi-part, easy parts", route(prompt="1. Convert to uppercase: 'hello'\n2. What is the capital of Japan?\n3. List 3 primary colors."))
        show("4. forced escalation local -> mid (cascade; local draft must fail the judge)",
             route(prompt="What is 48271 * 91237? Reply with just the number.", strategy="cascade", split=False))
        show("5. user override (force_model=hosted-mid)", route(prompt="Convert to uppercase: 'abc'", force_model="hosted-mid", split=False))
        print("\nSKIPPED (need hosted-strong): hard prompt; override to hosted-strong")
    else:
        show("2. hard", route(prompt="Prove step by step why merge sort is O(n log n) and compare its trade-offs with quicksort.", split=False))
        show("3. multi-part", route(prompt="1. Convert to uppercase: 'hello'\n2. Translate to French: Good morning.\n3. What is 17*23?"))
        show("4. forced escalation (cascade + heuristic verifier; every tier is told to answer 'I'm not sure', which that verifier rejects)",
             route(prompt="Reply with exactly these words and nothing else: I'm not sure", strategy="cascade", split=False,
                   verifier="heuristic"))
        show("5. user override (force_model=hosted-strong)",
             route(prompt="Convert to uppercase: 'abc'", force_model="hosted-strong", split=False))
    C.post(BASE + "/api/overrides", json={"task_rules": {"translation": "hosted-mid"}})
    show("6. admin rule (translation -> hosted-mid)", route(prompt="Translate to Spanish: Where is the station?", split=False))
finally:
    C.post(BASE + "/api/overrides", json={"global_pin": saved.get("global_pin"), "task_rules": saved.get("task_rules") or {},
                                          "bias": saved.get("bias")})
print("\nsmoke test finished (overrides restored)")
