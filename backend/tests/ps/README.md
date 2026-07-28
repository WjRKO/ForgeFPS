# Test PowerShell dell'agent (ps_agent.py)
Setup pwsh (container aarch64):
  cd /tmp && curl -sL -o p.tgz https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell-7.4.6-linux-arm64.tar.gz && mkdir -p pwsh7a && tar xzf p.tgz -C pwsh7a && chmod +x pwsh7a/pwsh

1) Sintassi intero script:
  cd /app/backend && python3 -c "import ps_agent; open('/tmp/full_script.ps1','w').write(ps_agent.PS_SCRIPT)"
  /tmp/pwsh7a/pwsh -NoProfile -Command '[System.Management.Automation.Language.Parser]::ParseFile("/tmp/full_script.ps1",[ref]$null,[ref]$e)|Out-Null; if($e.Count -eq 0){"PS SYNTAX OK"}else{$e|%{"ERR $($_.Extent.StartLineNumber): $($_.Message)"}}'

2) Runtime Get-Fps (estrarre la funzione con lo snippet python in test_getfps note, poi):
  /tmp/pwsh7a/pwsh -NoProfile -File /app/backend/tests/ps/test_getfps.ps1
  (richiede /tmp/getfps.ps1 estratto: python3 - vedi PRD entry 65)
