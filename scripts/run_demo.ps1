$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

Push-Location $root
& $python -m self_improving_memory_augmented_agent run 'remember semantic retention 30 tags: incident,latency Lead with customer impact for latency incidents.' --auto-approve --json-output
& $python -m self_improving_memory_augmented_agent run 'retrieve latency incidents' --json-output
& $python -m self_improving_memory_augmented_agent run 'reflect on latency incidents' --json-output
& $python -m self_improving_memory_augmented_agent run 'forget expired memories' --json-output
Pop-Location
