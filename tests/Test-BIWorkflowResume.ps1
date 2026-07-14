$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$workflowScript = Join-Path $repoRoot 'scripts\Invoke-BIWorkflow.ps1'
$runtimeScript = Join-Path $repoRoot 'scripts\bi_workflow_runtime.py'
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bi-resume-test-' + [guid]::NewGuid().ToString('N'))
$projectPath = Join-Path $temporaryRoot 'project'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

try {
    New-Item -ItemType Directory -Path (Join-Path $projectPath 'docs') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectPath 'evidence\runs') -Force | Out-Null
    @'
project:
  name: "Resume Test"
  status: "active"
quality_gates:
  documentation: "pending"
external_validation:
  power_bi_service: "not-validated"
'@ | Set-Content -LiteralPath (Join-Path $projectPath 'project.yaml') -Encoding UTF8
    '# Resume Test' | Set-Content -LiteralPath (Join-Path $projectPath 'README.md') -Encoding UTF8
    '# Scope' | Set-Content -LiteralPath (Join-Path $projectPath 'docs\scope.md') -Encoding UTF8

    $plan = (& python $runtimeScript plan --project-path $projectPath | ConvertFrom-Json)
    $fingerprintsJson = ($plan.fingerprints | ConvertTo-Json -Compress).Replace('"', '\"')
    @"

workflow:
  schema_version: 1
  last_run_id: "seed"
  last_status: "passed"
  last_mode: "resume"
  last_successful_stage: ""
  input_fingerprints_json: "$fingerprintsJson"
"@ | Add-Content -LiteralPath (Join-Path $projectPath 'project.yaml') -Encoding UTF8

    Add-Content -LiteralPath (Join-Path $projectPath 'docs\scope.md') -Value "`nUpdated."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $workflowScript -Stage Resume -ProjectPath $projectPath
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message 'Resume should pass for a documentation-only change'

    $runDirectories = @(Get-ChildItem -LiteralPath (Join-Path $projectPath 'evidence\runs') -Directory)
    Assert-True -Condition ($runDirectories.Count -eq 1) -Message 'Resume should write one run directory'
    $summary = Get-Content -LiteralPath (Join-Path $runDirectories[0].FullName 'summary.json') -Raw | ConvertFrom-Json
    Assert-True -Condition (@($summary.selected_stages).Count -eq 1) -Message 'Resume should select one documentation stage'
    Assert-True -Condition ($summary.selected_stages[0] -eq 'ValidateDocumentation') -Message 'Resume should select documentation validation'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'NEXT_CONTEXT.md')) -Message 'Resume should generate NEXT_CONTEXT.md'

    & powershell -NoProfile -ExecutionPolicy Bypass -File $workflowScript -Stage Resume -ProjectPath $projectPath
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message 'Unchanged Resume should return success'
    Write-Output 'resume_workflow_tests_passed'
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
