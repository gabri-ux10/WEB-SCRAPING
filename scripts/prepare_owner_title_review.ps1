$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$inputPath = Join-Path $root 'data/reference/cs_job_title_manual_review_v2.csv'
$disagreementPath = Join-Path $root 'data/reference/cs_job_title_disagreements_v2.csv'
$ownerPath = Join-Path $root 'data/reference/cs_job_title_owner_review_v2.csv'
$rows = Import-Csv -LiteralPath $inputPath
$disagreements = [System.Collections.Generic.List[object]]::new()
$agreed = [System.Collections.Generic.List[object]]::new()
foreach ($row in $rows) {
    $rule = if ($row.expected_category_id_unverified -in @('C1','C2','C3','C4','C5','C6','C7')) { "$($row.expected_category_id_unverified)/$($row.expected_sub_domain_id_unverified)" } else { $row.expected_category_id_unverified }
    $type = ''
    if ($rule -eq $row.judge_label) { $type = 'agreement' }
    elseif ($rule -eq 'U' -and $row.judge_label -eq 'N') { $type = 'Unclassified to Non-Tech' }
    elseif ($rule -eq 'U' -and $row.judge_label -match '^C[1-7]/S\d+$') { $type = 'Unclassified to specific sub-domain' }
    elseif ($rule -eq 'C5/S50' -and $row.judge_label -eq 'U') { $type = 'Product title tie-break to Unclassified' }
    elseif ($rule -eq 'C5/S50' -and $row.judge_label -eq 'N') { $type = 'Wrong product alias; Non-Tech' }
    elseif ($rule -eq 'C1/S03' -and $row.judge_label -eq 'C1/S01') { $type = 'Software role sub-domain tie-break' }
    else { $type = 'Other label disagreement' }

    $item = [pscustomobject]@{
        raw_title=$row.raw_title; rule_label=$rule; judge_label=$row.judge_label
        judge_confidence=$row.judge_confidence; disagreement_type=$type; review_type='disagreement'; owner_decision=''
    }
    if ($type -eq 'agreement') { $agreed.Add($item) } else { $disagreements.Add($item) }
}
$disagreements | Export-Csv -LiteralPath $disagreementPath -NoTypeInformation -Encoding utf8BOM
$spotChecks = @($agreed | Get-Random -Count ([Math]::Min(15, $agreed.Count)) | ForEach-Object {
    [pscustomobject]@{raw_title=$_.raw_title;rule_label=$_.rule_label;judge_label=$_.judge_label;judge_confidence=$_.judge_confidence;disagreement_type='';review_type='spot-check';owner_decision=''}
})
@($disagreements) + $spotChecks | Export-Csv -LiteralPath $ownerPath -NoTypeInformation -Encoding utf8BOM
$disagreements | Group-Object disagreement_type | Sort-Object Name | ForEach-Object { Write-Output ("{0}: {1}" -f $_.Name,$_.Count) }
Write-Output "Disagreements: $($disagreements.Count); random agreed spot-check rows: $($spotChecks.Count); owner_decision fields left blank."
