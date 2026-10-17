@echo off
rem Starts the TierRoute gateway + dashboard on http://localhost:8000 (needs: pip install -r requirements.txt)
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
start "" http://localhost:8000
python -m uvicorn app:app --host 127.0.0.1 --port 8000
