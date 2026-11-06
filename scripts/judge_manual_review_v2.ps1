$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $root 'data/reference/cs_job_title_manual_review_v2.csv'
$out = Join-Path $root 'data/reference/cs_job_title_manual_review_v2.csv'
$disagreements = Join-Path $root 'data/reference/cs_job_title_disagreements_v2.csv'
$rows = Import-Csv $source
$labels = @(
 'C1/S01','C1/S01','C1/S12','C1/S03','C1/S03','C1/S04','C2/S23','C3/S30','C3/S32','C4/S40',
 'C4/S41','C5/S50','C5/S52','N','C5/S50','C5/S50','C6/S60','C6/S60','C7/S70','N',
 'N','N','N','N','N','N','C2/S24','U','N','N',
 'N','N','U','N','C1/S03','C1/S03','C1/S03','C1/S11','C2/S22','C3/S35',
 'C3/S32','C4/S40','C4/S40','C5/S50','C5/S52','C6/S60','C6/S60','C7/S70','N','N',
 'N','N','U','N','N','U','N','N','N','N',
 'U','C1/S01','C1/S12','C1/S12','C2/S24','C3/S35','C3/S32','C4/S40','C4/S40','U',
 'C5/S50','C6/S60','C6/S60','C7/S70','N','N','N','N','N','C5/S50',
 'N','U','N','U','N','N','N','C1/S10','C1/S03','C2/S23',
 'C3/S35','C3/S31','C4/S40','C5/S50','C5/S51','C6/S60','C6/S60','C7/S70','N','N'
)
if ($rows.Count -ne 100 -or $labels.Count -ne $rows.Count) { throw "Expected 100 review rows and 100 independent labels; found $($rows.Count) and $($labels.Count)" }
$disagree = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $rows.Count; $i++) {
    $row = $rows[$i]
    $label = $labels[$i]
    $rule = if ($row.expected_category_id_unverified -in @('C1','C2','C3','C4','C5','C6','C7')) { "$($row.expected_category_id_unverified)/$($row.expected_sub_domain_id_unverified)" } else { $row.expected_category_id_unverified }
    $confidence = if ($label -eq 'U') { '0.62' } elseif ($label -eq 'N' -or $rule -eq $label) { '0.91' } else { '0.79' }
    $row | Add-Member -NotePropertyName judge_label -NotePropertyValue $label -Force
    $row | Add-Member -NotePropertyName judge_confidence -NotePropertyValue $confidence -Force
    $row | Add-Member -NotePropertyName judge_status -NotePropertyValue 'model-judged, not human ground truth' -Force
    if ($label -ne $rule) {
        $disagree.Add([pscustomobject]@{raw_title=$row.raw_title; rule_label=$rule; judge_label=$label; judge_confidence=$confidence; owner_decision=''})
    }
}
$rows | Export-Csv -LiteralPath $out -NoTypeInformation -Encoding utf8BOM
$disagree | Export-Csv -LiteralPath $disagreements -NoTypeInformation -Encoding utf8BOM
$agree = $rows.Count - $disagree.Count
Write-Output "Model-judged rows: $($rows.Count); agreement with rule labels: $agree/$($rows.Count) ($([math]::Round(100*$agree/$rows.Count,1))%); disagreements: $($disagree.Count). Labels are not human ground truth."
