$scriptPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\Invoke-BIWorkflow.ps1'
$tokens = $null
$parseErrors = $null
$scriptAst = [System.Management.Automation.Language.Parser]::ParseFile(
    $scriptPath,
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {
    throw ($parseErrors | ForEach-Object { $_.Message } | Out-String)
}

function Import-WorkflowFunction {
    param([Parameter(Mandatory = $true)][string]$Name)

    $functionAst = $scriptAst.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $Name
    }, $true) | Select-Object -First 1
    if ($null -eq $functionAst) {
        throw "Workflow function not found: $Name"
    }
    Invoke-Expression ("function global:$Name " + $functionAst.Body.Extent.Text)
}

Import-WorkflowFunction -Name 'Get-DesktopBridgeStatus'
Import-WorkflowFunction -Name 'Get-AllDesktopBridgeInstances'
Import-WorkflowFunction -Name 'Wait-DesktopTargetInstance'

Describe 'Power BI Desktop session discovery' {
    It 'fails closed when all running Desktop bridge queries fail' {
        Mock Get-Process { @([pscustomobject]@{ Id = 10 }, [pscustomobject]@{ Id = 20 }) }
        Mock Get-DesktopBridgeStatus { $null }

        $result = Get-AllDesktopBridgeInstances -BridgePath 'bridge.exe'

        $result | Should BeNullOrEmpty
    }

    It 'fails closed when only a subset of running Desktop bridge queries succeeds' {
        Mock Get-Process { @([pscustomobject]@{ Id = 10 }, [pscustomobject]@{ Id = 20 }) }
        Mock Get-DesktopBridgeStatus {
            if ($ProcessId -eq 10) {
                return [pscustomobject]@{ instances = @([pscustomobject]@{ pid = 10 }) }
            }
            return $null
        }

        $result = Get-AllDesktopBridgeInstances -BridgePath 'bridge.exe'

        $result | Should BeNullOrEmpty
    }

    It 'returns a ready empty set when no Desktop process is running' {
        Mock Get-Process { @() }
        Mock Get-DesktopBridgeStatus { throw 'must not be called' }

        $result = Get-AllDesktopBridgeInstances -BridgePath 'bridge.exe'

        $result.status | Should Be 'ready'
        @($result.instances).Count | Should Be 0
        Assert-MockCalled Get-DesktopBridgeStatus -Times 0 -Scope It
    }

    It 'probes newly appeared Desktop processes before existing processes' {
        $script:observedProcessIds = New-Object System.Collections.Generic.List[int]
        function Get-Process {
            return @(
                [pscustomobject]@{ Id = 10 },
                [pscustomobject]@{ Id = 20 }
            )
        }
        function Get-DesktopBridgeStatus {
            param($BridgePath, $WaitSeconds, $ProcessId)
            $script:observedProcessIds.Add([int]$ProcessId)
            if ($ProcessId -eq 20) {
                return [pscustomobject]@{
                    instances = @([pscustomobject]@{
                        pid = 20
                        bridgeStatus = 'connected'
                        currentFilePath = 'C:\target.pbip'
                    })
                }
            }
            return [pscustomobject]@{ instances = @() }
        }
        function Get-DesktopTargetInstance {
            param($Status, $TargetFile)
            return @($Status.instances | Where-Object { $_.currentFilePath -eq $TargetFile }) | Select-Object -First 1
        }
        function Start-Sleep { }

        $result = Wait-DesktopTargetInstance -BridgePath 'bridge.exe' -TargetFile 'C:\target.pbip' -ExistingProcessIds @(10) -TimeoutSeconds 1

        $result.pid | Should Be 20
        $script:observedProcessIds[0] | Should Be 20
    }
}
