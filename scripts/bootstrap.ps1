$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root '.venv'

if (-not (Test-Path $venv)) {
    python -m venv $venv
}

$python = Join-Path $venv 'Scripts\python.exe'
Push-Location $root
& $python -m pip install --upgrade pip
& $python -m pip install -e '.[dev]'
Pop-Location

