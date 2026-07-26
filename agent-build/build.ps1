# ============================================================
#  FrameForge - Build dell'agent Windows come cartella + ZIP
#  Esegui su Windows:  powershell -ExecutionPolicy Bypass -File build.ps1
#
#  Da v0.6.7 usiamo --onedir invece di --onefile: PyInstaller
#  onefile e' un archivio auto-estraente e Windows Defender lo
#  classifica euristicamente come "dropper". La build --onedir
#  produce una cartella con .exe + DLL affiancate, che passa
#  senza falsi positivi anche senza firma Authenticode.
# ============================================================

Write-Host "[1/5] Installo PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pip pyinstaller

Write-Host "[2/5] Pulisco build precedenti..." -ForegroundColor Cyan
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }

Write-Host "[3/5] Costruisco la cartella dist\forgefps-agent\ (onedir, metadati, no UPX, manifest esplicito asInvoker)..." -ForegroundColor Cyan
# v0.7.8: manifest ESPLICITO forgefps-agent.manifest con asInvoker.
# Sostituisce il default PyInstaller (che in alcune versioni puo' includere
# comunque requireAdministrator anche senza --uac-admin).
# La build FALLISCE al passo [4/5] se il manifest embedded ha requireAdministrator.
pyinstaller --onedir --name forgefps-agent --console --noupx --clean `
  --manifest forgefps-agent.manifest `
  --version-file version_info.txt forgefps_agent.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "[3.5/5] Verifica manifest embedded (safety check)..." -ForegroundColor Cyan
$exeBytes = [System.IO.File]::ReadAllBytes("dist\forgefps-agent\forgefps-agent.exe")
$exeText = [System.Text.Encoding]::ASCII.GetString($exeBytes)
if ($exeText -match "requireAdministrator") {
  Write-Host "[FAIL] L'exe contiene ancora 'requireAdministrator' - build ANNULLATA" -ForegroundColor Red
  exit 1
}
if ($exeText -notmatch "asInvoker") {
  Write-Host "[FAIL] Manifest asInvoker NON trovato nell'exe - build ANNULLATA" -ForegroundColor Red
  exit 1
}
Write-Host "[OK] Manifest verificato: asInvoker presente, nessun requireAdministrator" -ForegroundColor Green

Write-Host "[4/5] Comprimo dist\forgefps-agent\ in forgefps-agent.zip..." -ForegroundColor Cyan
Compress-Archive -Path 'dist\forgefps-agent' -DestinationPath 'dist\forgefps-agent.zip' -Force

Write-Host "[5/5] Checksum SHA256 del ZIP:" -ForegroundColor Cyan
Get-FileHash .\dist\forgefps-agent.zip -Algorithm SHA256 | Format-List

Write-Host "`nFATTO. Distribuisci: dist\forgefps-agent.zip" -ForegroundColor Green
Write-Host "Uso finale: unzip -> apri la cartella -> forgefps-agent.exe --token IL_TUO_TOKEN" -ForegroundColor Yellow

Write-Host "`nSe un antivirus lo segnala ancora (raro con --onedir):" -ForegroundColor DarkYellow
Write-Host "  1) Segnala il falso positivo a Microsoft: https://www.microsoft.com/wdsi/filesubmission"
Write-Host "  2) Vedi VENDOR_FALSE_POSITIVE.md per i testi pronti da inviare a Kaspersky, Bitdefender, Norton, ESET"
Write-Host "  3) Verifica su https://www.virustotal.com quali motori lo flaggano"
