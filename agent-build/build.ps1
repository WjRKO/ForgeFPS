# ============================================================
#  FrameForge - Build dell'agent Windows come .exe standalone
#  Esegui su Windows:  powershell -ExecutionPolicy Bypass -File build.ps1
# ============================================================

Write-Host "[1/3] Installo PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pip pyinstaller

Write-Host "[2/3] Costruisco forgefps-agent.exe..." -ForegroundColor Cyan
pyinstaller --onefile --name forgefps-agent --console forgefps_agent.py

Write-Host "[3/3] Checksum SHA256:" -ForegroundColor Cyan
Get-FileHash .\dist\forgefps-agent.exe -Algorithm SHA256 | Format-List

Write-Host "`nFATTO. Eseguibile: dist\forgefps-agent.exe" -ForegroundColor Green
Write-Host "Avvialo con:  .\forgefps-agent.exe --token IL_TUO_TOKEN" -ForegroundColor Yellow
