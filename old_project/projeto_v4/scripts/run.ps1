param(
    [int]$Port = 8080
)

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1

pip install -e ./projeto_v3

uvicorn projeto_v3.app.main:app --host 0.0.0.0 --port $Port
