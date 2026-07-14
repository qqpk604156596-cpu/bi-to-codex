[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath,

    [Parameter(Mandatory = $true)]
    [string]$PowerBIDesktopBin,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,

    [Parameter(Mandatory = $true)]
    [string]$BaselinePath,

    [int]$PerformanceThresholdMilliseconds = 3000
)

$ErrorActionPreference = 'Stop'
$startedAt = (Get-Date).ToUniversalTime().ToString('o')
$connection = $null
$rootConnection = $null
$catalog = ''

function Write-MetricEvidence {
    param(
        [string]$Status,
        [string]$Message,
        [object]$Result = $null
    )

    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
    [ordered]@{
        name = 'Power BI Desktop metric validation'
        status = $Status
        started_at = $startedAt
        completed_at = (Get-Date).ToUniversalTime().ToString('o')
        workspace_name = Split-Path -Leaf $WorkspacePath
        catalog = $catalog
        message = $Message
        source = 'Desktop local Analysis Services DAX query compared with approved MySQL baseline'
        mysql_credentials_written = $false
        result = $Result
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'desktop-metric-validation.json') -Encoding UTF8
}

function Get-DaxRow {
    param([string]$Query)

    $command = $connection.CreateCommand()
    $command.CommandText = $Query
    $reader = $command.ExecuteReader()
    try {
        if (-not $reader.Read()) {
            throw 'desktop_dax_query_returned_no_rows'
        }

        $row = [ordered]@{}
        for ($columnIndex = 0; $columnIndex -lt $reader.FieldCount; $columnIndex++) {
            $value = $reader.GetValue($columnIndex)
            $columnName = $reader.GetName($columnIndex).Trim([char[]]'[]')
            $row[$columnName] = if ($value -is [System.DBNull]) { $null } else { $value }
        }
        return $row
    }
    finally {
        $reader.Close()
    }
}

function Test-MetricValue {
    param(
        [object]$Actual,
        [object]$Expected
    )

    if ($null -eq $Expected) {
        return $null -eq $Actual
    }
    if ($null -eq $Actual) {
        return $false
    }
    return [math]::Abs(([decimal]$Actual) - ([decimal]$Expected)) -le [decimal]'0.0001'
}

try {
    $portFile = Join-Path $WorkspacePath 'Data\msmdsrv.port.txt'
    if (-not (Test-Path -LiteralPath $portFile -PathType Leaf)) {
        throw 'desktop_workspace_port_not_found'
    }
    $port = (Get-Content -LiteralPath $portFile -Raw -Encoding Unicode).Trim()
    if ($port -notmatch '^\d+$') {
        throw 'desktop_workspace_port_invalid'
    }
    if (-not (Test-Path -LiteralPath $BaselinePath -PathType Leaf)) {
        throw 'metric_baseline_not_found'
    }

    Add-Type -Path (Join-Path $PowerBIDesktopBin 'Microsoft.PowerBI.AdomdClient.dll')
    $rootConnection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
    $rootConnection.Open()
    $catalogCommand = $rootConnection.CreateCommand()
    $catalogCommand.CommandText = "SELECT * FROM `$SYSTEM.DBSCHEMA_CATALOGS"
    $catalogReader = $catalogCommand.ExecuteReader()
    if (-not $catalogReader.Read()) {
        throw 'desktop_catalog_not_found'
    }
    $catalog = [string]$catalogReader['CATALOG_NAME']
    $catalogReader.Close()
    $rootConnection.Close()
    $rootConnection = $null

    $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port;Initial Catalog=$catalog")
    $connection.Open()

    $metricRow = 'ROW("gross_sales", [Gross Sales], "cancelled_sales", [Cancelled Sales], "net_sales", [Net Sales], "order_count", [Order Count], "units_sold", [Units Sold], "active_customers", [Active Customers], "average_order_value", [Average Order Value], "cancellation_rate", [Cancellation Rate], "sales_mom_pct", [Sales MoM %], "sales_yoy_pct", [Sales YoY %])'
    $queries = [ordered]@{
        all = "EVALUATE $metricRow"
        country = ('EVALUATE CALCULATETABLE(' + $metricRow + ', DimCountry[Country] = "United Kingdom")')
        month = ('EVALUATE CALCULATETABLE(' + $metricRow + ', DimDate[YearMonth] = "2010-11")')
    }
    $baseline = Get-Content -LiteralPath $BaselinePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $results = @()
    $mismatches = @()
    $performanceFailures = @()

    foreach ($sliceId in $queries.Keys) {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        try {
            $actual = Get-DaxRow -Query $queries[$sliceId]
        }
        finally {
            $timer.Stop()
        }
        $durationMilliseconds = [math]::Round($timer.Elapsed.TotalMilliseconds, 2)
        $performancePassed = $durationMilliseconds -le $PerformanceThresholdMilliseconds
        if (-not $performancePassed) {
            $performanceFailures += [ordered]@{
                id = $sliceId
                duration_ms = $durationMilliseconds
                threshold_ms = $PerformanceThresholdMilliseconds
            }
        }
        $expectedSlice = @($baseline.slices | Where-Object { $_.id -eq $sliceId }) | Select-Object -First 1
        if ($null -eq $expectedSlice) {
            throw "metric_baseline_slice_not_found:$sliceId"
        }
        $sliceMismatches = @()
        foreach ($metricName in $expectedSlice.metrics.PSObject.Properties.Name) {
            $expected = $expectedSlice.metrics.$metricName
            $actualValue = $actual[$metricName]
            if (-not (Test-MetricValue -Actual $actualValue -Expected $expected)) {
                $sliceMismatches += [ordered]@{ metric = $metricName; expected = $expected; actual = $actualValue }
            }
        }
        $results += [ordered]@{
            id = $sliceId
            metrics = $actual
            mismatch_count = $sliceMismatches.Count
            duration_ms = $durationMilliseconds
            performance_proxy_passed = $performancePassed
        }
        $mismatches += $sliceMismatches
    }

    $result = [ordered]@{
        baseline = (Split-Path -Leaf $BaselinePath)
        performance_proxy = 'Local Desktop DAX query duration; not Performance Analyzer'
        performance_threshold_ms = $PerformanceThresholdMilliseconds
        slices = $results
        mismatches = $mismatches
        performance_failures = $performanceFailures
    }
    if ($mismatches.Count -gt 0) {
        Write-MetricEvidence -Status 'failed' -Message 'Desktop DAX metrics differ from the approved baseline.' -Result $result
        throw "desktop_metric_validation_failed:$($mismatches.Count)"
    }
    if ($performanceFailures.Count -gt 0) {
        Write-MetricEvidence -Status 'failed' -Message 'Desktop DAX performance proxy exceeded the approved threshold.' -Result $result
        throw "desktop_performance_proxy_failed:$($performanceFailures.Count)"
    }
    Write-MetricEvidence -Status 'passed' -Message 'Desktop DAX metrics match the approved baseline for all, country, and month slices.' -Result $result
    Write-Output 'desktop_metric_validation_passed'
}
catch {
    if (-not (Test-Path -LiteralPath (Join-Path $EvidenceDirectory 'desktop-metric-validation.json'))) {
        Write-MetricEvidence -Status 'failed' -Message $_.Exception.Message
    }
    throw
}
finally {
    if ($connection) { $connection.Close() }
    if ($rootConnection) { $rootConnection.Close() }
}
