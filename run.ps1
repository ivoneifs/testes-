Set-Location $PSScriptRoot
if (-not (Test-Path '.venv')) { py -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --disable-pip-version-check -r requirements.txt
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Start-Process 'http://127.0.0.1:8000'
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
