$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $Root '.env'))) { throw 'Missing .env. Restore required keys by key only; do not overwrite the file.' }
Push-Location $Root
try {
    $ProjectPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $ProjectPython) {
        & $ProjectPython -m app.v2.local_runner
    } else {
        python -m app.v2.local_runner
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }
