# Avvia il bot Discord di FrameForge.
#
# E' un processo SEPARATO da backend e frontend: `discord_bot.py` apre una
# connessione gateway propria e non viene lanciato da server.py. Mancava lo
# script, quindi in locale il bot non partiva mai.
#
# Legge la configurazione da backend/.env come il resto del backend.
# Esce subito se DISCORD_BOT_TOKEN o DISCORD_GUILD_ID non sono impostati.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\backend

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "venv assente. Ricrearlo con: py -3.11 -m venv .venv"
}

$mongo = Get-Service MongoDB -ErrorAction SilentlyContinue
if ($mongo -and $mongo.Status -ne "Running") {
    Write-Host "Avvio del servizio MongoDB..." -ForegroundColor Yellow
    Start-Service MongoDB
}

Write-Host "Bot Discord in avvio (Ctrl+C per fermarlo)" -ForegroundColor Green
& .venv\Scripts\python.exe discord_bot.py
