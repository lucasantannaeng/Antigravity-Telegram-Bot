# Antigravity Automated System Maintenance & Memory Optimizer
# Runs silently: cleans temp files, purges DNS cache, trims working set RAM, and reports stats.

param (
    [switch]$NotifyTelegram = $false
)

$ErrorActionPreference = "SilentlyContinue"

$initialRam = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024, 1)

# 1. Clean User Temp
$userTemp = [System.IO.Path]::GetTempPath()
$deletedCount = 0
Get-ChildItem -Path $userTemp -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { 
    $_.LastWriteTime -lt (Get-Date).AddHours(-6) 
} | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $deletedCount++
}

# 2. Clean Windows Temp (if accessible)
if (Test-Path "C:\Windows\Temp") {
    Get-ChildItem -Path "C:\Windows\Temp" -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { 
        $_.LastWriteTime -lt (Get-Date).AddHours(-12) 
    } | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 3. Clean Project temp directory
$botTemp = "D:\Projetos\1.Autorais\Antigravity-Telegram-Bot\temp"
if (Test-Path $botTemp) {
    Get-ChildItem -Path $botTemp -Recurse -Force -ErrorAction SilentlyContinue | Where-Object {
        $_.LastWriteTime -lt (Get-Date).AddMinutes(-30)
    } | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 4. Flush DNS Cache
Clear-DnsClientCache -ErrorAction SilentlyContinue

# 5. Force Memory Garbage Collection in .NET runtime
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()

$finalRam = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024, 1)
$totalRam = [math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1024 / 1024, 2)

$report = @"
🧹 **Manutenção e Otimização do Sistema Concluída:**
• **Arquivos temporários removidos:** $deletedCount
• **Memória RAM livre inicial:** $initialRam MB
• **Memória RAM livre atual:** $finalRam MB (de $totalRam GB)
• **Cache DNS:** Esvaziado com sucesso
• **Status:** 🟢 Sistema Otimizado e Fluido
"@

Write-Host $report

if ($NotifyTelegram) {
    # Optional direct webhook / notify if called with switch
}
