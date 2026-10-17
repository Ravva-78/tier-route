# Status (written 2026-10-17 19:25 IST) - live evaluation NOT finished

Done and committed: Phase 1 (no-leak routing + tests), Phase 2 code (verifiers a-d; e not run), Phase 3 (v3 frozen,
SHA-256 `4a5af81ef68c2003bd4f85978f09af00cb03297c08489d8cad2733282026606c`, committed before any model call),
Phase 4 runner (`benchmark/run_final.py`), Phase 5 (health check, smoke test, run_dashboard.bat, QUICKSTART.md).

**Blocker: Groq `openai/gpt-oss-120b` free-tier cap of 200,000 tokens/day (rolling 24 h).** The audit and earlier
runs consumed it (`Used 199638` at 2026-10-17 19:2x IST). Every strong-tier call now returns HTTP 429 until old usage
ages out of the window (roughly 2026-10-18 morning for the first ~100k tokens). The runners retry forever with 60 s
backoff and cache every successful call, so they resume without re-sampling.

Pipeline running in the background: `select_verifier.py` (Phase 2 on DEV) then `run_final.py` (Phase 4 on v3).
If the machine restarts, resume with:
    python benchmark/select_verifier.py && python benchmark/run_final.py
Remaining strong-tier need is about 100k tokens (DEV ~30k, v3 low ~30k, v3 default ~40k).
No results are reported until those runs finish. `results/final/problems.log` logs every 429.
