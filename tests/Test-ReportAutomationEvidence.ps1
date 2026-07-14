[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Join-Path $repoRoot 'projects\bi-delivery-pilot'
$script:passed = 0
$script:failed = 0

function Assert-True {
    param([bool]$Condition, [string]$Message)

    if ($Condition) {
        $script:passed++
        Write-Host "PASS: $Message" -ForegroundColor Green
        return
    }

    $script:failed++
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

$evidencePath = Join-Path $projectRoot 'evidence\report\desktop-ui-automation-2026-07-10.json'
Assert-True -Condition (Test-Path -LiteralPath $evidencePath) -Message 'Desktop UI automation evidence exists'
if (Test-Path -LiteralPath $evidencePath) {
    $evidence = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True -Condition ($evidence.status -eq 'blocked') -Message 'Desktop UI automation is marked blocked'
    Assert-True -Condition ($evidence.power_bi_ui_action_executed -eq $false) -Message 'Evidence confirms no Power BI UI action was executed'
    Assert-True -Condition ($evidence.error.message -match 'SetIsBorderRequired failed') -Message 'Evidence preserves the capture interface error'
}

$qaPath = Join-Path $projectRoot 'docs\qa-report.md'
Assert-True -Condition (Test-Path -LiteralPath $qaPath) -Message 'QA report exists'
if (Test-Path -LiteralPath $qaPath) {
    $qa = Get-Content -LiteralPath $qaPath -Raw -Encoding UTF8
    Assert-True -Condition ($qa -match 'DESKTOP_UI_AUTOMATION_BLOCKED_2026_07_10') -Message 'QA report links the Desktop automation blocker'
}

Write-Host "RESULT: $script:passed passed, $script:failed failed"
if ($script:failed -gt 0) {
    exit 1
}

exit 0
