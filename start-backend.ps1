# Avvia il backend FastAPI in locale, senza Docker.
#
# Equivale al servizio "backend" di docker-compose.yml, con due differenze:
#   - MongoDB e' il servizio Windows su localhost:27017, non il container mongo:7
#   - --reload attivo: il codice viene ricaricato a ogni salvataggio
#
# Una sola istanza, niente --workers: APScheduler vive nel processo e non ha
# lock distribuito (stessa ragione documentata nel Dockerfile).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\backend

if (-not (Test-Path ".venv\Scripts\uvicorn.exe")) {
    Write-Error "venv assente. Ricrearlo con: py -3.11 -m venv .venv"
}

$mongo = Get-Service MongoDB -ErrorAction SilentlyContinue
if ($mongo -and $mongo.Status -ne "Running") {
    Write-Host "Avvio del servizio MongoDB..." -ForegroundColor Yellow
    Start-Service MongoDB
}

Write-Host "Backend su http://localhost:8001 (Ctrl+C per fermarlo)" -ForegroundColor Green
& .venv\Scripts\uvicorn.exe server:app --host 127.0.0.1 --port 8001 --reload
