# Registra a inicialização automática do Antigravity Telegram Bot na pasta Startup do usuário
$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$BotDir = "D:\Projetos\1.Autorais\Antigravity-Telegram-Bot"
$VbsPath = Join-Path $StartupFolder "Antigravity_Telegram_Bot.vbs"
$BatPath = Join-Path $BotDir "run-hidden.vbs"

Write-Host "Configurando inicialização automática no Windows..." -ForegroundColor Cyan

# Conteudo do script VBS para rodar em background sem janela preta
$VbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$BotDir"
WshShell.Run "python.exe `"$BotDir\bot.py`"", 0, False
"@

Set-Content -Path $VbsPath -Value $VbsContent -Encoding UTF8
Set-Content -Path $BatPath -Value $VbsContent -Encoding UTF8

Write-Host "Inicialização automática configurada com sucesso em:" -ForegroundColor Green
Write-Host "  $VbsPath" -ForegroundColor Gray
Write-Host "O bot iniciará automaticamente sempre que você fizer login no Windows." -ForegroundColor Yellow
