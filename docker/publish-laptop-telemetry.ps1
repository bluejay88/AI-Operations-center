param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32"
)

$ErrorActionPreference = "Continue"

function Get-BatteryPercent {
    try {
        $battery = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($battery -and $null -ne $battery.EstimatedChargeRemaining) {
            return [double]$battery.EstimatedChargeRemaining
        }
    } catch {}
    return $null
}

function Get-FreeDiskMb {
    try {
        $drive = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue
        if ($drive -and $drive.FreeSpace) {
            return [math]::Round($drive.FreeSpace / 1MB, 2)
        }
    } catch {}
    return $null
}

function Get-RamMb {
    try {
        $computer = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction SilentlyContinue
        if ($computer -and $computer.TotalPhysicalMemory) {
            return [math]::Round($computer.TotalPhysicalMemory / 1MB, 2)
        }
    } catch {}
    return $null
}

$batteryPercent = Get-BatteryPercent
$healthScore = 90
if ($null -ne $batteryPercent -and $batteryPercent -le 5) {
    $healthScore = 25
} elseif ($null -ne $batteryPercent -and $batteryPercent -le 15) {
    $healthScore = 55
}

$payload = @{
    machine_id = $MachineId
    device_name = $env:COMPUTERNAME
    hostname = $env:COMPUTERNAME
    operating_system = (Get-CimInstance Win32_OperatingSystem).Caption
    ram_mb = Get-RamMb
    storage_free_mb = Get-FreeDiskMb
    battery_percent = $batteryPercent
    current_user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    network_status = "online"
    tailscale_status = "online"
    current_tasks = @()
    health_score = $healthScore
    metadata = @{
        telemetry_source = "publish-laptop-telemetry.ps1"
        battery_policy = "failover_at_5_percent"
        git_savepoint_required_at_percent = 5
    }
} | ConvertTo-Json -Depth 5

try {
    $result = Invoke-RestMethod -Uri "http://$BrainHost`:8088/ops2/device-telemetry" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 15
    Write-Host "Telemetry published for $MachineId"
    if ($result.failover) {
        Write-Host "Failover response:"
        $result.failover | ConvertTo-Json -Depth 6
    }
} catch {
    Write-Host "Telemetry publish failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
        Write-Host $_.ErrorDetails.Message
    }
}

if ($null -ne $batteryPercent -and $batteryPercent -le 5) {
    Write-Host "CRITICAL BATTERY: Create a safe git savepoint now." -ForegroundColor Red
    git status
    Write-Host "If there are safe local changes, run: git add . ; git commit -m `"Battery failover savepoint from $MachineId`" ; git push origin master"
}
