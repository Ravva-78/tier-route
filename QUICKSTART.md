# TierRoute quickstart (Windows, PowerShell or cmd)

Needs Python 3.11+, git, a free Groq API key (https://console.groq.com) and ~3 GB of disk for the local model.

1. **Install Ollama and pull the local model**
   ```powershell
   winget install Ollama.Ollama
   ollama pull llama3.2:3b
   ollama serve        # skip if the Ollama tray app is already running
   ```
2. **Create `.env`** (it is git-ignored; never commit it)
   ```powershell
   copy .env.example .env
   notepad .env        # set GROQ_API_KEY=<your key> and TIERROUTE_MODE=live
   ```
3. **Install requirements**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Run the tests** (offline, no API calls, includes the no-leak guards)
   ```powershell
   python -m pytest tests -q
   ```
5. **Check the models are reachable**
   ```powershell
   python scripts/health_check.py
   ```
6. **Start the server and open the dashboard**
   ```powershell
   run_dashboard.bat   # serves http://localhost:8000 and opens the browser
   ```
7. **Smoke test** (second terminal, server running): sends 6 prompts (easy, hard, multi-part, forced escalation,
   user override, admin rule) and prints each routing decision.
   ```powershell
   python scripts/smoke_test.py
   ```
8. **Reproduce the benchmark** (live calls; Groq's free tier rate-limits, so expect 429 back-off pauses and
   an hour or more; calls are cached, so a re-run resumes):
   ```powershell
   python benchmark/select_verifier.py   # Phase 2: choose the verifier on the v2 DEV set
   python benchmark/validate_v3.py       # checks the frozen v3 file (SHA-256 in benchmark/tasks_v3.sha256)
   python benchmark/run_final.py         # Phase 4: single run on v3 -> results/final/v3_tables.md
   ```

## Docker (optional)
```powershell
docker compose up --build
docker exec tierroute-local-engine ollama pull llama3.2:3b   # first run only
```
The compose file points the gateway at the `local-ollama` container through `TIERROUTE_LOCAL_BASE_URL`.
Put `GROQ_API_KEY` in your shell or in a `.env` next to `docker-compose.yml`.

## Troubleshooting
* `Ollama NOT REACHABLE` - start `ollama serve`; check `curl http://localhost:11434/api/tags`.
* `HTTP 429` from Groq - the free tier allows about 8,000 tokens/minute and 1,000 requests/day per model; the
  benchmark code backs off and retries. Wait and re-run; cached calls are not repeated.
* Never paste your `.env` into chat or commit it.
