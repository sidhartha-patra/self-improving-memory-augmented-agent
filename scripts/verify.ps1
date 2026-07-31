$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

Push-Location $root
& $python -m ruff check .
& $python -m mypy src
& $python -m pytest
& $python scripts/run_evals.py
Pop-Location

