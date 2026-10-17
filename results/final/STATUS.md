# Status (updated 2026-10-17 20:15 IST)

Done: Phases 1, 3, 5 (see git log); Phase 2 DEV verifier selection finished -> `selected_verifier.json` = judge, threshold 0.5
(`verifier_selection.md`); live health check OK; live smoke test saved (`smoke_live.txt`, partly rate-limited).

**Blocked: the single v3 run (`benchmark/run_final.py`, running in the background).** Groq `openai/gpt-oss-120b` allows
200,000 tokens per rolling 24 h; the latest response said `Used 199720` at 20:14 IST. Each strong-tier call waits and retries
(60 s backoff, calls cached, nothing re-sampled or filled in). Tokens free up only as earlier usage ages past 24 h; the large
earlier batches (v2 follow-up on Oct 17 morning, audit on Oct 17 14:00-16:30 IST) free up roughly Oct 18 morning to afternoon IST.
Still needed from the strong tier: about 70k tokens (v3 low-effort run about 30k, always_strong 4096/default baseline about 40k).
`results/final/v3_tables.md` appears when the run completes; then write `RESULTS_FINAL.md` (not yet written: no numbers yet).
Resume after a restart: `python benchmark/run_final.py` (selection already done; do not re-run it).
