$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envPath = Join-Path $root '.env'
$composePath = Join-Path $root 'docker-compose.yml'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Existing .env is missing; refusing to create or overwrite it.' }
if (Select-String -LiteralPath $envPath -Pattern '^\s*DATABASE_URL\s*=' -Quiet) {
    throw 'DATABASE_URL already exists; leaving .env unchanged.'
}
$definition = Select-String -LiteralPath $composePath -Pattern '^\s*DATABASE_URL\s*:\s*(.+)$' | Select-Object -First 1
if (-not $definition) { throw 'Compose DATABASE_URL setting was not found; .env left unchanged.' }
$url = $definition.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
if ($url.Contains('$') -or $url -notmatch '^postgresql\+asyncpg://[^@]+@db:\d+/[^\s]+$') {
    throw 'Compose URL is not a literal host-side connection setting; .env left unchanged.'
}
$url = $url -replace '@db:', '@localhost:'
Add-Content -LiteralPath $envPath -Value "DATABASE_URL=$url" -Encoding utf8
Write-Output 'Added the missing DATABASE_URL key from the Compose settings using localhost; value was not displayed. No database connection was attempted.'
