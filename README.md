# TierRoute: cost-aware LLM router

> Step-by-step setup: see **QUICKSTART.md**. Final, leak-free results: `results/final/RESULTS_FINAL.md`. Older results are indexed in `results/README.md` (several are invalid).

Routes each request to the cheapest model that can handle it: local model, mid hosted, strong hosted.
Splits multi-part requests, verifies answers, escalates weak ones, logs every decision, and lets users/admins override.

## Setup (Windows)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests            # 11 tests, runs offline in mock mode
```

## Try it offline (mock mode, answers are SIMULATED)
```
uvicorn app:app --reload          # open http://127.0.0.1:8000
python benchmark/run_benchmark.py # prints strategy comparison + writes results/
```

## Go live (real models)
1. Local tier: install Ollama, then `ollama pull llama3.2:3b` (about 2 GB, fits a 4 GB GPU).
   On Colab/Kaggle instead: run Ollama there, expose it with a tunnel, and set that URL as `base_url` of `local-small`.
2. Free API key at console.groq.com, then in the terminal: `set GROQ_API_KEY=your_key`
3. Check current model names and prices on the provider pages, then edit `config/models.yaml`.
4. `set TIERROUTE_MODE=live` then run the same two commands as above.

## Where things are
| Piece | File |
|---|---|
| Model pool, prices | config/models.yaml |
| Complexity analyser | tierroute/analyzer.py |
| Request splitter / merger | tierroute/splitter.py, merger.py |
| Router, escalation, overrides | tierroute/router.py |
| Answer verifier | tierroute/verifier.py |
| Decision log (SQLite) | tierroute/store.py |
| API + dashboard | app.py, static/index.html |
| Benchmark (strategies + cost/quality sweep) | benchmark/run_benchmark.py, benchmark/tasks.json |

## Before you report numbers
- Report only live-mode results. Mock mode simulates answers to test the harness.
- Thresholds in `router.py` were tuned on the 22 starter tasks. Expand the set (40+), tune on part, report on held-out prompts.
- Prices in the config are placeholders from memory. Verify them.

## 5-minute demo
Prerequisites done once (see QUICKSTART.md): Ollama running with `llama3.2:3b`, `GROQ_API_KEY` in `.env`, `pip install -r requirements.txt`.

| Min | What to do | What to point out |
|---|---|---|
| 0:00 | `python scripts/health_check.py` | all three tiers answer (local Ollama, Groq mid, Groq strong); prices come from `config/models.yaml` |
| 0:30 | `run_dashboard.bat` (opens http://localhost:8000) | dashboard, model pool with prices, strategy and bias controls |
| 1:00 | Send "What is the capital of France?" | routed to `local-small`, cost $0, reason shown |
| 1:45 | Send a hard prompt ("Prove step by step why merge sort is O(n log n) ...") | goes straight to `hosted-strong`; compare cost with the all-strong estimate |
| 2:30 | Send a 3-item numbered request | split into parts, each routed on its own, merged answer |
| 3:15 | Strategy `cascade` + prompt "Reply with exactly these words and nothing else: I'm not sure" | verifier flags the answer, request escalates tier by tier (see the attempt chain) |
| 4:00 | Pin a model (force_model) and add an admin rule (translation -> hosted-mid) | overrides are logged with who applied them |
| 4:30 | `python scripts/smoke_test.py` (or show saved `results/final/smoke_live.txt`) and `python -m pytest tests -q` | the six scenarios above as a script; 46 tests including the no-leak guards |
| 5:00 | Open `results/final/RESULTS_FINAL.md` | the honest result: what the router saves and what it costs in quality, with confidence intervals |

If Groq is rate limited during the demo (free tier: 8,000 tokens/minute, 200,000 tokens/day on the strong model) show the saved `results/final/smoke_live.txt` instead of retrying live.
