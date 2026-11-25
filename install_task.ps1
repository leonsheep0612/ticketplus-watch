# 建立 Windows 工作排程：每 5 分鐘執行一次釋票通知（只在登入時執行，不需要系統管理員權限）
# 用法：在這個資料夾開 PowerShell 執行 .\install_task.ps1；移除：.\install_task.ps1 -Uninstall
param([switch]$Uninstall)

$TaskName = "TicketPlusWatch"
if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "已移除工作排程 $TaskName"
    return
}

$root = $PSScriptRoot
if (-not (Test-Path "$root\.env")) {
    Write-Host "找不到 .env：請把 .env.example 複製成 .env，填好 Telegram 金鑰再執行" -ForegroundColor Red
    return
}
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1).Source
if (-not $pythonw) {
    Write-Host "找不到 pythonw.exe，請先安裝 Python（安裝時勾選 Add to PATH）" -ForegroundColor Red
    return
}

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$root\run_local.pyw`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
# 錯過的排程（電腦睡眠中）醒來後補跑一次；同一時間只跑一個
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Ticket Plus 釋票通知（$root）" -Force | Out-Null
Write-Host "已建立工作排程 $TaskName，每 5 分鐘執行一次；紀錄在 $root\logs\watch.log"
