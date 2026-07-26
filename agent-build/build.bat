@echo off
REM v0.6.7: --onedir per eliminare i falsi positivi Windows Defender
echo [1/5] Installo PyInstaller...
python -m pip install --upgrade pip pyinstaller
echo [2/5] Pulisco build precedenti...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
 main-v.0.7.7

echo [3/5] Costruisco la cartella dist\forgefps-agent\ (onedir, metadati, no UPX, asInvoker manifest)...
REM v0.7.7: rimosso --uac-admin. L'exe gira in user-space (no UAC all'avvio).
REM Mode 'optimize' self-eleva on-demand (vedi forgefps_agent.py:1127).

echo [3/5] Costruisco la cartella dist\forgefps-agent\ (onedir, metadati, no UPX, UAC admin)...
main
pyinstaller --onedir --name forgefps-agent --console --noupx --clean ^
  --version-file version_info.txt forgefps_agent.py
echo [4/5] Comprimo dist\forgefps-agent\ in forgefps-agent.zip...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\forgefps-agent' -DestinationPath 'dist\forgefps-agent.zip' -Force"
echo [5/5] SHA256 del ZIP:
certutil -hashfile dist\forgefps-agent.zip SHA256
echo.
echo FATTO. Distribuisci: dist\forgefps-agent.zip
echo Uso: estrai lo ZIP, apri la cartella, forgefps-agent.exe --token IL_TUO_TOKEN