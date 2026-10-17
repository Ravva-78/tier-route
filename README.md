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
