# Le azioni di avvio decise dalla dashboard, eseguite davvero in PowerShell.
#
# Gli altri test su questa funzione leggono il testo dello script. Qui invece le
# funzioni vere vengono estratte dallo script dell'agent e CHIAMATE, con i soli
# collaboratori esterni sostituiti: la rete, la scrittura nel registro, il
# prompt di Windows. Serve per la sola domanda a cui il testo non risponde:
# quando in coda ci sono sia voci dell'utente sia voci di sistema, chi finisce
# dove, e chi viene applicato lo stesso se l'elevazione non arriva.
#
# Non chiede nessun permesso e non tocca il registro: Set-StartupEntry e
# Start-StartupElevato sono finti e registrano solo di essere stati chiamati.
#
# Uso:
#   cd backend
#   ./.venv/Scripts/python.exe -c "import ps_agent; open('agent.ps1','w',encoding='utf-8').write(ps_agent.PS_SCRIPT)"
#   powershell -NoProfile -File tests/ps/test_azioni_avvio.ps1 -Script agent.ps1
Param([string]$Script = '')

$ErrorActionPreference = 'Stop'
if (-not $Script) { $Script = Join-Path $env:TEMP 'ff_agent_full.ps1' }
if (-not (Test-Path $Script)) { Write-Host "script assente: $Script" -ForegroundColor Red; exit 2 }

# --- estrazione: le funzioni vere, prese dall'AST cosi' come sono scritte ---
$err = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Script, [ref]$null, [ref]$err)
if ($err) { $err | ForEach-Object { Write-Host $_ -ForegroundColor Red }; exit 2 }
$volute = @('Get-StartupActionEntry', 'Invoke-StartupBatch', 'Invoke-StartupActions',
            'Test-StartupServeAdmin', 'Test-StartupIntoccabile')
$defs = $ast.FindAll({
    param($n)
    $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $volute -contains $n.Name
  }, $true)
if ($defs.Count -ne $volute.Count) {
  Write-Host ("estratte {0} funzioni su {1}: lo script e' cambiato" -f $defs.Count, $volute.Count) -ForegroundColor Red
  exit 2
}
$raw = Get-Content $Script -Raw
$intoccabili = [regex]::Match($raw, '(?m)^\$script:STARTUP_INTOCCABILI = .*$').Value
if (-not $intoccabili) { Write-Host 'STARTUP_INTOCCABILI non trovata' -ForegroundColor Red; exit 2 }

# --- i finti: tutto quello che uscirebbe da questo processo ---
$BACKEND = 'http://localhost:0'
$TOKEN   = 'finto'
$script:FAKE_ADMIN = $false
$script:FAKE_ELEV  = $true
$script:CODA       = @()
$script:APPLICATE  = New-Object System.Collections.ArrayList
$script:RIFERITE   = New-Object System.Collections.ArrayList
$script:ELEVAZIONI = 0

function Say($m, $c = 'Gray') {}
function Say-Ok($m, $tag = '') {}
function Say-Info($m, $tag = '') {}
function Say-Step($m, $tag = '') {}
function Say-Warn($m, $tag = '') {}
function Say-Err($m, $tag = '') {}
function Write-Journal { }
function Test-Admin { return $script:FAKE_ADMIN }
function Start-StartupElevato { $script:ELEVAZIONI++; return $script:FAKE_ELEV }
function Set-StartupEntry($voce, $enable) {
  [void]$script:APPLICATE.Add("$($voce.name)")
  return @{ ok = $true; msg = '' }
}
function Invoke-RestMethod {
  param($Uri, $Method, $Headers, $Body, $ContentType, $TimeoutSec, $OutFile)
  if ("$Uri" -like '*/agent/startup-actions') {
    # La risposta passa da JSON come quella vera: `$a.entry` deve comportarsi
    # allo stesso modo, e un array di un elemento e' proprio il caso storto.
    return (@{ actions = @($script:CODA) } | ConvertTo-Json -Depth 6) | ConvertFrom-Json
  }
  if ("$Uri" -like '*/agent/startup-actions/result') {
    [void]$script:RIFERITE.Add(([System.Text.Encoding]::UTF8.GetString($Body) | ConvertFrom-Json))
    return @{ ok = $true }
  }
  throw "chiamata non prevista: $Uri"
}

Invoke-Expression $intoccabili
foreach ($d in $defs) { Invoke-Expression $d.Extent.Text }

# --- le voci di prova ---
$UTENTE = @{ id = 'a1'; enable = $false; entry = @{
  name = 'DiscordUpdate'; display = 'Discord Updater'; source = 'registry'
  location = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' } }
$SERVIZIO = @{ id = 'b2'; enable = $false; entry = @{
  name = 'GoogleUpdate'; display = 'Google Update Service'; source = 'service'
  svc_name = 'gupdate'; location = '' } }
$INTOCCABILE = @{ id = 'c3'; enable = $false; entry = @{
  name = 'WinDefend'; display = 'Microsoft Defender Antivirus Service'; source = 'service'
  svc_name = 'WinDefend'; location = '' } }

$esiti = New-Object System.Collections.ArrayList
function Prova($nome, $blocco) {
  $script:APPLICATE  = New-Object System.Collections.ArrayList
  $script:RIFERITE   = New-Object System.Collections.ArrayList
  $script:ELEVAZIONI = 0
  try {
    & $blocco
    [void]$esiti.Add(@{ nome = $nome; ok = $true; msg = '' })
    Write-Host ("  ok   {0}" -f $nome) -ForegroundColor Green
  } catch {
    [void]$esiti.Add(@{ nome = $nome; ok = $false; msg = "$($_.Exception.Message)" })
    Write-Host ("  FAIL {0}: {1}" -f $nome, $_.Exception.Message) -ForegroundColor Red
  }
}
function Assert($cond, $msg) { if (-not $cond) { throw $msg } }
function Riferiti() {
  $ids = @()
  foreach ($r in $script:RIFERITE) { foreach ($x in @($r.results)) { $ids += "$($x.id)" } }
  return $ids
}

Write-Host "`nAzioni di avvio - comportamento reale" -ForegroundColor Cyan

Prova 'senza admin, le voci utente non aspettano il prompt' {
  $script:FAKE_ADMIN = $false; $script:FAKE_ELEV = $true
  $script:CODA = @($UTENTE, $SERVIZIO)
  $n = Invoke-StartupActions
  Assert ($script:APPLICATE -contains 'DiscordUpdate') 'la voce utente doveva essere applicata subito'
  Assert (-not ($script:APPLICATE -contains 'GoogleUpdate')) 'il servizio doveva passare alla copia elevata'
  Assert ($script:ELEVAZIONI -eq 1) "elevazioni attese 1, viste $($script:ELEVAZIONI)"
  Assert (((Riferiti) -join ',') -eq 'a1') 'al backend doveva arrivare solo l esito della voce utente'
  Assert ($n -eq 1) "riuscite attese 1, viste $n"
}

Prova 'se il permesso viene negato, si prova lo stesso' {
  $script:FAKE_ADMIN = $false; $script:FAKE_ELEV = $false
  $script:CODA = @($UTENTE, $SERVIZIO)
  [void](Invoke-StartupActions)
  Assert ($script:APPLICATE -contains 'GoogleUpdate') 'senza elevazione il servizio va provato lo stesso, per far tornare l errore'
  Assert ($script:ELEVAZIONI -eq 1) 'l elevazione va tentata una volta sola'
  $ids = (Riferiti | Sort-Object) -join ','
  Assert ($ids -eq 'a1,b2') "esiti attesi a1,b2 - visti $ids"
}

Prova 'da amministratore non chiede niente a nessuno' {
  $script:FAKE_ADMIN = $true; $script:FAKE_ELEV = $true
  $script:CODA = @($UTENTE, $SERVIZIO)
  [void](Invoke-StartupActions)
  Assert ($script:ELEVAZIONI -eq 0) 'gia elevato: non deve rilanciarsi'
  Assert ($script:APPLICATE.Count -eq 2) 'entrambe le voci vanno applicate qui'
}

Prova 'una voce intoccabile non fa comparire il prompt' {
  $script:FAKE_ADMIN = $false; $script:FAKE_ELEV = $true
  $script:CODA = @($INTOCCABILE)
  [void](Invoke-StartupActions)
  Assert ($script:ELEVAZIONI -eq 0) 'chiedere l amministratore per poi rifiutare comunque e un prompt per niente'
  Assert ((Riferiti) -contains 'c3') 'il rifiuto deve comunque tornare alla dashboard'
}

Prova 'una coda vuota non fa niente' {
  $script:FAKE_ADMIN = $false; $script:FAKE_ELEV = $true
  $script:CODA = @()
  $n = Invoke-StartupActions
  Assert ($n -eq 0) 'niente in coda, niente da fare'
  Assert ($script:RIFERITE.Count -eq 0) 'senza azioni non si scrive al backend'
  Assert ($script:ELEVAZIONI -eq 0) 'senza azioni non si chiede l elevazione'
}

Prova 'una sola azione di sistema in coda' {
  # Il caso in cui PowerShell 5.1 spacchetta l array di un elemento: se
  # `@($daElevare)` non fosse esplicito, qui si passerebbe uno scalare.
  $script:FAKE_ADMIN = $false; $script:FAKE_ELEV = $false
  $script:CODA = @($SERVIZIO)
  [void](Invoke-StartupActions)
  Assert ($script:APPLICATE.Count -eq 1) "applicate attese 1, viste $($script:APPLICATE.Count)"
  Assert (((Riferiti) -join ',') -eq 'b2') 'l unico esito deve arrivare al backend'
}

$falliti = @($esiti | Where-Object { -not $_.ok })
Write-Host ("`n{0} prove, {1} fallite" -f $esiti.Count, $falliti.Count) -ForegroundColor $(if ($falliti.Count) { 'Red' } else { 'Green' })
if ($falliti.Count) { exit 1 }
exit 0
