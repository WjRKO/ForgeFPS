@echo off
REM ============================================================
REM  FrameForge - Firma locale dell'.exe con signtool (Windows)
REM  Usa questo dopo aver ottenuto un certificato (es. Certum Open Source / SimplySign).
REM  signtool fa parte del Windows SDK. Se non ce l'hai:
REM    https://developer.microsoft.com/windows/downloads/windows-sdk/
REM ============================================================

set EXE=dist\forgefps-agent.exe

echo [1/2] Firmo %EXE% ...
REM  Con certificato in Windows Certificate Store (Certum SimplySign monta un virtual token):
signtool sign /fd SHA256 /tr http://time.certum.pl /td SHA256 /a "%EXE%"

REM  --- In alternativa, con un file .pfx: ---
REM  signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f "certificato.pfx" /p LA_TUA_PASSWORD "%EXE%"

echo [2/2] Verifico la firma...
signtool verify /pa /v "%EXE%"

echo.
echo FATTO. Ricalcola lo SHA256 (la firma cambia il file!):
certutil -hashfile "%EXE%" SHA256
pause
