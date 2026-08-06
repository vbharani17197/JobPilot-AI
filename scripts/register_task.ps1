# =============================================================
# register_task.ps1
# Registers a Windows Task Scheduler job that runs JobPilot-AI
# every day at 9:00 AM. Run this ONCE from an elevated (Admin)
# PowerShell prompt inside the project folder.
#
# Usage:
#   cd "F:\JobPilot AI"
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# =============================================================

$ErrorActionPreference = "Stop"

# --- Resolve paths -------------------------------------------------
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$RunnerBat   = Join-Path $ProjectRoot "scripts\run_agent.bat"
$TaskName    = "JobPilot-AI Daily 9AM"

if (-not (Test-Path $RunnerBat)) {
    Write-Error "Could not find run_agent.bat at $RunnerBat"
    exit 1
}

Write-Host "Project root : $ProjectRoot"
Write-Host "Runner       : $RunnerBat"
Write-Host "Task name    : $TaskName"

# --- Build the task ------------------------------------------------
$Action  = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c `"$RunnerBat`"" -WorkingDirectory $ProjectRoot

# 9:00 AM daily. Your machine's local time should be IST.
$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Run whether or not the user is logged on would need a password.
# Default here: run only when YOU are logged on (no password needed).
Register-ScheduledTask -TaskName $TaskName -Action $Action `
    -Trigger $Trigger -Settings $Settings `
    -Description "Runs the JobPilot-AI job discovery agent daily at 9 AM." `
    -Force

Write-Host ""
Write-Host "Task registered. It will run daily at 9:00 AM (local/IST time)."
Write-Host "To test immediately:  Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "To remove:            Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
