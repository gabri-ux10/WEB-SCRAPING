$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$path = Join-Path $root 'data/reference/source_terms_decisions_v2.csv'
$rows = Import-Csv -LiteralPath $path
$conditions = 'Non-commercial academic use; credit the source in reports; do not redistribute raw posting text; at most one request per host per second.'
foreach ($row in $rows) {
    $row | Add-Member -NotePropertyName conditions -NotePropertyValue $conditions -Force
    if ($row.source_id -eq 'workable') {
        $row.verification_status = 'RECHECK'
        $row.terms_decision = 'blocked_evidence_confirmation'
        $row.notes = 'Evidence URL needs confirmation before this source is enabled. ' + $row.notes
    }
    if ($row.source_id -eq 'jooble') {
        $row.terms_decision = 'not_viable_lifetime_call_limit'
        $row.notes = 'Not viable (500 lifetime calls per regional key). ' + $row.notes
    }
}
$rows | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding utf8BOM
