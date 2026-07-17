# ============================================================
#  FrameForge - Build dell'agent Windows come .exe standalone
#  Esegui su Windows:  powershell -ExecutionPolicy Bypass -File build.ps1
#  I flag (metadati versione + no UPX) riducono molto i FALSI POSITIVI
#  degli antivirus sugli eseguibili PyInstaller.
# ============================================================

Write-Host "[1/4] Installo PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pip pyinstaller

Write-Host "[2/4] Pulisco build precedenti..." -ForegroundColor Cyan
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }

Write-Host "[3/4] Costruisco forgefps-agent.exe (con metadati, senza UPX)..." -ForegroundColor Cyan
pyinstaller --onefile --name forgefps-agent --console --noupx --clean `
  --version-file version_info.txt forgefps_agent.py

Write-Host "[4/4] Checksum SHA256:" -ForegroundColor Cyan
Get-FileHash .\dist\forgefps-agent.exe -Algorithm SHA256 | Format-List

Write-Host "`nFATTO. Eseguibile: dist\forgefps-agent.exe" -ForegroundColor Green
Write-Host "Avvialo con:  .\forgefps-agent.exe --token IL_TUO_TOKEN" -ForegroundColor Yellow
Write-Host "`nSe un antivirus lo segnala (falso positivo tipico di PyInstaller):" -ForegroundColor DarkYellow
Write-Host "  1) Firma l'exe con un certificato Authenticode (soluzione definitiva)"
Write-Host "  2) Segnala il falso positivo: https://www.microsoft.com/wdsi/filesubmission"
Write-Host "  3) Verifica su https://www.virustotal.com quali motori lo flaggano"
