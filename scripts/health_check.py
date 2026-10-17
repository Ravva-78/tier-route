#!/usr/bin/env python3
"""Health check: Ollama (local tier), Groq (hosted tiers) and, if enabled, Jev (OpenRouter).
Sends one tiny prompt to every model in config/models.yaml. Never prints API keys. Exit code 0 = all required OK."""
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tierroute.config import load_config
from tierroute.providers import Provider


def check_ollama(spec) -> bool:
    base = spec.base_url.rstrip("/").removesuffix("/v1")
    try:
        tags = [m["name"] for m in httpx.get(base + "/api/tags", timeout=5).json().get("models", [])]
    except Exception as e:  # noqa: BLE001
        print(f"  Ollama:    NOT REACHABLE at {base} ({type(e).__name__}). Start it with `ollama serve`.")
        return False
    if spec.model not in tags:
        print(f"  Ollama:    running, but model '{spec.model}' is not pulled. Run: ollama pull {spec.model}")
        return False
    print(f"  Ollama:    running, model '{spec.model}' present")
    return True


def check_jev() -> None:
    if os.getenv("TIERROUTE_ENABLE_JEV") != "1":
        print("\n[Jev] disabled (optional; set TIERROUTE_ENABLE_JEV=1 and OPENROUTER_API_KEY to enable) - skipped")
    elif not os.getenv("OPENROUTER_API_KEY"):
        print("\n[Jev] enabled but OPENROUTER_API_KEY is missing - skipped")
    else:
        print("\n[Jev] key present; the Jev verifier is not implemented in this release - skipped")


def main() -> bool:
    cfg = load_config()
    print("=" * 65 + f"\nTierRoute health check (mode: {cfg.mode})\n" + "=" * 65)
    ok_all = True
    for spec in cfg.models:
        print(f"\n[Tier {spec.tier}] {spec.name}  ({spec.model} @ {spec.base_url})")
        if spec.api_key_env and not os.getenv(spec.api_key_env):
            print(f"  API key:   MISSING (set {spec.api_key_env} in .env)")
            ok_all = False
            continue
        if not spec.api_key_env and "11434" in spec.base_url and not check_ollama(spec):
            ok_all = False
            continue
        t0 = time.time()
        res = Provider(spec, mode=cfg.mode).generate("Reply with exactly: OK", max_tokens=64, temperature=0.0)
        if res.error:
            ok_all = False
            print(f"  Status:    FAILED - {res.error}")
        else:
            print(f"  Status:    OK  reply={res.text.strip()[:30]!r} tokens={res.tokens_in}+{res.tokens_out} "
                  f"latency={time.time() - t0:.2f}s")
    check_jev()
    print("\n" + ("ALL REQUIRED MODELS HEALTHY" if ok_all else "SOME CHECKS FAILED (see above)"))
    return ok_all


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
