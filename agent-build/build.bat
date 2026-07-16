@echo off
REM ============================================================
REM  FrameForge - Build dell'agent Windows come .exe standalone
REM  Esegui questo file su un PC Windows con Python 3.10+ installato.
REM ============================================================

echo [1/3] Installo PyInstaller...
python -m pip install --upgrade pip pyinstaller

echo [2/3] Costruisco forgefps-agent.exe...
pyinstaller --onefile --name forgefps-agent --console forgefps_agent.py

echo [3/3] Calcolo il checksum SHA256...
certutil -hashfile dist\forgefps-agent.exe SHA256

echo.
echo FATTO. L'eseguibile si trova in:  dist\forgefps-agent.exe
echo Avvialo con:  forgefps-agent.exe --token IL_TUO_TOKEN
pause
