[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$workflowScript = Join-Path $repoRoot 'scripts\Invoke-BIWorkflow.ps1'
$sandboxRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bi-workflow-test-' + [guid]::NewGuid().ToString('N'))
$projectPath = Join-Path $sandboxRoot 'sample-bi-project'

$script:passed = 0
$script:failed = 0

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if ($Condition) {
        $script:passed++
        Write-Host "PASS: $Message" -ForegroundColor Green
        return
    }

    $script:failed++
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

function Invoke-WorkflowProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $outputFile = Join-Path $sandboxRoot ('stdout-' + [guid]::NewGuid().ToString('N') + '.txt')
    $errorFile = Join-Path $sandboxRoot ('stderr-' + [guid]::NewGuid().ToString('N') + '.txt')

    $processArguments = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        ('"{0}"' -f $workflowScript)
    )
    $processArguments += $Arguments | ForEach-Object {
        '"{0}"' -f ([string]$_).Replace('"', '\"')
    }

    $process = Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList $processArguments `
        -Wait `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outputFile `
        -RedirectStandardError $errorFile

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = ((Get-Content -LiteralPath $outputFile -Raw -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath $errorFile -Raw -ErrorAction SilentlyContinue))
    }
}

function Write-JsonFile {
    param([string]$RelativePath, [object]$Value)
    $fullPath = Join-Path $projectPath $RelativePath
    $parent = Split-Path -Parent $fullPath
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $fullPath -Encoding UTF8
}

function Initialize-MinimalPowerBIProject {
    param(
        [string]$ReportName = 'Test.Report',
        [string]$SemanticModelName = 'Test.SemanticModel'
    )

    Write-JsonFile -RelativePath 'Test.pbip' -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json'
        version = '1.0'
        artifacts = @(
            [ordered]@{
                report = [ordered]@{
                    path = $ReportName
                }
            }
        )
    })

    Write-JsonFile -RelativePath (Join-Path $ReportName 'definition.pbir') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json'
        version = '4.0'
        datasetReference = [ordered]@{
            byPath = [ordered]@{
                path = "../$SemanticModelName"
            }
        }
    })

    Write-JsonFile -RelativePath (Join-Path $ReportName 'definition\report.json') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json'
        themeCollection = [ordered]@{}
        reportSource = 'Default'
    })

    Write-JsonFile -RelativePath (Join-Path $ReportName 'definition\version.json') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json'
        version = '4.0.0'
    })

    Write-JsonFile -RelativePath (Join-Path $ReportName 'definition\pages\pages.json') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json'
        pageOrder = @('Overview')
        activePageName = 'Overview'
    })

    Write-JsonFile -RelativePath (Join-Path $ReportName 'definition\pages\Overview\page.json') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json'
        name = 'Overview'
        displayName = 'Overview'
        displayOption = 'FitToPage'
        height = 720
        width = 1280
    })

    Write-JsonFile -RelativePath (Join-Path $SemanticModelName 'definition.pbism') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json'
        version = '4.0'
    })

    $definitionPath = Join-Path $projectPath (Join-Path $SemanticModelName 'definition')
    New-Item -ItemType Directory -Path (Join-Path $definitionPath 'tables') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $definitionPath 'database.tmdl') -Value "database Test`n`tcompatibilityLevel: 1600" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $definitionPath 'model.tmdl') -Value "model Model`n`tref table FactOrders" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $definitionPath 'relationships.tmdl') -Value "createOrReplace`n" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $definitionPath 'tables\FactOrders.tmdl') -Value @'
table FactOrders
	partition FactOrders = m
		mode: import
		source =
				let
				    Source = Csv.Document(File.Contents(SourceCsvPath), [Delimiter=",", Columns=2, Encoding=65001, QuoteStyle=QuoteStyle.Csv])
				in
				    Source
'@ -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $definitionPath 'expressions.tmdl') -Value @'
expression SourceCsvPath = "data/sample/orders.csv" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
'@ -Encoding UTF8
}

function Initialize-MinimalMetricModelContracts {
    $metrics = @'
{
  "schema_version": 1,
  "dataset": "Synthetic test orders",
  "metrics": [
    {
      "id": "order_count",
      "name": "Order Count",
      "aggregation": "distinct_count",
      "column": "order_id",
      "expected": 2,
      "tolerance": 0,
      "format_string": "0"
    },
    {
      "id": "revenue",
      "name": "Revenue",
      "aggregation": "sum",
      "column": "revenue",
      "expected": 449.5,
      "tolerance": 0.01,
      "format_string": "#,0.00"
    }
  ]
}
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'config\metrics.json') -Value $metrics -Encoding UTF8

    $modelSpec = @'
{
  "schema_version": 1,
  "model": {
    "name": "Synthetic Test Model",
    "fact_table": "FactOrders",
    "date_table": "DimDate"
  },
  "tables": [
    {
      "name": "FactOrders",
      "kind": "fact",
      "grain": "one row per order",
      "source": "data/sample/orders.csv",
      "columns": [
        "order_id",
        "order_date",
        "region",
        "quantity",
        "revenue"
      ]
    },
    {
      "name": "DimDate",
      "kind": "date",
      "primary_key": "Date",
      "columns": [
        "Date",
        "Year",
        "Month"
      ]
    }
  ],
  "relationships": [
    {
      "from_table": "FactOrders",
      "from_column": "order_date",
      "to_table": "DimDate",
      "to_column": "Date",
      "cardinality": "many-to-one",
      "active": true
    }
  ],
  "measures": [
    {
      "name": "Order Count",
      "metric_id": "order_count",
      "table": "FactOrders",
      "expression": "DISTINCTCOUNT(FactOrders[order_id])",
      "format_string": "0"
    },
    {
      "name": "Revenue",
      "metric_id": "revenue",
      "table": "FactOrders",
      "expression": "SUM(FactOrders[revenue])",
      "format_string": "#,0.00"
    }
  ]
}
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'model\model-spec.json') -Value $modelSpec -Encoding UTF8
}

function Set-ReportQAGateResult {
    param(
        [string]$ReportResult,
        [string]$ReleaseResult = 'Blocked',
        [string]$DesktopRenderResult = 'Pending'
    )

    $qaReport = @"
# QA report

## Gate summary

| Gate | Evidence | Result | Reviewer |
|---|---|---|---|
| Scope | `docs/scope.md` | Passed | Automated |
| Report | PBIR page and visual files, manual visual QA checklist | $ReportResult | Portfolio project owner |
| Release | Manual publish, refresh, permission, and performance checks | $ReleaseResult | Portfolio project owner |

## Manual report QA checklist

- Refresh: must be verified in Power BI Desktop before delivery.
- Visual interactions: must be reviewed by a human.
- Performance: must be checked before release.
- Release: must remain blocked until publish and permissions are approved.

## Desktop render evidence

- Status: $DesktopRenderResult
"@
    Set-Content -LiteralPath (Join-Path $projectPath 'docs\qa-report.md') -Value $qaReport -Encoding UTF8
}

function Add-MinimalPBIRVisual {
    param([string]$ReportName = 'Test.Report')

    $visualFolder = Join-Path $projectPath (Join-Path $ReportName 'definition\pages\Overview\visuals\Visual1')
    New-Item -ItemType Directory -Path $visualFolder -Force | Out-Null
    Write-JsonFile -RelativePath (Join-Path $ReportName 'definition\pages\Overview\visuals\Visual1\visual.json') -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.1.0/schema.json'
        name = 'Visual1'
        position = [ordered]@{
            x = 0
            y = 0
            z = 0
            height = 120
            width = 240
        }
        visual = [ordered]@{
            visualType = 'card'
        }
    })
}

try {
    New-Item -ItemType Directory -Path $sandboxRoot -Force | Out-Null

    Assert-True -Condition (Test-Path -LiteralPath $workflowScript -PathType Leaf) -Message 'Workflow entry script exists'
    if (-not (Test-Path -LiteralPath $workflowScript -PathType Leaf)) {
        throw "Missing workflow script: $workflowScript"
    }

    $newResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'New',
        '-ProjectPath', $projectPath,
        '-ProjectName', 'Sample BI Project'
    )
    Assert-True -Condition ($newResult.ExitCode -eq 0) -Message 'New stage initializes a project'

    $requiredPaths = @(
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

    foreach ($relativePath in $requiredPaths) {
        $fullPath = Join-Path $projectPath $relativePath
        Assert-True -Condition (Test-Path -LiteralPath $fullPath -PathType Leaf) -Message "Template contains $relativePath"
    }

    $projectConfig = Get-Content -LiteralPath (Join-Path $projectPath 'project.yaml') -Raw
    Assert-True -Condition ($projectConfig -match 'Sample BI Project') -Message 'New stage replaces the project name placeholder'

    $preflightResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'Preflight',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($preflightResult.ExitCode -eq 0) -Message 'Preflight stage succeeds'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\workflow\preflight.json')) -Message 'Preflight writes JSON evidence'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\workflow\preflight.md')) -Message 'Preflight writes Markdown evidence'
    $preflightEvidence = Get-Content -LiteralPath (Join-Path $projectPath 'evidence\workflow\preflight.json') -Raw | ConvertFrom-Json
    Assert-True -Condition (-not [System.IO.Path]::IsPathRooted($preflightEvidence.project_path)) -Message 'Workflow evidence does not expose the local absolute project path'

    $validationResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateStructure',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($validationResult.ExitCode -eq 0) -Message 'Complete template passes structure validation'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\workflow\structure-validation.json')) -Message 'Structure validation writes JSON evidence'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\workflow\structure-validation.md')) -Message 'Structure validation writes Markdown evidence'

    Initialize-MinimalPowerBIProject
    $powerBIProjectResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidatePowerBIProject',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($powerBIProjectResult.ExitCode -eq 0) -Message 'Valid Power BI project passes validation'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\model\powerbi-project-validation.json')) -Message 'Power BI project validation writes JSON evidence'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\model\powerbi-project-validation.md')) -Message 'Power BI project validation writes Markdown evidence'

    Remove-Item -LiteralPath (Join-Path $projectPath 'Test.Report\definition\version.json') -Force
    $missingVersionResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidatePowerBIProject',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($missingVersionResult.ExitCode -ne 0 -and $missingVersionResult.Output -match 'report_definition_version_missing') -Message 'Missing PBIR version.json fails validation'

    Initialize-MinimalPowerBIProject
    Remove-Item -LiteralPath (Join-Path $projectPath 'Test.SemanticModel\definition.pbism') -Force
    $missingPbismResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidatePowerBIProject',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($missingPbismResult.ExitCode -ne 0 -and $missingPbismResult.Output -match 'semantic_model_definition_missing') -Message 'Missing semantic model definition.pbism fails validation'

    Initialize-MinimalPowerBIProject
    Write-JsonFile -RelativePath 'Test.Report\definition.pbir' -Value ([ordered]@{
        '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json'
        version = '4.0'
        datasetReference = [ordered]@{
            byPath = [ordered]@{
                path = '../Missing.SemanticModel'
            }
        }
    })
    $missingModelPathResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidatePowerBIProject',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($missingModelPathResult.ExitCode -ne 0 -and $missingModelPathResult.Output -match 'semantic_model_path_missing') -Message 'Invalid PBIR semantic model path fails validation'

    Initialize-MinimalPowerBIProject
    Set-Content -LiteralPath (Join-Path $projectPath 'Test.SemanticModel\definition\tables\FactOrders.tmdl') -Value @'
table FactOrders
	partition FactOrders = m
		mode: import
		source =
				let
				    Source = Csv.Document(File.Contents("C:/Users/w/Desktop/Power BI/data/sample/orders.csv"), [Delimiter=",", Columns=2, Encoding=65001, QuoteStyle=QuoteStyle.Csv])
				in
				    Source
'@ -Encoding UTF8
    $absoluteSourcePathResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidatePowerBIProject',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($absoluteSourcePathResult.ExitCode -ne 0 -and $absoluteSourcePathResult.Output -match 'absolute_tmdl_source_path') -Message 'Absolute TMDL source path fails validation'

    Initialize-MinimalPowerBIProject
    Remove-Item -LiteralPath (Join-Path $projectPath 'Test.SemanticModel\definition\expressions.tmdl') -Force
    $missingSourceParameterResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidatePowerBIProject',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($missingSourceParameterResult.ExitCode -ne 0 -and $missingSourceParameterResult.Output -match 'missing_tmdl_source_parameter') -Message 'Missing TMDL source parameter fails validation'

    $contract = @'
{
  "schema_version": 1,
  "dataset": {
    "name": "Synthetic retail orders",
    "grain": "one row per order",
    "source": {
      "type": "csv",
      "path": "data/sample/orders.csv",
      "encoding": "utf-8-sig",
      "delimiter": ","
    },
    "primary_key": ["order_id"]
  },
  "expectations": {
    "min_rows": 2,
    "max_rows": 10
  },
  "columns": [
    {
      "name": "order_id",
      "type": "string",
      "required": true,
      "nullable": false
    },
    {
      "name": "order_date",
      "type": "date",
      "format": "%Y-%m-%d",
      "required": true,
      "nullable": false
    },
    {
      "name": "region",
      "type": "string",
      "required": true,
      "nullable": false,
      "allowed_values": ["East", "West"]
    },
    {
      "name": "quantity",
      "type": "integer",
      "required": true,
      "nullable": false,
      "min": 1,
      "max": 100
    },
    {
      "name": "revenue",
      "type": "number",
      "required": true,
      "nullable": false,
      "min": 0
    }
  ]
}
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'config\data-contract.json') -Value $contract -Encoding UTF8

    $validCsv = @'
order_id,order_date,region,quantity,revenue
O-001,2026-01-01,East,2,199.50
O-002,2026-01-02,West,3,250.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $validCsv -Encoding UTF8

    $contractResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateDataContract',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($contractResult.ExitCode -eq 0) -Message 'Valid data contract passes validation'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\data-quality\contract-validation.json')) -Message 'Contract validation writes JSON evidence'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\data-quality\contract-validation.md')) -Message 'Contract validation writes Markdown evidence'

    $dataResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'TestDataQuality',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($dataResult.ExitCode -eq 0) -Message 'Valid CSV passes data quality checks'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\data-quality\data-quality.json')) -Message 'Data quality writes JSON evidence'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\data-quality\data-quality.md')) -Message 'Data quality writes Markdown evidence'
    $dataQualityEvidence = Get-Content -LiteralPath (Join-Path $projectPath 'evidence\data-quality\data-quality.json') -Raw | ConvertFrom-Json
    $dataEvidenceUsesRelativePaths = -not [System.IO.Path]::IsPathRooted($dataQualityEvidence.project_path)
    $dataEvidenceUsesRelativePaths = $dataEvidenceUsesRelativePaths -and -not [System.IO.Path]::IsPathRooted($dataQualityEvidence.summary.data_path)
    Assert-True -Condition $dataEvidenceUsesRelativePaths -Message 'Data-quality evidence does not expose local absolute paths'

    $missingColumnCsv = @'
order_id,order_date,region,quantity
O-001,2026-01-01,East,2
O-002,2026-01-02,West,3
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $missingColumnCsv -Encoding UTF8
    $missingColumnResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($missingColumnResult.ExitCode -ne 0 -and $missingColumnResult.Output -match 'missing_required_column') -Message 'Missing required column fails with a clear code'

    $duplicateCsv = @'
order_id,order_date,region,quantity,revenue
O-001,2026-01-01,East,2,199.50
O-001,2026-01-02,West,3,250.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $duplicateCsv -Encoding UTF8
    $duplicateDataResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($duplicateDataResult.ExitCode -ne 0 -and $duplicateDataResult.Output -match 'duplicate_primary_key') -Message 'Duplicate primary key fails with a clear code'

    $nullCsv = @'
order_id,order_date,region,quantity,revenue
O-001,2026-01-01,,2,199.50
O-002,2026-01-02,West,3,250.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $nullCsv -Encoding UTF8
    $nullResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($nullResult.ExitCode -ne 0 -and $nullResult.Output -match 'null_not_allowed') -Message 'Null in a required field fails with a clear code'

    $typeCsv = @'
order_id,order_date,region,quantity,revenue
O-001,2026-01-01,East,two,199.50
O-002,2026-01-02,West,3,250.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $typeCsv -Encoding UTF8
    $typeResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($typeResult.ExitCode -ne 0 -and $typeResult.Output -match 'invalid_type') -Message 'Invalid type fails with a clear code'

    $rangeCsv = @'
order_id,order_date,region,quantity,revenue
O-001,2026-01-01,East,101,199.50
O-002,2026-01-02,West,3,250.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $rangeCsv -Encoding UTF8
    $rangeResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($rangeResult.ExitCode -ne 0 -and $rangeResult.Output -match 'above_maximum') -Message 'Out-of-range value fails with a clear code'

    $allowedCsv = @'
order_id,order_date,region,quantity,revenue
O-001,2026-01-01,North,2,199.50
O-002,2026-01-02,West,3,250.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $allowedCsv -Encoding UTF8
    $allowedResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($allowedResult.ExitCode -ne 0 -and $allowedResult.Output -match 'not_allowed') -Message 'Value outside allowed values fails with a clear code'

    $invalidContract = $contract.Replace('"type": "integer"', '"type": "currency"')
    Set-Content -LiteralPath (Join-Path $projectPath 'config\data-contract.json') -Value $invalidContract -Encoding UTF8
    $invalidContractResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateDataContract', '-ProjectPath', $projectPath)
    Assert-True -Condition ($invalidContractResult.ExitCode -ne 0 -and $invalidContractResult.Output -match 'unsupported_type') -Message 'Unsupported contract type fails with a clear code'

    Set-Content -LiteralPath (Join-Path $projectPath 'config\data-contract.json') -Value $contract -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $validCsv -Encoding UTF8
    Initialize-MinimalMetricModelContracts

    Initialize-MinimalPowerBIProject
    $reportQAResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateReportQA',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($reportQAResult.ExitCode -ne 0 -and $reportQAResult.Output -match 'report_qa_failed') -Message 'Report QA fails when report visuals and manual checks are missing'
    $reportQAEvidencePath = Join-Path $projectPath 'evidence\report\report-qa.json'
    Assert-True -Condition (Test-Path -LiteralPath $reportQAEvidencePath) -Message 'Report QA writes JSON evidence when blocked'
    if (Test-Path -LiteralPath $reportQAEvidencePath) {
        $reportQAEvidence = Get-Content -LiteralPath $reportQAEvidencePath -Raw | ConvertFrom-Json
        Assert-True -Condition ($reportQAEvidence.status -eq 'blocked') -Message 'Report QA marks incomplete report work as blocked'
        Assert-True -Condition (@($reportQAEvidence.issues | Where-Object { $_.code -eq 'report_visuals_missing' }).Count -gt 0) -Message 'Report QA identifies missing report visuals'
    }
    else {
        Assert-True -Condition $false -Message 'Report QA marks incomplete report work as blocked'
        Assert-True -Condition $false -Message 'Report QA identifies missing report visuals'
    }

    Add-MinimalPBIRVisual
    Set-ReportQAGateResult -ReportResult 'Passed'
    $draftReportQAResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateReportQA',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($draftReportQAResult.ExitCode -eq 0 -and $draftReportQAResult.Output -match 'report_qa_passed') -Message 'Report QA allows Pending Desktop evidence before DesktopQA'
    if (Test-Path -LiteralPath $reportQAEvidencePath) {
        $draftReportQAEvidence = Get-Content -LiteralPath $reportQAEvidencePath -Raw | ConvertFrom-Json
        Assert-True -Condition ($draftReportQAEvidence.status -eq 'passed' -and $draftReportQAEvidence.summary.desktop_render_status -eq 'Pending') -Message 'Report QA preserves Pending Desktop evidence for the downstream gate'
    }
    else {
        Assert-True -Condition $false -Message 'Report QA preserves Pending Desktop evidence for the downstream gate'
    }

    Set-ReportQAGateResult -ReportResult 'Passed' -DesktopRenderResult 'Blocked: Desktop validation could not run'
    $blockedDesktopReportQAResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateReportQA',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($blockedDesktopReportQAResult.ExitCode -ne 0 -and $blockedDesktopReportQAResult.Output -match 'desktop_render_failed') -Message 'Report QA blocks an explicit Desktop Failed or Blocked status'
    $blockedDesktopReportQAEvidence = Get-Content -LiteralPath $reportQAEvidencePath -Raw | ConvertFrom-Json
    Assert-True -Condition ($blockedDesktopReportQAEvidence.status -eq 'blocked') -Message 'Report QA evidence records an explicit Desktop blocker'

    Set-ReportQAGateResult -ReportResult 'Passed' -DesktopRenderResult 'Passed: opened in Power BI Desktop and reviewed by test owner'
    $passingReportQAResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateReportQA',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($passingReportQAResult.ExitCode -eq 0 -and $passingReportQAResult.Output -match 'report_qa_passed') -Message 'Report QA passes when PBIR visuals have Desktop render evidence'
    $passingReportQAEvidence = Get-Content -LiteralPath $reportQAEvidencePath -Raw | ConvertFrom-Json
    Assert-True -Condition ($passingReportQAEvidence.status -eq 'passed') -Message 'Report QA evidence status is passed for a Desktop-rendered report'

    Initialize-MinimalPowerBIProject
    $validateAllResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateAll',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($validateAllResult.ExitCode -eq 0) -Message 'ValidateAll succeeds when every quality gate passes'
    $validationSummaryPath = Join-Path $projectPath 'evidence\workflow\validation-summary.json'
    $validationSummaryMarkdownPath = Join-Path $projectPath 'evidence\workflow\validation-summary.md'
    $validationSummaryExists = Test-Path -LiteralPath $validationSummaryPath
    Assert-True -Condition $validationSummaryExists -Message 'ValidateAll writes JSON summary evidence'
    Assert-True -Condition (Test-Path -LiteralPath $validationSummaryMarkdownPath) -Message 'ValidateAll writes Markdown summary evidence'
    if ($validationSummaryExists) {
        $validationSummary = Get-Content -LiteralPath $validationSummaryPath -Raw | ConvertFrom-Json
        Assert-True -Condition ($validationSummary.status -eq 'passed') -Message 'ValidateAll summary status is passed for a valid project'
        Assert-True -Condition (@($validationSummary.stages).Count -eq 7) -Message 'ValidateAll summary records all seven quality gates'
        Assert-True -Condition (($validationSummary.stages | Where-Object { $_.stage -eq 'ValidatePowerBIProject' }).status -eq 'passed') -Message 'ValidateAll includes the Power BI project gate'
    }
    else {
        Assert-True -Condition $false -Message 'ValidateAll summary status is passed for a valid project'
        Assert-True -Condition $false -Message 'ValidateAll summary records all seven quality gates'
        Assert-True -Condition $false -Message 'ValidateAll includes the Power BI project gate'
    }

    Set-Content -LiteralPath (Join-Path $projectPath 'do-not-overwrite.txt') -Value 'preserve'
    $duplicateResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'New',
        '-ProjectPath', $projectPath,
        '-ProjectName', 'Replacement'
    )
    Assert-True -Condition ($duplicateResult.ExitCode -ne 0) -Message 'New stage refuses to overwrite an existing directory'
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $projectPath 'do-not-overwrite.txt') -Raw).Trim() -eq 'preserve') -Message 'Existing files remain unchanged after refusal'

    Remove-Item -LiteralPath (Join-Path $projectPath 'docs\data-contract.md') -Force
    $validateAllFailureResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateAll',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($validateAllFailureResult.ExitCode -ne 0 -and $validateAllFailureResult.Output -match 'validate_all_failed') -Message 'ValidateAll fails when any quality gate fails'
    $failedValidationSummaryPath = Join-Path $projectPath 'evidence\workflow\validation-summary.json'
    if (Test-Path -LiteralPath $failedValidationSummaryPath) {
        $failedValidationSummary = Get-Content -LiteralPath $failedValidationSummaryPath -Raw | ConvertFrom-Json
        Assert-True -Condition ($failedValidationSummary.status -eq 'failed') -Message 'ValidateAll summary status is failed when a gate fails'
        Assert-True -Condition (($failedValidationSummary.stages | Where-Object { $_.stage -eq 'ValidateStructure' }).status -eq 'failed') -Message 'ValidateAll summary identifies the failed quality gate'
    }
    else {
        Assert-True -Condition $false -Message 'ValidateAll summary status is failed when a gate fails'
        Assert-True -Condition $false -Message 'ValidateAll summary identifies the failed quality gate'
    }

    $invalidResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'ValidateStructure',
        '-ProjectPath', $projectPath
    )
    Assert-True -Condition ($invalidResult.ExitCode -ne 0) -Message 'Structure validation fails when a required file is missing'
    Assert-True -Condition ($invalidResult.Output -match 'docs.data-contract.md|data-contract.md') -Message 'Structure validation identifies the missing file'

    $gitignore = Get-Content -LiteralPath (Join-Path $projectPath '.gitignore') -Raw
    Assert-True -Condition ($gitignore -match 'data/raw') -Message 'Template ignores raw data'
    Assert-True -Condition ($gitignore -match '\*\.pbix') -Message 'Template ignores PBIX binaries'
    Assert-True -Condition ($gitignore -match '\.env') -Message 'Template ignores credential environment files'
}
finally {
    if (Test-Path -LiteralPath $sandboxRoot) {
        $resolvedSandbox = [System.IO.Path]::GetFullPath($sandboxRoot)
        $resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if ($resolvedSandbox.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedSandbox -Recurse -Force
        }
    }
}

Write-Host "RESULT: $script:passed passed, $script:failed failed"
if ($script:failed -gt 0) {
    exit 1
}

exit 0
