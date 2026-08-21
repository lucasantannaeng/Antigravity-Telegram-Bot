# Antigravity Telegram Bot - Task Scheduler Registration for 24/7 Persistence
# Registers a scheduled task that runs at logon with highest privileges and auto-restart on failure

$ErrorActionPreference = "Stop"

$TaskName = "AntigravityTelegramBot_24_7"
$BotDir = "D:\Projetos\1.Autorais\Antigravity-Telegram-Bot"
$VbsScript = "$BotDir\run-hidden.vbs"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Antigravity Telegram Bot - 24/7 Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Remove existing task if present
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removendo tarefa existente: $TaskName" -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create action: run the VBS script silently
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsScript`""

# Trigger: At logon
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Settings: Run with highest privileges, restart on failure, don't stop on idle
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -Priority BelowNormal

# Register task (requires admin for RunLevel=Highest)
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User "SYSTEM" `
        -RunLevel Highest `
        -Force
    
    Write-Host "✅ Tarefa '$TaskName' registrada com sucesso!" -ForegroundColor Green
    Write-Host "   - Executa no logon do Windows (SYSTEM)" -ForegroundColor Gray
    Write-Host "   - Prioridade BelowNormal (não impacta boot)" -ForegroundColor Gray
    Write-Host "   - Auto-restart em falha (3 tentativas, 5 min)" -ForegroundColor Gray
    Write-Host "   - Apenas se rede disponível" -ForegroundColor Gray
} catch {
    Write-Host "⚠️ Falha ao registrar como SYSTEM. Tentando como usuário atual..." -ForegroundColor Yellow
    try {
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -User $currentUser `
            -RunLevel Highest `
            -Force
        Write-Host "✅ Tarefa registrada para usuário atual: $currentUser" -ForegroundColor Green
    } catch {
        Write-Host "❌ Erro ao registrar tarefa: $_" -ForegroundColor Red
        Write-Host "Execute este script como Administrador para registrar como SYSTEM." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Verificação:" -ForegroundColor Cyan
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State, Triggers, Settings | Format-List