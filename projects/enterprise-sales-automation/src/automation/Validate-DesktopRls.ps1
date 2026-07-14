[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath,

    [Parameter(Mandatory = $true)]
    [string]$PowerBIDesktopBin,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,

    [Parameter(Mandatory = $true)]
    [string]$BaselinePath
)

$ErrorActionPreference = 'Stop'
$startedAt = (Get-Date).ToUniversalTime().ToString('o')
$catalog = ''
$runtimeIdentity = ''
$originalPartitionExpression = ''
$restoreStatus = 'not_started'
$scenarioResults = @()
$connection = $null
$rootConnection = $null
$tabularServer = $null
$temporaryMappingApplied = $false
$validationStatus = 'failed'
$validationMessage = ''
$validationFailure = $null

function Get-IdentityHash {
    param([string]$Identity)

    $bytes = [Text.Encoding]::UTF8.GetBytes($Identity)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
}

function Write-RlsEvidence {
    param(
        [string]$Status,
        [string]$Message
    )

    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
    $json = [ordered]@{
        name = 'Power BI Desktop dynamic RLS validation'
        status = $Status
        started_at = $startedAt
        completed_at = (Get-Date).ToUniversalTime().ToString('o')
        workspace_name = Split-Path -Leaf $WorkspacePath
        catalog = $catalog
        runtime_identity_sha256 = if ($runtimeIdentity) { Get-IdentityHash $runtimeIdentity } else { '' }
        original_partition_restored = $restoreStatus
        message = $Message
        source = 'Desktop local Analysis Services; temporary in-memory security mapping only'
        service_identity_validated = $false
        mysql_credentials_written = $false
        scenarios = $scenarioResults
    } | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText((Join-Path $EvidenceDirectory 'desktop-rls-validation.json'), $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
}

function Get-DaxRow {
    param(
        [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]$DaxConnection,
        [string]$Query
    )

    $command = $DaxConnection.CreateCommand()
    $command.CommandText = $Query
    $reader = $command.ExecuteReader()
    try {
        if (-not $reader.Read()) { throw 'desktop_dax_query_returned_no_rows' }
        $row = [ordered]@{}
        for ($index = 0; $index -lt $reader.FieldCount; $index++) {
            $value = $reader.GetValue($index)
            $row[$reader.GetName($index).Trim([char[]]'[]')] = if ($value -is [System.DBNull]) { $null } else { $value }
        }
        return $row
    }
    finally {
        $reader.Close()
    }
}

function Set-SecurityPartitionExpression {
    param([string]$Expression)

    $database = $tabularServer.Databases[$catalog]
    $table = $database.Model.Tables['SecurityUserCountry']
    $partition = $table.Partitions['SecurityUserCountry']
    $source = [Microsoft.AnalysisServices.Tabular.MPartitionSource]$partition.Source
    if (-not $source) { throw 'security_partition_source_is_not_m' }
    $source.Expression = $Expression
    $table.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    [void]$database.Model.SaveChanges()
}

function New-SecurityMappingExpression {
    param([object[]]$Mappings)

    $rows = foreach ($mapping in $Mappings) {
        $identity = ([string]$mapping.Identity).Replace('"', '""')
        $country = ([string]$mapping.Country).Replace('"', '""')
        '{{"{0}", "{1}", true}}' -f $identity, $country
    }
    '#table(type table [UserPrincipalName = text, Country = text, IsActive = logical], {' + ($rows -join ', ') + '})'
}

function Get-VisibleScope {
    $roleConnection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port;Initial Catalog=$catalog;Roles=CountryManager")
    try {
        $roleConnection.Open()
        return Get-DaxRow $roleConnection @'
EVALUATE
ROW(
    "VisibleCountryCount", COUNTROWS(VALUES('DimCountry'[Country])),
    "VisibleCountries", CONCATENATEX(VALUES('DimCountry'[Country]), 'DimCountry'[Country], "|"),
    "NetSales", [Net Sales]
)
'@
    }
    finally {
        if ($roleConnection) { $roleConnection.Close() }
    }
}

try {
    $portFile = Join-Path $WorkspacePath 'Data\msmdsrv.port.txt'
    if (-not (Test-Path -LiteralPath $portFile -PathType Leaf)) { throw 'desktop_workspace_port_not_found' }
    $port = (Get-Content -LiteralPath $portFile -Raw -Encoding Unicode).Trim()
    if ($port -notmatch '^\d+$') { throw 'desktop_workspace_port_invalid' }

    Add-Type -Path (Join-Path $PowerBIDesktopBin 'Microsoft.PowerBI.AdomdClient.dll')
    Add-Type -Path (Join-Path $PowerBIDesktopBin 'Microsoft.AnalysisServices.Server.Core.dll')
    Add-Type -Path (Join-Path $PowerBIDesktopBin 'Microsoft.AnalysisServices.Server.Tabular.dll')
    $rootConnection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
    $rootConnection.Open()
    $catalogReader = $rootConnection.CreateCommand()
    $catalogReader.CommandText = 'SELECT * FROM $SYSTEM.DBSCHEMA_CATALOGS'
    $catalogResult = $catalogReader.ExecuteReader()
    if (-not $catalogResult.Read()) { throw 'desktop_catalog_not_found' }
    $catalog = [string]$catalogResult['CATALOG_NAME']
    $catalogResult.Close()
    $rootConnection.Close()
    $rootConnection = $null

    $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port;Initial Catalog=$catalog")
    $connection.Open()
    $tabularServer = New-Object Microsoft.AnalysisServices.Tabular.Server
    $tabularServer.Connect("Data Source=localhost:$port")
    $identityRow = Get-DaxRow $connection 'EVALUATE ROW("RuntimeIdentity", USERPRINCIPALNAME())'
    $runtimeIdentity = [string]$identityRow.RuntimeIdentity
    if ([string]::IsNullOrWhiteSpace($runtimeIdentity)) { throw 'desktop_runtime_identity_empty' }

    $partitionCommand = $connection.CreateCommand()
    $partitionCommand.CommandText = "SELECT [QueryDefinition] FROM `$SYSTEM.TMSCHEMA_PARTITIONS WHERE [Name] = 'SecurityUserCountry'"
    $partitionReader = $partitionCommand.ExecuteReader()
    if (-not $partitionReader.Read()) { throw 'security_partition_not_found' }
    $originalPartitionExpression = [string]$partitionReader['QueryDefinition']
    $partitionReader.Close()
    if ([string]::IsNullOrWhiteSpace($originalPartitionExpression)) { throw 'security_partition_expression_empty' }

    $baseline = Get-Content -LiteralPath $BaselinePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $countryBaselines = @{}
    foreach ($countryBaseline in $baseline.countries) {
        $countryBaselines[[string]$countryBaseline.country] = [decimal]$countryBaseline.metrics.net_sales
    }
    if (-not $countryBaselines.ContainsKey('United Kingdom') -or -not $countryBaselines.ContainsKey('France')) { throw 'approved_rls_country_baselines_not_found' }

    $scenarios = @(
        @{ id = 'uk'; country = 'United Kingdom'; mappings = @(@{ Identity = $runtimeIdentity; Country = 'United Kingdom' }); comparison = 'approved_duckdb_baseline' },
        @{ id = 'france'; country = 'France'; mappings = @(@{ Identity = $runtimeIdentity; Country = 'France' }); comparison = 'approved_duckdb_baseline' },
        @{ id = 'unmapped'; country = ''; mappings = @(); comparison = 'deny_by_default' }
    )

    foreach ($scenario in $scenarios) {
        Set-SecurityPartitionExpression (New-SecurityMappingExpression $scenario.mappings)
        $temporaryMappingApplied = $true
        $visible = Get-VisibleScope
        $expectedNetSales = if ($scenario.country) { $countryBaselines[$scenario.country] } else { $null }
        $actualNetSales = if ($null -eq $visible.NetSales) { $null } else { [decimal]$visible.NetSales }
        $isVisibleCountryCorrect = if ($scenario.country) { $visible.VisibleCountryCount -eq 1 -and $visible.VisibleCountries -eq $scenario.country } else { ($visible.VisibleCountryCount -eq 0 -or $null -eq $visible.VisibleCountryCount) -and [string]::IsNullOrWhiteSpace([string]$visible.VisibleCountries) }
        $isNetSalesCorrect = if ($null -eq $expectedNetSales) { $null -eq $actualNetSales } else { [math]::Abs($actualNetSales - $expectedNetSales) -lt 0.01 }
        $scenarioResults += [ordered]@{
            id = $scenario.id
            expected_country = $scenario.country
            visible_country_count = $visible.VisibleCountryCount
            visible_countries = $visible.VisibleCountries
            expected_net_sales = $expectedNetSales
            actual_net_sales = $actualNetSales
            comparison = $scenario.comparison
            passed = $isVisibleCountryCorrect -and $isNetSalesCorrect
        }
    }

    if (@($scenarioResults | Where-Object { -not $_.passed }).Count -gt 0) { throw 'desktop_rls_scenario_failed' }
    $validationStatus = 'passed'
    $validationMessage = 'UK, France, and unmapped local Desktop RLS scenarios passed against the approved DuckDB country baseline; Service identity is not validated.'
}
catch {
    $validationFailure = $_
    $validationStatus = 'failed'
    $validationMessage = $_.Exception.Message
}
finally {
    if ($connection -and $originalPartitionExpression -and $temporaryMappingApplied) {
        try {
            Set-SecurityPartitionExpression $originalPartitionExpression
            $restoreStatus = 'passed'
        }
        catch {
            $restoreStatus = 'failed'
            $validationStatus = 'failed'
            $validationMessage = "security_partition_restore_failed=$($_.Exception.Message)"
        }
    }
    Write-RlsEvidence -Status $validationStatus -Message $validationMessage
    if ($connection) { $connection.Close() }
    if ($rootConnection) { $rootConnection.Close() }
    if ($tabularServer) { $tabularServer.Disconnect() }
}

if ($validationFailure) { throw $validationFailure }
if ($validationStatus -ne 'passed') { throw $validationMessage }
Write-Output 'desktop_rls_validation_passed'
