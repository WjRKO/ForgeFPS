@echo off
REM ============================================================
REM  FrameForge - Build dell'agent Windows come cartella + ZIP
REM  Esegui questo file su un PC Windows con Python 3.10+ installato.
REM
REM  Da v0.6.7 usiamo --onedir invece di --onefile: PyInstaller
REM  onefile e' un archivio auto-estraente e Windows Defender lo
REM  classifica euristicamente come "dropper". La build --onedir
REM  produce una cartella con .exe + DLL affiancate, che passa
REM  senza falsi positivi anche senza firma Authenticode.
REM ============================================================

echo [1/5] Installo PyInstaller...
python -m pip install --upgrade pip pyinstaller

echo [2/5] Pulisco build precedenti...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/5] Costruisco la cartella dist\forgefps-agent\ (onedir, metadati, no UPX, UAC admin)...
pyinstaller --onedir --name forgefps-agent --console --noupx --clean ^
  --uac-admin ^
  --version-file version_info.txt forgefps_agent.py

echo [4/5] Comprimo dist\forgefps-agent\ in forgefps-agent.zip...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\forgefps-agent' -DestinationPath 'dist\forgefps-agent.zip' -Force"

echo [5/5] Checksum SHA256 del ZIP:
certutil -hashfile dist\forgefps-agent.zip SHA256

echo.
echo FATTO. Distribuisci:  dist\forgefps-agent.zip
echo Uso finale: unzip -> apri la cartella -> forgefps-agent.exe --token IL_TUO_TOKEN
echo.
echo Se un antivirus lo segnala ancora (raro con --onedir):
echo   1) Segnala il falso positivo a Microsoft: https://www.microsoft.com/wdsi/filesubmission
echo   2) Vedi VENDOR_FALSE_POSITIVE.md per i testi pronti da inviare a Kaspersky, Bitdefender, Norton, ESET
echo   3) Verifica su https://www.virustotal.com quali motori lo flaggano
pause
