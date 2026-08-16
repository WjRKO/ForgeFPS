# Avvia il dev server del frontend, senza Docker.
#
# Diverso dal servizio "frontend" del compose: li' il bundle veniva compilato
# e servito da nginx sulla 80; qui gira il dev server di craco sulla 3000, con
# hot reload. REACT_APP_BACKEND_URL viene letta da frontend/.env.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\frontend

$nodeDir = "C:\Program Files\nodejs"
$env:PATH = "$nodeDir;$env:PATH"

if (-not (Test-Path "node_modules")) {
    Write-Error "node_modules assente. Eseguire prima: yarn install (oppure npm install)"
}

# Si esegue direttamente il binario LOCALE di craco, non `yarn start`.
# `yarn start` si limita a lanciare `craco start` (vedi package.json), ma yarn
# e' un pacchetto globale di npm e la sua reperibilita' cambia da finestra a
# finestra: l'errore "Termine 'yarn' non riconosciuto" arrivava da li'. Il
# binario dentro node_modules c'e' sempre dopo l'installazione delle
# dipendenze, e non dipende ne' dal PATH ne' dalla policy di esecuzione.
$craco = Join-Path (Get-Location) "node_modules\.bin\craco.cmd"

if (-not (Test-Path $craco)) {
    Write-Error ("craco non trovato in $craco. " +
                 "Le dipendenze sembrano incomplete: rilancia l'installazione.")
}
if (-not (Test-Path "$nodeDir\node.exe")) {
    Write-Error "node.exe non trovato in $nodeDir. Node.js e' installato?"
}

Write-Host "Frontend su http://localhost:3000 (Ctrl+C per fermarlo)" -ForegroundColor Green
& $craco start
