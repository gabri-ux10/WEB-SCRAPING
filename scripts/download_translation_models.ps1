$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:HF_HOME = Join-Path $Root 'models/hf'
New-Item -ItemType Directory -Force -Path $env:HF_HOME | Out-Null
@('de','fr','es','pt','it','nl','ja','zh') | ForEach-Object {
    hf download "Helsinki-NLP/opus-mt-$($_)-en"
    if ($LASTEXITCODE -ne 0) { throw "Model download failed: opus-mt-$($_)-en" }
}
