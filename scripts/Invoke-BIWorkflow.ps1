[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('New', 'Preflight', 'ValidateStructure', 'ValidateDataContract', 'TestDataQuality', 'ValidateMetrics', 'ValidateModelSpec', 'ValidatePowerBIProject', 'ValidateDocumentation', 'ValidateUIContract', 'ValidatePrototype', 'GenerateReport', 'ValidateReportQA', 'DesktopPreflight', 'DesktopRefresh', 'DesktopMetrics', 'DesktopRls', 'CaptureDesktopScreenshots', 'DesktopQA', 'ValidateRelease', 'ValidateAll', 'Resume', 'Release')]
    [string]$Stage,

    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [string]$ProjectName,

    [string]$TemplatePath,

    [switch]$ForceFull,

    [ValidateRange(5, 60)]
    [int]$HeartbeatSeconds = 15,

    [ValidateRange(0, 3600)]
    [int]$StageTimeoutSeconds = 0,

    [ValidateSet('Auto', 'Reuse', 'Fresh', 'Reload')]
    [string]$DesktopSessionPolicy = 'Fresh',

    [switch]$SkipDesktopReload,

    [string]$InternalRunDirectory
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($TemplatePath)) {
    $TemplatePath = Join-Path $repoRoot 'templates\bi-project'
}

$requiredFiles = @(
    'project.yaml',
    'AGENTS.md',
    'README.md',
    '.gitignore',
    'config\data-contract.json',
    'config\metrics.json',
    'docs\scope.md',
    'docs\acceptance-criteria.md',
    'docs\data-contract.md',
    'docs\metric-dictionary.md',
    'docs\dashboard-blueprint.md',
    'docs\risk-register.md',
    'docs\qa-report.md',
    'docs\delivery-notes.md',
    'docs\portfolio-case-study.md',
    'data\raw\.gitkeep',
    'data\interim\.gitkeep',
    'data\sample\.gitkeep',
    'src\extract\.gitkeep',
    'src\transform\.gitkeep',
    'src\sql\.gitkeep',
    'src\powerquery\.gitkeep',
    'src\dax\.gitkeep',
    'model\.gitkeep',
    'model\model-spec.json',
    'report\.gitkeep',
    'themes\theme.json',
    'tests\.gitkeep',
    'evidence\.gitkeep'
)

function Get-AbsolutePath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Get-StageTimeoutSeconds {
    param([string]$StageName)

    if ($StageTimeoutSeconds -gt 0) {
        return $StageTimeoutSeconds
    }
    $budgets = @{
        Preflight = 60
        ValidateStructure = 60
        ValidateDataContract = 120
        TestDataQuality = 300
        ValidateMetrics = 120
        ValidateModelSpec = 120
        ValidatePowerBIProject = 120
        ValidateDocumentation = 60
        ValidateUIContract = 120
        ValidatePrototype = 180
        GenerateReport = 120
        ValidateReportQA = 60
        DesktopPreflight = 120
        DesktopRefresh = 360
        DesktopMetrics = 120
        DesktopRls = 120
        CaptureDesktopScreenshots = 90
        DesktopQA = 600
        ValidateRelease = 120
    }
    if ($budgets.ContainsKey($StageName)) {
        return [int]$budgets[$StageName]
    }
    return 300
}

function New-CheckResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Details
    )

    return [pscustomobject]@{
        name = $Name
        passed = $Passed
        details = $Details
    }
}

function Write-WorkflowReport {
    param(
        [string]$Name,
        [string]$TargetProjectPath,
        [object[]]$Checks,
        [string]$FileBaseName
    )

    $evidencePath = Join-Path $TargetProjectPath 'evidence\workflow'
    New-Item -ItemType Directory -Path $evidencePath -Force | Out-Null

    $passed = @($Checks | Where-Object { $_.passed }).Count
    $failed = @($Checks | Where-Object { -not $_.passed }).Count
    $status = if ($failed -eq 0) { 'passed' } else { 'failed' }

    $report = [ordered]@{
        name = $Name
        status = $status
        generated_at = (Get-Date).ToString('o')
        project_path = '.'
        summary = [ordered]@{
            passed = $passed
            failed = $failed
        }
        checks = $Checks
    }

    $jsonPath = Join-Path $evidencePath ($FileBaseName + '.json')
    $markdownPath = Join-Path $evidencePath ($FileBaseName + '.md')
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = New-Object System.Collections.Generic.List[string]
    $markdown.Add("# $Name")
    $markdown.Add('')
    $markdown.Add("- Status: **$status**")
    $markdown.Add("- Passed: $passed")
    $markdown.Add("- Failed: $failed")
    $markdown.Add('')
    $markdown.Add('| Check | Result | Details |')
    $markdown.Add('|---|---|---|')
    foreach ($check in $Checks) {
        $result = if ($check.passed) { 'PASS' } else { 'FAIL' }
        $details = ([string]$check.details).Replace('|', '\|')
        $markdown.Add("| $($check.name) | $result | $details |")
    }
    $markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

    return $report
}

function Invoke-NewStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $sourcePath = Get-AbsolutePath -Path $TemplatePath

    if (Test-Path -LiteralPath $targetPath) {
        Write-Error "Target already exists; refusing to overwrite: $targetPath"
        return 10
    }
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
        Write-Error "Template directory does not exist: $sourcePath"
        return 3
    }

    if ([string]::IsNullOrWhiteSpace($ProjectName)) {
        $ProjectName = Split-Path -Leaf $targetPath
    }

    $parentPath = Split-Path -Parent $targetPath
    New-Item -ItemType Directory -Path $parentPath -Force | Out-Null
    $temporaryPath = Join-Path $parentPath ('.bi-workflow-' + [guid]::NewGuid().ToString('N'))

    try {
        New-Item -ItemType Directory -Path $temporaryPath | Out-Null
        Get-ChildItem -LiteralPath $sourcePath -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $temporaryPath -Recurse -Force
        }

        Get-ChildItem -LiteralPath $temporaryPath -Recurse -File | Where-Object {
            $_.Extension -in @('.md', '.yaml', '.yml', '.json', '.txt')
        } | ForEach-Object {
            $content = Get-Content -LiteralPath $_.FullName -Raw
            $content = $content.Replace('{{PROJECT_NAME}}', $ProjectName)
            [System.IO.File]::WriteAllText($_.FullName, $content, (New-Object System.Text.UTF8Encoding($false)))
        }

        Move-Item -LiteralPath $temporaryPath -Destination $targetPath
        Write-Host "Created BI project: $targetPath"
        return 0
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath) {
            $resolvedTemporary = Get-AbsolutePath -Path $temporaryPath
            $resolvedParent = Get-AbsolutePath -Path $parentPath
            if ($resolvedTemporary.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
            }
        }
        throw
    }
}

function Invoke-PreflightStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Write-Error "Project directory does not exist: $targetPath"
        return 2
    }

    $checks = @()
    $checks += New-CheckResult -Name 'PowerShell version' -Passed ($PSVersionTable.PSVersion.Major -ge 5) -Details $PSVersionTable.PSVersion.ToString()
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    $checks += New-CheckResult -Name 'Git command' -Passed ($null -ne $gitCommand) -Details $(if ($gitCommand) { $gitCommand.Source } else { 'not found' })
    $checks += New-CheckResult -Name 'Project directory' -Passed $true -Details '.'
    $checks += New-CheckResult -Name 'Project config' -Passed (Test-Path -LiteralPath (Join-Path $targetPath 'project.yaml') -PathType Leaf) -Details 'project.yaml'

    $report = Write-WorkflowReport -Name 'BI Workflow Preflight' -TargetProjectPath $targetPath -Checks $checks -FileBaseName 'preflight'
    Write-Host "Preflight $($report.status): $($report.summary.passed) passed, $($report.summary.failed) failed"
    if ($report.status -eq 'passed') { return 0 }
    return 2
}

function Invoke-ValidateStructureStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Write-Error "Project directory does not exist: $targetPath"
        return 2
    }

    $checks = foreach ($relativePath in $requiredFiles) {
        $exists = Test-Path -LiteralPath (Join-Path $targetPath $relativePath) -PathType Leaf
        $details = if ($exists) { $relativePath } else { "Missing: $relativePath" }
        New-CheckResult -Name $relativePath -Passed $exists -Details $details
    }

    $report = Write-WorkflowReport -Name 'BI Project Structure Validation' -TargetProjectPath $targetPath -Checks $checks -FileBaseName 'structure-validation'
    foreach ($failedCheck in @($checks | Where-Object { -not $_.passed })) {
        Write-Host $failedCheck.details
    }
    Write-Host "Structure validation $($report.status): $($report.summary.passed) passed, $($report.summary.failed) failed"
    if ($report.status -eq 'passed') { return 0 }
    return 2
}

function Invoke-DataQualityStage {
    param(
        [ValidateSet('validate-contract', 'test-data')]
        [string]$Mode
    )

    $targetPath = Get-AbsolutePath -Path $ProjectPath
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Write-Error "Project directory does not exist: $targetPath"
        return 2
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        Write-Error 'Python is required for data contract and data quality stages.'
        return 2
    }

    $qualityScript = Join-Path $repoRoot 'scripts\Test-BIDataQuality.py'
    if (-not (Test-Path -LiteralPath $qualityScript -PathType Leaf)) {
        Write-Error "Data quality script does not exist: $qualityScript"
        return 3
    }

    & $pythonCommand.Source $qualityScript --mode $Mode --project-path $targetPath |
        ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

function Invoke-PythonProjectCheck {
    param([string]$ScriptName)

    $targetPath = Get-AbsolutePath -Path $ProjectPath
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Write-Error "Project directory does not exist: $targetPath"
        return 2
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        Write-Error 'Python is required for this BI validation stage.'
        return 2
    }

    $checkScript = Join-Path $repoRoot "scripts\$ScriptName"
    if (-not (Test-Path -LiteralPath $checkScript -PathType Leaf)) {
        Write-Error "Validation script does not exist: $checkScript"
        return 3
    }

    & $pythonCommand.Source $checkScript --project-path $targetPath |
        ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

function Write-ValidationSummary {
    param(
        [string]$TargetProjectPath,
        [object[]]$StageResults
    )

    $evidencePath = Join-Path $TargetProjectPath 'evidence\workflow'
    New-Item -ItemType Directory -Path $evidencePath -Force | Out-Null

    $passed = @($StageResults | Where-Object { $_.status -eq 'passed' }).Count
    $failed = @($StageResults | Where-Object { $_.status -eq 'failed' }).Count
    $status = if ($failed -eq 0) { 'passed' } else { 'failed' }

    $report = [ordered]@{
        name = 'BI Workflow Validation Summary'
        status = $status
        generated_at = (Get-Date).ToString('o')
        project_path = '.'
        summary = [ordered]@{
            stage_count = @($StageResults).Count
            passed = $passed
            failed = $failed
            manual_or_external_checks = @(
                'Power BI Desktop Import refresh with local runtime parameter'
                'Power BI report canvas and interaction review'
                'Power BI Service or Fabric publish and permission validation'
            )
        }
        stages = $StageResults
    }

    $jsonPath = Join-Path $evidencePath 'validation-summary.json'
    $markdownPath = Join-Path $evidencePath 'validation-summary.md'
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = New-Object System.Collections.Generic.List[string]
    $markdown.Add('# BI Workflow Validation Summary')
    $markdown.Add('')
    $markdown.Add("- Status: **$status**")
    $markdown.Add("- Stages: $(@($StageResults).Count)")
    $markdown.Add("- Passed: $passed")
    $markdown.Add("- Failed: $failed")
    $markdown.Add('')
    $markdown.Add('| Stage | Result | Exit code | Evidence |')
    $markdown.Add('|---|---|---:|---|')
    foreach ($stageResult in $StageResults) {
        $result = if ($stageResult.status -eq 'passed') { 'PASS' } else { 'FAIL' }
        $evidence = if ($stageResult.evidence_files -and @($stageResult.evidence_files).Count -gt 0) {
            (@($stageResult.evidence_files) -join '<br>')
        }
        else {
            '-'
        }
        $markdown.Add("| $($stageResult.stage) | $result | $($stageResult.exit_code) | $evidence |")
    }
    $markdown.Add('')
    $markdown.Add('## Manual or external checks not covered by this command')
    $markdown.Add('')
    $markdown.Add('- Power BI Desktop Import refresh with local runtime parameter.')
    $markdown.Add('- Power BI report canvas and interaction review.')
    $markdown.Add('- Power BI Service or Fabric publish and permission validation.')
    $markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

    return $report
}

function Invoke-ValidateAllStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Write-Error "Project directory does not exist: $targetPath"
        return 2
    }

    $stageDefinitions = @(
        [ordered]@{
            Stage = 'Preflight'
            Evidence = @('evidence/workflow/preflight.json', 'evidence/workflow/preflight.md')
            Invoke = { Invoke-PreflightStage }
        },
        [ordered]@{
            Stage = 'ValidateStructure'
            Evidence = @('evidence/workflow/structure-validation.json', 'evidence/workflow/structure-validation.md')
            Invoke = { Invoke-ValidateStructureStage }
        },
        [ordered]@{
            Stage = 'ValidateDataContract'
            Evidence = @('evidence/data-quality/contract-validation.json', 'evidence/data-quality/contract-validation.md')
            Invoke = { Invoke-DataQualityStage -Mode 'validate-contract' }
        },
        [ordered]@{
            Stage = 'TestDataQuality'
            Evidence = @('evidence/data-quality/data-quality.json', 'evidence/data-quality/data-quality.md')
            Invoke = { Invoke-DataQualityStage -Mode 'test-data' }
        },
        [ordered]@{
            Stage = 'ValidateMetrics'
            Evidence = @('evidence/metrics/metrics-validation.json', 'evidence/metrics/metrics-validation.md')
            Invoke = { Invoke-PythonProjectCheck -ScriptName 'Test-BIMetrics.py' }
        },
        [ordered]@{
            Stage = 'ValidateModelSpec'
            Evidence = @('evidence/model/model-spec-validation.json', 'evidence/model/model-spec-validation.md')
            Invoke = { Invoke-PythonProjectCheck -ScriptName 'Test-BIModelSpec.py' }
        },
        [ordered]@{
            Stage = 'ValidatePowerBIProject'
            Evidence = @('evidence/model/powerbi-project-validation.json', 'evidence/model/powerbi-project-validation.md')
            Invoke = { Invoke-PythonProjectCheck -ScriptName 'Test-BIPowerBIProject.py' }
        }
    )

    $stageResults = foreach ($stageDefinition in $stageDefinitions) {
        Write-Host "Running $($stageDefinition.Stage)..."
        $exitCode = 3
        $errorMessage = $null
        try {
            $exitCode = & $stageDefinition.Invoke
        }
        catch {
            $errorMessage = $_.Exception.Message
            Write-Host "$($stageDefinition.Stage) failed with unexpected error: $errorMessage"
        }

        $status = if ($exitCode -eq 0) { 'passed' } else { 'failed' }
        $evidenceFiles = @(
            foreach ($relativeEvidence in $stageDefinition.Evidence) {
                $windowsRelativeEvidence = $relativeEvidence.Replace('/', '\')
                if (Test-Path -LiteralPath (Join-Path $targetPath $windowsRelativeEvidence) -PathType Leaf) {
                    $relativeEvidence
                }
            }
        )

        $result = [ordered]@{
            stage = $stageDefinition.Stage
            status = $status
            exit_code = $exitCode
            evidence_files = $evidenceFiles
        }
        if ($errorMessage) {
            $result.error = $errorMessage
        }
        [pscustomobject]$result
    }

    $report = Write-ValidationSummary -TargetProjectPath $targetPath -StageResults $stageResults
    Write-Host "ValidateAll $($report.status): $($report.summary.passed) passed, $($report.summary.failed) failed"
    Write-Host $(if ($report.status -eq 'passed') { 'validate_all_passed' } else { 'validate_all_failed' })
    if ($report.status -eq 'passed') { return 0 }
    return 2
}

function Get-ProjectPythonCommand {
    param([string]$TargetPath)

    $projectPython = Join-Path $TargetPath '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
        return $projectPython
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw 'Python is required for resumable workflow stages.'
    }
    return $pythonCommand.Source
}

function Invoke-DocumentationStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $runtimeScript = Join-Path $repoRoot 'scripts\bi_workflow_runtime.py'
    & python $runtimeScript validate-docs --project-path $targetPath | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

function Invoke-NativeCommandCaptured {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @()
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host ([string]$_) }
        $nativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return $nativeExitCode
}

function Invoke-UIContractStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $pythonCommand = Get-ProjectPythonCommand -TargetPath $targetPath
    $testPath = Join-Path $targetPath 'tests\test_ui_contract.py'
    if (-not (Test-Path -LiteralPath $testPath -PathType Leaf)) {
        Write-Host 'ui_contract_test_not_found'
        return 2
    }
    Push-Location $targetPath
    try {
        return Invoke-NativeCommandCaptured -FilePath $pythonCommand -Arguments @('-m', 'unittest', 'tests/test_ui_contract.py', '-v')
    }
    finally {
        Pop-Location
    }
}

function Invoke-PrototypeStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $prototypePath = Join-Path $targetPath 'ui-prototype'
    $packagePath = Join-Path $prototypePath 'package.json'
    if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
        Write-Host 'ui_prototype_not_found'
        return 2
    }
    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
    if ($null -eq $npmCommand) {
        Write-Host 'npm_not_found'
        return 2
    }
    Push-Location $prototypePath
    try {
        return Invoke-NativeCommandCaptured -FilePath $npmCommand.Source -Arguments @('test')
    }
    finally {
        Pop-Location
    }
}

function Resolve-DesktopSessionPolicy {
    if ($SkipDesktopReload) {
        Write-Host 'desktop_session_legacy_skip_reload_mapped_to_reuse'
        return 'Reuse'
    }
    return $DesktopSessionPolicy
}

function Get-DesktopBridgeStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BridgePath,

        [int]$WaitSeconds = 2,

        [int]$ProcessId = 0
    )

    $statusArguments = @('status', '--wait-seconds', [string]$WaitSeconds)
    if ($ProcessId -gt 0) {
        $statusArguments += @('--pid', [string]$ProcessId)
    }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $statusText = (& $BridgePath @statusArguments 2>&1) -join [Environment]::NewLine
        $statusExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($statusExitCode -ne 0) {
        Write-Host "desktop_bridge_status_failed exit_code=$statusExitCode"
        return $null
    }
    try {
        return $statusText | ConvertFrom-Json
    }
    catch {
        Write-Host 'desktop_bridge_status_invalid'
        return $null
    }
}

function Get-AllDesktopBridgeInstances {
    param([Parameter(Mandatory = $true)][string]$BridgePath)

    $desktopProcesses = @(Get-Process PBIDesktop -ErrorAction SilentlyContinue)
    $instances = New-Object System.Collections.Generic.List[object]
    $successfulStatusCount = 0
    foreach ($desktopProcess in $desktopProcesses) {
        $status = Get-DesktopBridgeStatus -BridgePath $BridgePath -WaitSeconds 0 -ProcessId $desktopProcess.Id
        if ($null -eq $status) { continue }
        $successfulStatusCount++
        foreach ($instance in @($status.instances)) {
            $instances.Add($instance)
        }
    }
    if ($desktopProcesses.Count -gt 0 -and $successfulStatusCount -ne $desktopProcesses.Count) {
        Write-Host "desktop_bridge_discovery_incomplete successful=$successfulStatusCount total=$($desktopProcesses.Count)"
        return $null
    }
    return [pscustomobject]@{
        status = 'ready'
        instances = $instances.ToArray()
    }
}

function Get-DesktopTargetInstances {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Status,

        [Parameter(Mandatory = $true)]
        [string]$TargetFile
    )

    $resolvedTargetFile = Get-AbsolutePath -Path $TargetFile
    return @($Status.instances | Where-Object {
        $_.bridgeStatus -eq 'connected' -and
        -not [string]::IsNullOrWhiteSpace([string]$_.currentFilePath) -and
        ((Get-AbsolutePath -Path ([string]$_.currentFilePath)) -eq $resolvedTargetFile)
    })
}

function Get-DesktopTargetInstance {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Status,

        [Parameter(Mandatory = $true)]
        [string]$TargetFile
    )

    return @(Get-DesktopTargetInstances -Status $Status -TargetFile $TargetFile) | Select-Object -First 1
}

function New-DesktopSessionResult {
    param(
        [bool]$Succeeded,
        [int]$ExitCode,
        [string]$Action,
        [object]$Instance,
        [bool]$CreatedByWorkflow,
        [int64]$AcquisitionDurationMs = 0
    )

    return [pscustomobject]@{
        succeeded = $Succeeded
        exit_code = $ExitCode
        action = $Action
        instance = $Instance
        created_by_workflow = $CreatedByWorkflow
        acquisition_duration_ms = $AcquisitionDurationMs
    }
}

function Resolve-PowerBIDesktopExecutable {
    param([Parameter(Mandatory = $true)][object]$StatusBeforeOpen)

    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:PBI_DESKTOP_PATH)) {
        $candidates.Add($env:PBI_DESKTOP_PATH)
    }
    foreach ($bridgeInstance in @($StatusBeforeOpen.instances)) {
        $desktopProcess = Get-Process -Id ([int]$bridgeInstance.pid) -ErrorAction SilentlyContinue
        if ($null -ne $desktopProcess -and -not [string]::IsNullOrWhiteSpace($desktopProcess.Path)) {
            $candidates.Add($desktopProcess.Path)
        }
    }
    foreach ($desktopProcess in @(Get-Process PBIDesktop -ErrorAction SilentlyContinue)) {
        if (-not [string]::IsNullOrWhiteSpace($desktopProcess.Path)) {
            $candidates.Add($desktopProcess.Path)
        }
    }
    $desktopCommand = Get-Command PBIDesktop.exe -ErrorAction SilentlyContinue
    if ($null -ne $desktopCommand -and -not [string]::IsNullOrWhiteSpace($desktopCommand.Source)) {
        $candidates.Add($desktopCommand.Source)
    }

    $shortcutShell = $null
    try {
        $shortcutShell = New-Object -ComObject WScript.Shell
        $shortcutRoots = @(
            (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs'),
            (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
        )
        foreach ($shortcut in @(Get-ChildItem $shortcutRoots -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*Power BI*' })) {
            $targetPath = $shortcutShell.CreateShortcut($shortcut.FullName).TargetPath
            if (-not [string]::IsNullOrWhiteSpace($targetPath)) {
                $candidates.Add($targetPath)
            }
        }
    }
    catch {
        Write-Host "desktop_executable_shortcut_discovery_skipped=$($_.Exception.Message)"
    }
    finally {
        if ($null -ne $shortcutShell) {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcutShell)
        }
    }

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return Get-AbsolutePath -Path $candidate
        }
    }
    return $null
}

function Wait-DesktopTargetInstance {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BridgePath,

        [Parameter(Mandatory = $true)]
        [string]$TargetFile,

        [int[]]$ExistingProcessIds = @(),

        [int]$TimeoutSeconds = 120
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $desktopProcesses = @(Get-Process PBIDesktop -ErrorAction SilentlyContinue)
        $newProcesses = @($desktopProcesses | Where-Object { $ExistingProcessIds -notcontains $_.Id })
        $existingProcesses = @($desktopProcesses | Where-Object { $ExistingProcessIds -contains $_.Id })
        foreach ($candidateProcess in @($newProcesses + $existingProcesses)) {
            $candidateStatus = Get-DesktopBridgeStatus -BridgePath $BridgePath -WaitSeconds 0 -ProcessId $candidateProcess.Id
            if ($null -eq $candidateStatus) { continue }
            $candidateInstance = Get-DesktopTargetInstance -Status $candidateStatus -TargetFile $TargetFile
            if ($null -ne $candidateInstance) {
                return $candidateInstance
            }
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    return $null
}

function Open-DesktopTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BridgePath,

        [Parameter(Mandatory = $true)]
        [string]$TargetFile,

        [Parameter(Mandatory = $true)]
        [object]$StatusBeforeOpen
    )

    $existingProcessIds = @($StatusBeforeOpen.instances | ForEach-Object { [int]$_.pid })
    $resolvedDesktopPath = Resolve-PowerBIDesktopExecutable -StatusBeforeOpen $StatusBeforeOpen
    $previousDesktopPath = $env:PBI_DESKTOP_PATH
    try {
        if (-not [string]::IsNullOrWhiteSpace($resolvedDesktopPath)) {
            $env:PBI_DESKTOP_PATH = $resolvedDesktopPath
            Write-Host "desktop_executable_resolved=$resolvedDesktopPath"
        }
        $openExitCode = Invoke-NativeCommandCaptured -FilePath $BridgePath -Arguments @(
            'open', $TargetFile, '--timeout', '5'
        )
    }
    finally {
        if ($null -eq $previousDesktopPath) {
            Remove-Item Env:PBI_DESKTOP_PATH -ErrorAction SilentlyContinue
        }
        else {
            $env:PBI_DESKTOP_PATH = $previousDesktopPath
        }
    }
    if ($openExitCode -ne 0) {
        Write-Host "desktop_target_open_failed exit_code=$openExitCode"
        return New-DesktopSessionResult -Succeeded $false -ExitCode 2 -Action 'open_failed' -Instance $null -CreatedByWorkflow $false
    }
    $instance = Wait-DesktopTargetInstance -BridgePath $BridgePath -TargetFile $TargetFile -ExistingProcessIds $existingProcessIds -TimeoutSeconds 120
    if ($null -eq $instance) {
        Write-Host 'desktop_target_open_timeout'
        return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'target_open_timeout' -Instance $null -CreatedByWorkflow $false
    }
    $createdByWorkflow = $existingProcessIds -notcontains [int]$instance.pid
    Write-Host "desktop_target_opened pid=$($instance.pid) created_by_workflow=$($createdByWorkflow.ToString().ToLower())"
    return New-DesktopSessionResult -Succeeded $true -ExitCode 0 -Action 'opened' -Instance $instance -CreatedByWorkflow $createdByWorkflow
}

function Close-DesktopTargetGracefully {
    param([Parameter(Mandatory = $true)][object]$Instance)

    $desktopProcess = Get-Process -Id ([int]$Instance.pid) -ErrorAction SilentlyContinue
    if ($null -eq $desktopProcess) {
        Write-Host "desktop_fresh_target_already_closed pid=$($Instance.pid)"
        return $true
    }
    if (-not $desktopProcess.CloseMainWindow()) {
        Write-Host "desktop_fresh_close_not_accepted pid=$($Instance.pid)"
        return $false
    }
    if (-not $desktopProcess.WaitForExit(30000)) {
        Write-Host "desktop_fresh_close_timeout pid=$($Instance.pid)"
        return $false
    }
    Write-Host "desktop_fresh_target_closed pid=$($Instance.pid)"
    return $true
}

function Acquire-DesktopSession {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BridgePath,

        [Parameter(Mandatory = $true)]
        [string]$TargetFile,

        [Parameter(Mandatory = $true)]
        [ValidateSet('Auto', 'Reuse', 'Fresh', 'Reload')]
        [string]$Policy
    )

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $status = Get-AllDesktopBridgeInstances -BridgePath $BridgePath
    if ($null -eq $status) {
        $stopwatch.Stop()
        return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'status_unavailable' -Instance $null -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
    }
    $targetInstances = @(Get-DesktopTargetInstances -Status $status -TargetFile $TargetFile)
    $unsavedInstances = @($targetInstances | Where-Object { $_.hasUnsavedChanges })
    if ($unsavedInstances.Count -gt 0) {
        $instance = $unsavedInstances | Select-Object -First 1
        Write-Host 'desktop_unsaved_changes_blocked'
        $stopwatch.Stop()
        return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'blocked_unsaved_changes' -Instance $instance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
    }
    if ($Policy -ne 'Fresh' -and $targetInstances.Count -gt 1) {
        $instance = $targetInstances | Select-Object -First 1
        Write-Host "desktop_multiple_target_instances_blocked count=$($targetInstances.Count)"
        $stopwatch.Stop()
        return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'multiple_targets_blocked' -Instance $instance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
    }
    $instance = $targetInstances | Select-Object -First 1

    switch ($Policy) {
        'Auto' {
            if ($null -ne $instance) {
                Write-Host "desktop_session_auto_reused pid=$($instance.pid)"
                $stopwatch.Stop()
                return New-DesktopSessionResult -Succeeded $true -ExitCode 0 -Action 'reused' -Instance $instance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
            }
            $result = Open-DesktopTarget -BridgePath $BridgePath -TargetFile $TargetFile -StatusBeforeOpen $status
            $stopwatch.Stop()
            $result.acquisition_duration_ms = $stopwatch.ElapsedMilliseconds
            return $result
        }
        'Reuse' {
            if ($null -eq $instance) {
                Write-Host 'desktop_target_not_connected_for_reuse'
                $stopwatch.Stop()
                return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'reuse_target_missing' -Instance $null -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
            }
            Write-Host "desktop_session_reused pid=$($instance.pid)"
            $stopwatch.Stop()
            return New-DesktopSessionResult -Succeeded $true -ExitCode 0 -Action 'reused' -Instance $instance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
        }
        'Fresh' {
            foreach ($freshInstance in $targetInstances) {
                if (-not (Close-DesktopTargetGracefully -Instance $freshInstance)) {
                    $stopwatch.Stop()
                    return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'fresh_close_blocked' -Instance $freshInstance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
                }
            }
            $statusBeforeOpen = Get-AllDesktopBridgeInstances -BridgePath $BridgePath
            if ($null -eq $statusBeforeOpen) {
                $stopwatch.Stop()
                return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'status_unavailable_before_fresh_open' -Instance $null -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
            }
            $result = Open-DesktopTarget -BridgePath $BridgePath -TargetFile $TargetFile -StatusBeforeOpen $statusBeforeOpen
            $stopwatch.Stop()
            $result.acquisition_duration_ms = $stopwatch.ElapsedMilliseconds
            if ($result.succeeded) {
                $result.action = 'fresh_started'
                Write-Host "desktop_fresh_session_started pid=$($result.instance.pid)"
            }
            return $result
        }
        'Reload' {
            if ($null -eq $instance) {
                Write-Host 'desktop_target_not_connected_for_reload'
                $stopwatch.Stop()
                return New-DesktopSessionResult -Succeeded $false -ExitCode 4 -Action 'reload_target_missing' -Instance $null -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
            }
            $reloadExitCode = Invoke-NativeCommandCaptured -FilePath $BridgePath -Arguments @(
                'reload', '--pid', [string]$instance.pid, '--wait-seconds', '60'
            )
            $stopwatch.Stop()
            if ($reloadExitCode -ne 0) {
                Write-Host "desktop_reload_failed exit_code=$reloadExitCode"
                return New-DesktopSessionResult -Succeeded $false -ExitCode 2 -Action 'reload_failed' -Instance $instance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
            }
            Write-Host "desktop_session_reload_completed pid=$($instance.pid)"
            return New-DesktopSessionResult -Succeeded $true -ExitCode 0 -Action 'reloaded' -Instance $instance -CreatedByWorkflow $false -AcquisitionDurationMs $stopwatch.ElapsedMilliseconds
        }
    }
}

function Write-DesktopSessionEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RunDirectory,

        [Parameter(Mandatory = $true)]
        [string]$RequestedPolicy,

        [Parameter(Mandatory = $true)]
        [string]$EffectivePolicy,

        [Parameter(Mandatory = $true)]
        [object]$SessionResult
    )

    if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
        return
    }
    New-Item -ItemType Directory -Path $RunDirectory -Force | Out-Null
    $evidence = [ordered]@{
        name = 'Power BI Desktop session lifecycle'
        status = if ($SessionResult.succeeded) { 'passed' } elseif ($SessionResult.exit_code -eq 4) { 'blocked' } else { 'failed' }
        generated_at = (Get-Date).ToString('o')
        requested_policy = $RequestedPolicy
        effective_policy = $EffectivePolicy
        action = $SessionResult.action
        exit_code = [int]$SessionResult.exit_code
        pid = if ($null -ne $SessionResult.instance) { [int]$SessionResult.instance.pid } else { $null }
        created_by_workflow = [bool]$SessionResult.created_by_workflow
        acquisition_duration_ms = [int64]$SessionResult.acquisition_duration_ms
    }
    $evidencePath = Join-Path $RunDirectory 'desktop-session.json'
    $evidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $evidencePath -Encoding UTF8
    Write-Host "desktop_session_evidence=$evidencePath"
}

function Invoke-GenerateReportStage {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $pythonCommand = Get-ProjectPythonCommand -TargetPath $targetPath
    $generatorPath = Join-Path $targetPath 'src\automation\apply_pbir_report.py'
    if (-not (Test-Path -LiteralPath $generatorPath -PathType Leaf)) {
        Write-Host 'pbir_generator_not_found'
        return 2
    }
    $bridgeCommand = Get-Command powerbi-desktop -ErrorAction SilentlyContinue
    if ($null -ne $bridgeCommand) {
        $status = Get-AllDesktopBridgeInstances -BridgePath $bridgeCommand.Source
        $targetFile = Join-Path $targetPath 'EnterpriseSalesAutomation.pbip'
        $targetInstances = @(Get-DesktopTargetInstances -Status $status -TargetFile $targetFile)
        if (@($targetInstances | Where-Object { $_.hasUnsavedChanges }).Count -gt 0) {
            Write-Host 'desktop_unsaved_changes_blocked'
            return 4
        }
        if ($targetInstances.Count -gt 1) {
            Write-Host "desktop_multiple_target_instances_blocked count=$($targetInstances.Count)"
            return 4
        }
    }
    & $pythonCommand $generatorPath --project-path $targetPath --replace-generated | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

function Resolve-DesktopRunDirectory {
    param([string]$RunDirectory)

    if (-not [string]::IsNullOrWhiteSpace($RunDirectory)) {
        return $RunDirectory
    }
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    return Join-Path $targetPath ('evidence\runs\manual-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ'))
}

function Get-DesktopExecutionContext {
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $bridgeCommand = Get-Command powerbi-desktop -ErrorAction SilentlyContinue
    if ($null -eq $bridgeCommand) {
        Write-Host 'desktop_bridge_not_installed'
        return $null
    }
    $targetFile = Join-Path $targetPath 'EnterpriseSalesAutomation.pbip'
    $status = Get-AllDesktopBridgeInstances -BridgePath $bridgeCommand.Source
    if ($null -eq $status) {
        Write-Host 'desktop_bridge_status_unavailable'
        return $null
    }
    $targetInstances = @(Get-DesktopTargetInstances -Status $status -TargetFile $targetFile)
    if ($targetInstances.Count -ne 1) {
        Write-Host "desktop_target_instance_count_blocked count=$($targetInstances.Count)"
        return $null
    }
    $instance = $targetInstances[0]
    $desktopProcess = Get-Process -Id $instance.pid -ErrorAction SilentlyContinue
    if ($null -eq $desktopProcess -or [string]::IsNullOrWhiteSpace($desktopProcess.Path)) {
        Write-Host 'desktop_process_path_not_found'
        return $null
    }
    $workspacePath = $null
    for ($attempt = 0; $attempt -lt 30 -and $null -eq $workspacePath; $attempt++) {
        $engineProcess = @(Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object {
            $_.ParentProcessId -eq $instance.pid
        }) | Select-Object -First 1
        if ($null -ne $engineProcess -and $engineProcess.CommandLine -match '-s\s+"(?<DataPath>[^"]+)"') {
            $candidateWorkspace = Split-Path -Parent $Matches.DataPath
            if (Test-Path -LiteralPath (Join-Path $candidateWorkspace 'Data\msmdsrv.port.txt') -PathType Leaf) {
                $workspacePath = $candidateWorkspace
                break
            }
        }
        Start-Sleep -Seconds 1
    }
    if ($null -eq $workspacePath) {
        Write-Host 'desktop_workspace_not_found'
        return $null
    }
    return [pscustomobject]@{
        TargetPath = $targetPath
        BridgePath = $bridgeCommand.Source
        Instance = $instance
        WorkspacePath = $workspacePath
        PowerBIDesktopBin = Split-Path -Parent $desktopProcess.Path
    }
}

function Invoke-DesktopPreflightStage {
    param([string]$RunDirectory)

    $RunDirectory = Resolve-DesktopRunDirectory -RunDirectory $RunDirectory
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $bridgeCommand = Get-Command powerbi-desktop -ErrorAction SilentlyContinue
    if ($null -eq $bridgeCommand) {
        Write-Host 'desktop_bridge_not_installed'
        return 4
    }
    $targetFile = Join-Path $targetPath 'EnterpriseSalesAutomation.pbip'
    $effectiveSessionPolicy = Resolve-DesktopSessionPolicy
    $sessionResult = Acquire-DesktopSession -BridgePath $bridgeCommand.Source -TargetFile $targetFile -Policy $effectiveSessionPolicy
    Write-DesktopSessionEvidence -RunDirectory $RunDirectory -RequestedPolicy $DesktopSessionPolicy -EffectivePolicy $effectiveSessionPolicy -SessionResult $sessionResult
    if (-not $sessionResult.succeeded) { return [int]$sessionResult.exit_code }
    $context = Get-DesktopExecutionContext
    if ($null -eq $context) { return 4 }
    Write-Host "desktop_preflight_passed pid=$($context.Instance.pid)"
    return 0
}

function Invoke-DesktopRefreshStage {
    param([string]$RunDirectory)

    $RunDirectory = Resolve-DesktopRunDirectory -RunDirectory $RunDirectory
    $context = Get-DesktopExecutionContext
    if ($null -eq $context) { return 4 }
    $refreshScript = Join-Path $context.TargetPath 'src\automation\Refresh-DesktopModel.ps1'
    try {
        & $refreshScript -WorkspacePath $context.WorkspacePath -PowerBIDesktopBin $context.PowerBIDesktopBin -EvidenceDirectory (Join-Path $RunDirectory 'desktop-model') | ForEach-Object { Write-Host $_ }
        return 0
    }
    catch {
        Write-Host "desktop_refresh_failed=$($_.Exception.Message)"
        return 2
    }
}

function Invoke-DesktopMetricsStage {
    param([string]$RunDirectory)

    $RunDirectory = Resolve-DesktopRunDirectory -RunDirectory $RunDirectory
    $context = Get-DesktopExecutionContext
    if ($null -eq $context) { return 4 }
    $metricScript = Join-Path $context.TargetPath 'src\automation\Validate-DesktopMetrics.ps1'
    $duckdbBaseline = Join-Path $context.TargetPath 'evidence\metrics\duckdb-baseline.json'
    try {
        & $metricScript -WorkspacePath $context.WorkspacePath -PowerBIDesktopBin $context.PowerBIDesktopBin -EvidenceDirectory (Join-Path $RunDirectory 'desktop-metrics') -BaselinePath $duckdbBaseline | ForEach-Object { Write-Host $_ }
        return 0
    }
    catch {
        Write-Host "desktop_metric_or_performance_failed=$($_.Exception.Message)"
        return 2
    }
}

function Invoke-DesktopRlsStage {
    param([string]$RunDirectory)

    $RunDirectory = Resolve-DesktopRunDirectory -RunDirectory $RunDirectory
    $context = Get-DesktopExecutionContext
    if ($null -eq $context) { return 4 }
    $rlsScript = Join-Path $context.TargetPath 'src\automation\Validate-DesktopRls.ps1'
    $rlsBaseline = Join-Path $context.TargetPath 'evidence\metrics\rls-country-baseline.json'
    try {
        & $rlsScript -WorkspacePath $context.WorkspacePath -PowerBIDesktopBin $context.PowerBIDesktopBin -EvidenceDirectory (Join-Path $RunDirectory 'desktop-rls') -BaselinePath $rlsBaseline | ForEach-Object { Write-Host $_ }
        return 0
    }
    catch {
        Write-Host "desktop_rls_failed=$($_.Exception.Message)"
        return 2
    }
}

function Invoke-CaptureDesktopScreenshotsStage {
    param([string]$RunDirectory)

    $RunDirectory = Resolve-DesktopRunDirectory -RunDirectory $RunDirectory
    $context = Get-DesktopExecutionContext
    if ($null -eq $context) { return 4 }
    $screenshotsPath = Join-Path $RunDirectory 'desktop-screenshots'
    New-Item -ItemType Directory -Path $screenshotsPath -Force | Out-Null
    & $context.BridgePath screenshot-all --pid $context.Instance.pid --output-dir $screenshotsPath --settle 2500 --wait-seconds 60 | Out-Null
    if ($LASTEXITCODE -ne 0) { return 2 }
    $screenshotCount = @(Get-ChildItem -LiteralPath $screenshotsPath -Filter '*.png' -File).Count
    if ($screenshotCount -lt 3) {
        Write-Host "desktop_screenshot_count_blocked count=$screenshotCount"
        return 2
    }
    Write-Host "desktop_screenshots_captured=$screenshotCount"
    return 0
}

function Invoke-DesktopQAStage {
    param([string]$RunDirectory)

    $RunDirectory = Resolve-DesktopRunDirectory -RunDirectory $RunDirectory
    foreach ($operation in @(
        { Invoke-DesktopPreflightStage -RunDirectory $RunDirectory },
        { Invoke-DesktopRefreshStage -RunDirectory $RunDirectory },
        { Invoke-DesktopMetricsStage -RunDirectory $RunDirectory },
        { Invoke-DesktopRlsStage -RunDirectory $RunDirectory },
        { Invoke-CaptureDesktopScreenshotsStage -RunDirectory $RunDirectory }
    )) {
        $exitCode = & $operation
        if ($exitCode -ne 0) { return $exitCode }
    }
    return 0
}

function Invoke-ReleaseStage {
    param([string]$RunDirectory)

    if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
        Write-Host 'release_run_directory_missing'
        return 3
    }
    $targetPath = Get-AbsolutePath -Path $ProjectPath
    $runtimeScript = Join-Path $repoRoot 'scripts\bi_workflow_runtime.py'
    & python $runtimeScript validate-release --project-path $targetPath --run-directory $RunDirectory |
        ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

function Invoke-WorkflowStageByName {
    param(
        [string]$StageName,
        [string]$RunDirectory
    )

    switch ($StageName) {
        'Preflight' { return Invoke-PreflightStage }
        'ValidateStructure' { return Invoke-ValidateStructureStage }
        'ValidateDataContract' { return Invoke-DataQualityStage -Mode 'validate-contract' }
        'TestDataQuality' { return Invoke-DataQualityStage -Mode 'test-data' }
        'ValidateMetrics' { return Invoke-PythonProjectCheck -ScriptName 'Test-BIMetrics.py' }
        'ValidateModelSpec' { return Invoke-PythonProjectCheck -ScriptName 'Test-BIModelSpec.py' }
        'ValidatePowerBIProject' { return Invoke-PythonProjectCheck -ScriptName 'Test-BIPowerBIProject.py' }
        'ValidateDocumentation' { return Invoke-DocumentationStage }
        'ValidateUIContract' { return Invoke-UIContractStage }
        'ValidatePrototype' { return Invoke-PrototypeStage }
        'GenerateReport' { return Invoke-GenerateReportStage }
        'ValidateReportQA' { return Invoke-PythonProjectCheck -ScriptName 'Test-BIReportQA.py' }
        'DesktopPreflight' { return Invoke-DesktopPreflightStage -RunDirectory $RunDirectory }
        'DesktopRefresh' { return Invoke-DesktopRefreshStage -RunDirectory $RunDirectory }
        'DesktopMetrics' { return Invoke-DesktopMetricsStage -RunDirectory $RunDirectory }
        'DesktopRls' { return Invoke-DesktopRlsStage -RunDirectory $RunDirectory }
        'CaptureDesktopScreenshots' { return Invoke-CaptureDesktopScreenshotsStage -RunDirectory $RunDirectory }
        'DesktopQA' { return Invoke-DesktopQAStage -RunDirectory $RunDirectory }
        'ValidateRelease' { return Invoke-ReleaseStage -RunDirectory $RunDirectory }
        default { Write-Host "unknown_resumable_stage=$StageName"; return 3 }
    }
}

function Invoke-ResumableStage {
    param([bool]$ReleaseMode)

    $targetPath = Get-AbsolutePath -Path $ProjectPath
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Write-Error "Project directory does not exist: $targetPath"
        return 2
    }
    $runtimeScript = Join-Path $repoRoot 'scripts\bi_workflow_runtime.py'
    $runnerScript = Join-Path $repoRoot 'scripts\run_with_heartbeat.py'
    $powershellExecutable = (Get-Process -Id $PID).Path
    $runId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
    $runDirectory = Join-Path $targetPath "evidence\runs\$runId"
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    $planPath = Join-Path $runDirectory 'plan.json'
    $resultsPath = Join-Path $runDirectory 'stage-results.json'
    $planArguments = @($runtimeScript, 'plan', '--project-path', $targetPath)
    if ($ForceFull) { $planArguments += '--force-full' }
    if ($ReleaseMode) { $planArguments += '--release' }
    $planJson = & python @planArguments
    if ($LASTEXITCODE -ne 0) { return 3 }
    [IO.File]::WriteAllText($planPath, $planJson + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
    $plan = $planJson | ConvertFrom-Json
    Write-Host "workflow_plan run=$runId selected_stages=$(@($plan.selected_stages).Count)"

    $stageResults = New-Object System.Collections.Generic.List[object]
    foreach ($selectedStage in @($plan.selected_stages)) {
        $logPath = Join-Path $runDirectory ($selectedStage + '.log')
        $processResultPath = Join-Path $runDirectory ($selectedStage + '.process.json')
        $timeoutSeconds = Get-StageTimeoutSeconds -StageName $selectedStage
        Write-Host "stage_start stage=$selectedStage timeout_s=$timeoutSeconds log=$logPath"
        $childArguments = @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', $PSCommandPath,
            '-Stage', $selectedStage,
            '-ProjectPath', $targetPath,
            '-InternalRunDirectory', $runDirectory,
            '-HeartbeatSeconds', [string]$HeartbeatSeconds,
            '-StageTimeoutSeconds', [string]$StageTimeoutSeconds,
            '-DesktopSessionPolicy', $DesktopSessionPolicy
        )
        if ($SkipDesktopReload) {
            $childArguments += '-SkipDesktopReload'
        }
        $runnerArguments = @(
            $runnerScript,
            '--log-file', $logPath,
            '--result-file', $processResultPath,
            '--stage', $selectedStage,
            '--heartbeat-seconds', [string]$HeartbeatSeconds,
            '--timeout-seconds', [string]$timeoutSeconds,
            '--',
            $powershellExecutable
        ) + $childArguments
        & python @runnerArguments | ForEach-Object { Write-Host $_ }
        $runnerExitCode = $LASTEXITCODE
        if (Test-Path -LiteralPath $processResultPath -PathType Leaf) {
            $processResult = Get-Content -LiteralPath $processResultPath -Raw | ConvertFrom-Json
            $exitCode = [int]$processResult.exit_code
            $durationMilliseconds = [int64]$processResult.duration_ms
            $timedOut = [bool]$processResult.timed_out
        }
        else {
            $exitCode = if ($runnerExitCode -eq 0) { 3 } else { $runnerExitCode }
            $durationMilliseconds = 0
            $timedOut = $false
        }
        $status = if ($exitCode -eq 0) { 'passed' } elseif ($exitCode -eq 4) { 'blocked' } else { 'failed' }
        $blockedAt = $null
        $blockedReason = $null
        if ($status -eq 'blocked') {
            $blockedAt = (Get-Date).ToUniversalTime().ToString('o')
            if (Test-Path -LiteralPath $logPath -PathType Leaf) {
                $blockedReason = Get-Content -LiteralPath $logPath | Where-Object {
                    -not [string]::IsNullOrWhiteSpace($_)
                } | Select-Object -Last 1
            }
            if ([string]::IsNullOrWhiteSpace($blockedReason)) {
                $blockedReason = 'unspecified_blocker'
            }
        }
        $stageResults.Add([pscustomobject]@{
            stage = $selectedStage
            status = $status
            exit_code = $exitCode
            duration_ms = $durationMilliseconds
            timed_out = $timedOut
            timeout_seconds = $timeoutSeconds
            log_file = "evidence/runs/$runId/$selectedStage.log"
            blocked_at = $blockedAt
            blocked_reason = $blockedReason
        })
        Write-Host "stage_complete stage=$selectedStage status=$status exit_code=$exitCode duration_ms=$durationMilliseconds timed_out=$($timedOut.ToString().ToLower())"
        if ($exitCode -ne 0) { break }
    }
    $stageResults | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultsPath -Encoding UTF8
    if ($stageResults.Count -eq 0) { '[]' | Set-Content -LiteralPath $resultsPath -Encoding UTF8 }
    $mode = if ($ReleaseMode) { 'release' } else { 'resume' }
    & python $runtimeScript finalize --project-path $targetPath --run-id $runId --mode $mode --plan-file $planPath --results-file $resultsPath | ForEach-Object { Write-Host $_ }
    $finalizeExit = $LASTEXITCODE
    Write-Host "workflow_run=$runId stages=$($stageResults.Count)"
    return $finalizeExit
}

try {
    $exitCode = switch ($Stage) {
        'New' { Invoke-NewStage }
        'Preflight' { Invoke-PreflightStage }
        'ValidateStructure' { Invoke-ValidateStructureStage }
        'ValidateDataContract' { Invoke-DataQualityStage -Mode 'validate-contract' }
        'TestDataQuality' { Invoke-DataQualityStage -Mode 'test-data' }
        'ValidateMetrics' { Invoke-PythonProjectCheck -ScriptName 'Test-BIMetrics.py' }
        'ValidateModelSpec' { Invoke-PythonProjectCheck -ScriptName 'Test-BIModelSpec.py' }
        'ValidatePowerBIProject' { Invoke-PythonProjectCheck -ScriptName 'Test-BIPowerBIProject.py' }
        'ValidateDocumentation' { Invoke-DocumentationStage }
        'ValidateUIContract' { Invoke-UIContractStage }
        'ValidatePrototype' { Invoke-PrototypeStage }
        'GenerateReport' { Invoke-GenerateReportStage }
        'ValidateReportQA' { Invoke-PythonProjectCheck -ScriptName 'Test-BIReportQA.py' }
        'DesktopPreflight' { Invoke-DesktopPreflightStage -RunDirectory $InternalRunDirectory }
        'DesktopRefresh' { Invoke-DesktopRefreshStage -RunDirectory $InternalRunDirectory }
        'DesktopMetrics' { Invoke-DesktopMetricsStage -RunDirectory $InternalRunDirectory }
        'DesktopRls' { Invoke-DesktopRlsStage -RunDirectory $InternalRunDirectory }
        'CaptureDesktopScreenshots' { Invoke-CaptureDesktopScreenshotsStage -RunDirectory $InternalRunDirectory }
        'DesktopQA' { Invoke-DesktopQAStage -RunDirectory $InternalRunDirectory }
        'ValidateRelease' { Invoke-ReleaseStage -RunDirectory $InternalRunDirectory }
        'ValidateAll' { Invoke-ValidateAllStage }
        'Resume' { Invoke-ResumableStage -ReleaseMode $false }
        'Release' { Invoke-ResumableStage -ReleaseMode $true }
    }
    exit $exitCode
}
catch {
    Write-Error $_
    exit 3
}
