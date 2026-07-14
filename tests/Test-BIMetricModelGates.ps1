[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$workflowScript = Join-Path $repoRoot 'scripts\Invoke-BIWorkflow.ps1'
$sandboxRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bi-gates-test-' + [guid]::NewGuid().ToString('N'))
$projectPath = Join-Path $sandboxRoot 'metric-model-project'

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

function Invoke-WorkflowProcess {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

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

try {
    New-Item -ItemType Directory -Path $sandboxRoot -Force | Out-Null

    $newResult = Invoke-WorkflowProcess -Arguments @(
        '-Stage', 'New',
        '-ProjectPath', $projectPath,
        '-ProjectName', 'Metric Model Test'
    )
    Assert-True -Condition ($newResult.ExitCode -eq 0) -Message 'Test project initializes'

    $contract = [ordered]@{
        schema_version = 1
        dataset = [ordered]@{
            name = 'Orders'
            grain = 'one row per order'
            source = [ordered]@{
                type = 'csv'
                path = 'data/sample/orders.csv'
                encoding = 'utf-8-sig'
                delimiter = ','
            }
            primary_key = @('order_id')
        }
        expectations = [ordered]@{ min_rows = 2; max_rows = 10 }
        columns = @(
            [ordered]@{ name = 'order_id'; type = 'string'; required = $true; nullable = $false; unique = $true },
            [ordered]@{ name = 'order_date'; type = 'date'; format = '%Y-%m-%d'; required = $true; nullable = $false },
            [ordered]@{ name = 'region'; type = 'string'; required = $true; nullable = $false },
            [ordered]@{ name = 'channel'; type = 'string'; required = $true; nullable = $false },
            [ordered]@{ name = 'category'; type = 'string'; required = $true; nullable = $false },
            [ordered]@{ name = 'quantity'; type = 'integer'; required = $true; nullable = $false; min = 1 },
            [ordered]@{ name = 'unit_price'; type = 'number'; required = $true; nullable = $false; min = 0 },
            [ordered]@{ name = 'discount_rate'; type = 'number'; required = $true; nullable = $false; min = 0; max = 1 },
            [ordered]@{ name = 'revenue'; type = 'number'; required = $true; nullable = $false; min = 0 }
        )
        row_rules = @(
            [ordered]@{
                name = 'revenue_reconciliation'
                type = 'formula'
                target = 'revenue'
                expression = 'quantity * unit_price * (1 - discount_rate)'
                tolerance = 0.01
            }
        )
    }
    Write-JsonFile -RelativePath 'config\data-contract.json' -Value $contract

    $validCsv = @'
order_id,order_date,region,channel,category,quantity,unit_price,discount_rate,revenue
O-001,2026-01-01,East,Online,Electronics,2,100.00,0.10,180.00
O-002,2026-01-02,West,Store,Home,3,40.00,0.00,120.00
'@
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $validCsv -Encoding UTF8

    $formulaPassResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($formulaPassResult.ExitCode -eq 0) -Message 'Valid cross-column revenue formula passes'

    $invalidRevenueCsv = $validCsv.Replace('180.00', '181.00')
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $invalidRevenueCsv -Encoding UTF8
    $formulaFailResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'TestDataQuality', '-ProjectPath', $projectPath)
    Assert-True -Condition ($formulaFailResult.ExitCode -ne 0 -and $formulaFailResult.Output -match 'formula_mismatch') -Message 'Revenue mismatch fails with formula_mismatch'
    Set-Content -LiteralPath (Join-Path $projectPath 'data\sample\orders.csv') -Value $validCsv -Encoding UTF8

    $unsafeContract = $contract | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $unsafeContract.row_rules[0].expression = '__import__("os").system("echo unsafe")'
    Write-JsonFile -RelativePath 'config\data-contract.json' -Value $unsafeContract
    $unsafeFormulaResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateDataContract', '-ProjectPath', $projectPath)
    Assert-True -Condition ($unsafeFormulaResult.ExitCode -ne 0 -and $unsafeFormulaResult.Output -match 'unsupported_formula_expression') -Message 'Unsafe formula expression is rejected'
    Write-JsonFile -RelativePath 'config\data-contract.json' -Value $contract

    $metrics = [ordered]@{
        schema_version = 1
        dataset = 'Synthetic retail orders'
        metrics = @(
            [ordered]@{ id = 'order_count'; name = 'Order Count'; aggregation = 'distinct_count'; column = 'order_id'; expected = 2; tolerance = 0; format_string = '0' },
            [ordered]@{ id = 'revenue'; name = 'Revenue'; aggregation = 'sum'; column = 'revenue'; expected = 300; tolerance = 0.01; format_string = '#,0.00' },
            [ordered]@{ id = 'units_sold'; name = 'Units Sold'; aggregation = 'sum'; column = 'quantity'; expected = 5; tolerance = 0; format_string = '0' },
            [ordered]@{ id = 'average_order_value'; name = 'Average Order Value'; aggregation = 'ratio'; numerator_metric = 'revenue'; denominator_metric = 'order_count'; expected = 150; tolerance = 0.01; format_string = '#,0.00' },
            [ordered]@{ id = 'average_discount_rate'; name = 'Average Discount Rate'; aggregation = 'average'; column = 'discount_rate'; expected = 0.05; tolerance = 0.000001; format_string = '0.00%' }
        )
    }
    Write-JsonFile -RelativePath 'config\metrics.json' -Value $metrics

    $modelSpec = [ordered]@{
        schema_version = 1
        model = [ordered]@{
            name = 'Retail Sales Model'
            fact_table = 'FactOrders'
            date_table = 'DimDate'
        }
        tables = @(
            [ordered]@{ name = 'FactOrders'; kind = 'fact'; grain = 'one row per order'; source = 'data/sample/orders.csv'; columns = @('order_id','order_date','region','channel','category','quantity','unit_price','discount_rate','revenue') },
            [ordered]@{ name = 'DimDate'; kind = 'date'; primary_key = 'Date'; columns = @('Date','Year','Month') },
            [ordered]@{ name = 'DimRegion'; kind = 'dimension'; primary_key = 'Region'; columns = @('Region') },
            [ordered]@{ name = 'DimChannel'; kind = 'dimension'; primary_key = 'Channel'; columns = @('Channel') },
            [ordered]@{ name = 'DimCategory'; kind = 'dimension'; primary_key = 'Category'; columns = @('Category') }
        )
        relationships = @(
            [ordered]@{ from_table = 'FactOrders'; from_column = 'order_date'; to_table = 'DimDate'; to_column = 'Date'; cardinality = 'many-to-one'; active = $true },
            [ordered]@{ from_table = 'FactOrders'; from_column = 'region'; to_table = 'DimRegion'; to_column = 'Region'; cardinality = 'many-to-one'; active = $true },
            [ordered]@{ from_table = 'FactOrders'; from_column = 'channel'; to_table = 'DimChannel'; to_column = 'Channel'; cardinality = 'many-to-one'; active = $true },
            [ordered]@{ from_table = 'FactOrders'; from_column = 'category'; to_table = 'DimCategory'; to_column = 'Category'; cardinality = 'many-to-one'; active = $true }
        )
        measures = @(
            [ordered]@{ name = 'Order Count'; metric_id = 'order_count'; table = 'FactOrders'; expression = 'DISTINCTCOUNT(FactOrders[order_id])'; format_string = '0' },
            [ordered]@{ name = 'Revenue'; metric_id = 'revenue'; table = 'FactOrders'; expression = 'SUM(FactOrders[revenue])'; format_string = '#,0.00' },
            [ordered]@{ name = 'Units Sold'; metric_id = 'units_sold'; table = 'FactOrders'; expression = 'SUM(FactOrders[quantity])'; format_string = '0' },
            [ordered]@{ name = 'Average Order Value'; metric_id = 'average_order_value'; table = 'FactOrders'; expression = 'DIVIDE([Revenue], [Order Count])'; format_string = '#,0.00' },
            [ordered]@{ name = 'Average Discount Rate'; metric_id = 'average_discount_rate'; table = 'FactOrders'; expression = 'AVERAGE(FactOrders[discount_rate])'; format_string = '0.00%' }
        )
    }
    Write-JsonFile -RelativePath 'model\model-spec.json' -Value $modelSpec

    $metricsPassResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateMetrics', '-ProjectPath', $projectPath)
    Assert-True -Condition ($metricsPassResult.ExitCode -eq 0) -Message 'Valid metric contract passes'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\metrics\metrics-validation.json')) -Message 'Metric validation writes JSON evidence'
    $metricEvidence = Get-Content -LiteralPath (Join-Path $projectPath 'evidence\metrics\metrics-validation.json') -Raw | ConvertFrom-Json
    Assert-True -Condition ($metricEvidence.results.order_count.actual -eq 2) -Message 'Order Count is reproducible'
    Assert-True -Condition ([decimal]$metricEvidence.results.revenue.actual -eq [decimal]300) -Message 'Revenue is reproducible'
    Assert-True -Condition ([decimal]$metricEvidence.results.units_sold.actual -eq [decimal]5) -Message 'Units Sold is reproducible'
    Assert-True -Condition ([decimal]$metricEvidence.results.average_order_value.actual -eq [decimal]150) -Message 'Average Order Value is reproducible'
    Assert-True -Condition ([math]::Abs([double]$metricEvidence.results.average_discount_rate.actual - 0.05) -lt 0.000001) -Message 'Average Discount Rate is reproducible'

    $missingDefinition = $metrics | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $missingDefinition.metrics[0].PSObject.Properties.Remove('name')
    Write-JsonFile -RelativePath 'config\metrics.json' -Value $missingDefinition
    $missingMetricResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateMetrics', '-ProjectPath', $projectPath)
    Assert-True -Condition ($missingMetricResult.ExitCode -ne 0 -and $missingMetricResult.Output -match 'missing_metric_field') -Message 'Incomplete metric definition fails'

    $unsupportedMetrics = $metrics | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $unsupportedMetrics.metrics[0].aggregation = 'median'
    Write-JsonFile -RelativePath 'config\metrics.json' -Value $unsupportedMetrics
    $unsupportedMetricResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateMetrics', '-ProjectPath', $projectPath)
    Assert-True -Condition ($unsupportedMetricResult.ExitCode -ne 0 -and $unsupportedMetricResult.Output -match 'unsupported_aggregation') -Message 'Unsupported aggregation fails'

    $mismatchedMetrics = $metrics | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $mismatchedMetrics.metrics[1].expected = 999
    Write-JsonFile -RelativePath 'config\metrics.json' -Value $mismatchedMetrics
    $metricMismatchResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateMetrics', '-ProjectPath', $projectPath)
    Assert-True -Condition ($metricMismatchResult.ExitCode -ne 0 -and $metricMismatchResult.Output -match 'metric_mismatch') -Message 'Metric snapshot mismatch fails'
    Write-JsonFile -RelativePath 'config\metrics.json' -Value $metrics

    $modelPassResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateModelSpec', '-ProjectPath', $projectPath)
    Assert-True -Condition ($modelPassResult.ExitCode -eq 0) -Message 'Valid semantic model specification passes'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $projectPath 'evidence\model\model-spec-validation.json')) -Message 'Model specification writes JSON evidence'

    $missingFactGrain = $modelSpec | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $missingFactGrain.tables[0].PSObject.Properties.Remove('grain')
    Write-JsonFile -RelativePath 'model\model-spec.json' -Value $missingFactGrain
    $missingFactGrainResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateModelSpec', '-ProjectPath', $projectPath)
    Assert-True -Condition ($missingFactGrainResult.ExitCode -ne 0 -and $missingFactGrainResult.Output -match 'missing_fact_field') -Message 'Fact table without an explicit grain fails'

    $missingDate = $modelSpec | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $missingDate.tables = @($missingDate.tables | Where-Object { $_.name -ne 'DimDate' })
    Write-JsonFile -RelativePath 'model\model-spec.json' -Value $missingDate
    $missingDateResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateModelSpec', '-ProjectPath', $projectPath)
    Assert-True -Condition ($missingDateResult.ExitCode -ne 0 -and $missingDateResult.Output -match 'missing_date_table') -Message 'Missing date table fails'

    $invalidRelationship = $modelSpec | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $invalidRelationship.relationships[0].to_table = 'UnknownDate'
    Write-JsonFile -RelativePath 'model\model-spec.json' -Value $invalidRelationship
    $invalidRelationshipResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateModelSpec', '-ProjectPath', $projectPath)
    Assert-True -Condition ($invalidRelationshipResult.ExitCode -ne 0 -and $invalidRelationshipResult.Output -match 'unknown_relationship_table') -Message 'Relationship to unknown table fails'

    $unmappedMetric = $modelSpec | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $unmappedMetric.measures = @($unmappedMetric.measures | Where-Object { $_.metric_id -ne 'revenue' })
    Write-JsonFile -RelativePath 'model\model-spec.json' -Value $unmappedMetric
    $unmappedMetricResult = Invoke-WorkflowProcess -Arguments @('-Stage', 'ValidateModelSpec', '-ProjectPath', $projectPath)
    Assert-True -Condition ($unmappedMetricResult.ExitCode -ne 0 -and $unmappedMetricResult.Output -match 'unmapped_metric') -Message 'Metric without a measure mapping fails'
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
