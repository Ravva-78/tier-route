#!/usr/bin/env python3
"""Health check script for TierRoute model pool.
Sends one short prompt to each model in config/models.yaml (or configured via env),
measuring success, latency, token counts, and printing detailed diagnostics.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tierroute.config import load_config
from tierroute.providers import Provider


def check_models():
    cfg = load_config()
    print("=" * 65)
    print(f"TierRoute Health Check (mode: {cfg.mode})")
    print("=" * 65)

    test_prompt = "Reply with exactly: 'OK'"
    overall_ok = True

    for spec in cfg.models:
        print(f"\n[Tier {spec.tier}] {spec.name}")
        print(f"  Model ID:  {spec.model}")
        print(f"  Base URL:  {spec.base_url}")
        print(f"  API Key:   {'Configured' if (spec.api_key_env and os.getenv(spec.api_key_env)) else ('None required' if not spec.api_key_env else 'MISSING')}")

        provider = Provider(spec, mode=cfg.mode)
        t0 = time.time()
        res = provider.generate(test_prompt, system="Be concise.", max_tokens=32, temperature=0.0)
        lat = time.time() - t0

        if res.error:
            overall_ok = False
            print(f"  Status:    FAILED [X]")
            print(f"  Error:     {res.error}")
        else:
            print(f"  Status:    SUCCESS [OK]")
            print(f"  Response:  {res.text.strip()[:60]}")
            print(f"  Tokens:    {res.tokens_in} prompt + {res.tokens_out} completion = {res.tokens_in + res.tokens_out} total")
            print(f"  Latency:   {res.latency_s:.3f}s (wall: {lat:.3f}s)")

    print("\n" + "=" * 65)
    if overall_ok:
        print("ALL CONFIGURED MODELS HEALTHY AND OPERATIONAL")
    else:
        print("SOME MODELS FAILED HEALTH CHECK (See details above)")
    print("=" * 65)
    return overall_ok


if __name__ == "__main__":
    check_models()
