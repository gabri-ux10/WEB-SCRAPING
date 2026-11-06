$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envPath = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Project .env is missing; refusing to create it.' }
$lines = [System.Collections.Generic.List[string]]::new()
$lines.AddRange([string[]](Get-Content -LiteralPath $envPath))
$matches = @($lines | Where-Object { $_ -match '^\s*(?:export\s+)?DATABASE_URL\s*=' })
if ($matches.Count -ne 1) { throw 'Expected exactly one DATABASE_URL key in .env; no file changes made.' }
$lineIndex = -1
for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\s*(?:export\s+)?DATABASE_URL\s*=') { $lineIndex = $i; break } }
$oldLine = $lines[$lineIndex]
$value = ($oldLine -split '=',2)[1].Trim().Trim('"').Trim("'")
$uriPattern = '^(?<prefix>postgresql\+asyncpg://(?<user>[^:/@]+):)(?<password>[^@]*)@(?<host>\[[^\]]+\]|[^:/]+)(?<port>:\d+)?/(?<database>[^?#]+)(?<suffix>[?#].*)?$'
if ($value -notmatch $uriPattern) { throw 'DATABASE_URL format is not supported; no file changes made.' }

$securePassword = Read-Host 'Enter the password for the configured PostgreSQL role (input hidden)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $encodedPassword = [Uri]::EscapeDataString($plainPassword)
    $newValue = "$($Matches.prefix)$encodedPassword@$($Matches.host)$($Matches.port)/$($Matches.database)$($Matches.suffix)"
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $plainPassword = $null
    $securePassword.Dispose()
}

$lines[$lineIndex] = "DATABASE_URL=$newValue"
$tempPath = Join-Path $root '.env.key-update.tmp'
try {
    [IO.File]::WriteAllLines($tempPath, $lines, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $envPath -Force
} finally {
    if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath -Force }
}
Write-Output 'Updated only DATABASE_URL in .env. The password was not printed and no database connection was attempted.'
