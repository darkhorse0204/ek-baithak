@echo off
REM Ek Baithak: one-click start. Opens http://localhost:8000
cd /d %~dp0
if not exist .env (
  echo GEMINI_API_KEY=> .env
  echo Created an empty .env. Add your Gemini key to it, or the app runs in offline mode.
)
start "" http://localhost:8000
python -m uvicorn app.main:app --port 8000
