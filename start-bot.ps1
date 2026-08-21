# Start Antigravity Telegram Bot
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Iniciando Antigravity Telegram Bot...   " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

python bot.py
