# Ferma backend (8001) e frontend (3000).
#
# MongoDB NON viene toccato: e' un servizio Windows ad avvio automatico e serve
# anche ad altro. Per fermarlo comunque: Stop-Service MongoDB (da amministratore).

$ErrorActionPreference = "Continue"

function Test-Alive($url) {
    try { Invoke-WebRequest $url -TimeoutSec 3 -UseBasicParsing | Out-Null; return $true }
    catch { return $false }
}

# 1) Chi e' in ascolto sulle due porte.
foreach ($port in 8001, 3000) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "porta $port : nessun listener" -ForegroundColor DarkGray; continue }
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "porta $port : fermato $($proc.ProcessName) (PID $($c.OwningProcess))" -ForegroundColor Yellow
        } else {
            Write-Host "porta $port : voce TCP stantia (PID $($c.OwningProcess) non esiste piu')" -ForegroundColor DarkGray
        }
    }
}

Start-Sleep -Seconds 2

# 2) uvicorn --reload lascia un figlio che sopravvive alla morte del padre e
#    continua a servire la porta. Non ha "ForgeFPS" nella riga di comando (e'
#    un multiprocessing.spawn), quindi va cercato cosi'. Si interviene solo se
#    il backend risponde ancora davvero: e' l'unica prova affidabile, la
#    tabella TCP puo' mostrare un proprietario che non esiste piu'.
if (Test-Alive "http://127.0.0.1:8001/health") {
    Write-Host "backend ancora vivo: cerco il worker di uvicorn..." -ForegroundColor Yellow
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*multiprocessing.spawn*" } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "  fermato worker PID $($_.ProcessId)" -ForegroundColor Yellow
        }
    Start-Sleep -Seconds 2
}

# 3) Verdetto basato su cosa risponde, non su cosa dice la tabella TCP.
$beUp = Test-Alive "http://127.0.0.1:8001/health"
$feUp = Test-Alive "http://localhost:3000"
if ($beUp) { Write-Host "backend  : ANCORA ATTIVO" -ForegroundColor Red }
else       { Write-Host "backend  : fermo" -ForegroundColor Green }
if ($feUp) { Write-Host "frontend : ANCORA ATTIVO" -ForegroundColor Red }
else       { Write-Host "frontend : fermo" -ForegroundColor Green }
