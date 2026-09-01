@echo off
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --disable-pip-version-check -r requirements.txt
python -m server.self_test
pause
