@echo off
setlocal
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --disable-pip-version-check -r requirements.txt
if not exist .env copy /Y .env.example .env >nul
start "" http://127.0.0.1:8000
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
pause
