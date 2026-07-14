[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath,

    [Parameter(Mandatory = $true)]
    [string]$PowerBIDesktopBin,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,

    [int]$RefreshThresholdSeconds = 300
)

$ErrorActionPreference = 'Stop'
$startedAt = (Get-Date).ToUniversalTime().ToString('o')
$connection = $null
$rootConnection = $null
$refreshTimer = $null
$refreshCompleted = $false

function Write-RefreshEvidence {
    param(
        [string]$Status,
        [string]$Message,
        [string]$Catalog = '',
        [object]$PerformanceGatePassed = $null
    )

    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
    $durationMilliseconds = if ($refreshTimer) { [math]::Round($refreshTimer.Elapsed.TotalMilliseconds, 2) } else { 0 }
    [ordered]@{
        name = 'Power BI Desktop local model refresh'
        status = $Status
        started_at = $startedAt
        completed_at = (Get-Date).ToUniversalTime().ToString('o')
        workspace_name = Split-Path -Leaf $WorkspacePath
        catalog = $Catalog
        duration_ms = $durationMilliseconds
        refresh_threshold_seconds = $RefreshThresholdSeconds
        performance_gate_passed = $PerformanceGatePassed
        message = $Message
        source = 'Desktop local Analysis Services via TMSL refresh'
        mysql_credentials_written = $false
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'desktop-model-refresh.json') -Encoding UTF8
}

try {
    $portFile = Join-Path $WorkspacePath 'Data\msmdsrv.port.txt'
    if (-not (Test-Path -LiteralPath $portFile -PathType Leaf)) {
        throw "desktop_workspace_port_not_found"
    }
    $port = (Get-Content -LiteralPath $portFile -Raw -Encoding Unicode).Trim()
    if ($port -notmatch '^\d+$') {
        throw "desktop_workspace_port_invalid"
    }

    Add-Type -Path (Join-Path $PowerBIDesktopBin 'Microsoft.PowerBI.AdomdClient.dll')
    $rootConnection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
    $rootConnection.Open()
    $catalogCommand = $rootConnection.CreateCommand()
    $catalogCommand.CommandText = "SELECT * FROM `$SYSTEM.DBSCHEMA_CATALOGS"
    $catalogReader = $catalogCommand.ExecuteReader()
    if (-not $catalogReader.Read()) {
        throw "desktop_catalog_not_found"
    }
    $catalog = [string]$catalogReader['CATALOG_NAME']
    $catalogReader.Close()
    $rootConnection.Close()
    $rootConnection = $null

    $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port;Initial Catalog=$catalog")
    $connection.Open()
    $refreshCommand = $connection.CreateCommand()
    $refreshCommand.CommandText = '{"refresh":{"type":"full","objects":[{"database":"' + $catalog + '"}]}}'
    $refreshTimer = [System.Diagnostics.Stopwatch]::StartNew()
    [void]$refreshCommand.ExecuteNonQuery()
    $refreshTimer.Stop()
    $refreshCompleted = $true
    if ($refreshTimer.Elapsed.TotalSeconds -gt $RefreshThresholdSeconds) {
        throw "desktop_refresh_performance_gate_failed:$([math]::Round($refreshTimer.Elapsed.TotalSeconds, 2))s"
    }
    Write-RefreshEvidence -Status 'passed' -Message 'Desktop local model refresh completed within the approved threshold.' -Catalog $catalog -PerformanceGatePassed $true
    Write-Output 'desktop_model_refresh_completed'
}
catch {
    if ($refreshTimer -and $refreshTimer.IsRunning) { $refreshTimer.Stop() }
    $catalogValue = if ($catalog) { [string]$catalog } else { '' }
    $performanceGatePassed = if (-not $refreshCompleted) { $null } else { $refreshTimer.Elapsed.TotalSeconds -le $RefreshThresholdSeconds }
    Write-RefreshEvidence -Status 'failed' -Message $_.Exception.Message -Catalog $catalogValue -PerformanceGatePassed $performanceGatePassed
    throw
}
finally {
    if ($connection) { $connection.Close() }
    if ($rootConnection) { $rootConnection.Close() }
}
