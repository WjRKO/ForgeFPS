
build.bat
@echo off
REM ============================================================
REM  FrameForge - Build dell'agent Windows come .exe standalone
REM  Esegui questo file su un PC Windows con Python 3.10+ installato.
REM  I flag qui sotto (metadati versione + no UPX) riducono molto
REM  i FALSI POSITIVI degli antivirus sugli eseguibili PyInstaller.
REM ============================================================

echo [1/4] Installo PyInstaller...
python -m pip install --upgrade pip pyinstaller

echo [2/4] Pulisco build precedenti...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Costruisco forgefps-agent.exe (con metadati, senza UPX)...
pyinstaller --onefile --name forgefps-agent --console --noupx --clean ^
  --version-file version_info.txt forgefps_agent.py

echo [4/4] Calcolo il checksum SHA256...
certutil -hashfile dist\forgefps-agent.exe SHA256

echo.
echo FATTO. L'eseguibile si trova in:  dist\forgefps-agent.exe
echo Avvialo con:  forgefps-agent.exe --token IL_TUO_TOKEN
echo.
echo Se un antivirus lo segnala (falso positivo tipico di PyInstaller):
echo   1) Firma l'exe con un certificato Authenticode (soluzione definitiva)
echo   2) Segnala il falso positivo a Microsoft: https://www.microsoft.com/wdsi/filesubmission
echo   3) Controlla su https://www.virustotal.com per vedere quali motori lo flaggano
pause
