"""PowerShell agent, served at GET /api/agent/script. Downloaded to a file and run as
`powershell -ExecutionPolicy Bypass -File forgefps.ps1 -Token <TOKEN> -Mode <mode>` (no irm|iex).
Modes:
  sync      -> safe: detect hardware/health/startup and report (no changes)
               High-precision detection: real CPU/GPU temps via LibreHardwareMonitor (admin),
               64-bit VRAM, locale-independent power plan (by GUID), accurate startup count,
               broad cleanable-space scan, 3-sample averaged RAM usage, configured RAM speed.
  benchmark -> quick CPU/RAM/disk/network benchmark and report it
  optimize  -> graphical window (WinForms) with tweaks grouped in TABS + presets,
               shows each tweak's current state, before/after benchmark
  restore   -> revert every tweak from the backup file
All reg/service/DNS/power tweaks are backed up before being applied so `restore` reverts them."""

from pathlib import Path as _Path

PS_SCRIPT = r'''Param([string]$Token = '', [string]$Mode = 'sync')
$ErrorActionPreference = 'SilentlyContinue'
$BACKEND = '__BACKEND_URL__'
$TOKEN   = $Token
$MODE    = $Mode
$BACKUP  = Join-Path $env:TEMP 'forgefps_backup.json'
$BACKUP_LEGACY = Join-Path $env:TEMP 'boostpc_backup.json'  # v0.7.3+: fallback lettura vecchio nome
$script:PROFILE = @(__PROFILE_IDS__)
$INSTALLED_VER = '__INSTALLED_AGENT_VER__'
$LATEST_VER    = '__LATEST_AGENT_VER__'
$AGENT_DL_URL  = '__AGENT_DL_URL__'

if ([string]::IsNullOrWhiteSpace($TOKEN)) {
  Write-Host ''
  Write-Host '[ERR ] Token mancante / Missing token.' -ForegroundColor Red
  Write-Host 'Esegui / Run:  powershell -ExecutionPolicy Bypass -File .\forgefps.ps1 -Token IL_TUO_TOKEN -Mode optimize' -ForegroundColor Yellow
  Write-Host 'Il token si trova nella pagina "FrameForge Agent" del tuo account. / Find the token on the FrameForge Agent page.' -ForegroundColor Yellow
  return
}

function Say($m, $c='Gray') { Write-Host $m -ForegroundColor $c }

# Cinque severita', cinque colori, una sola scrittura per ciascuna.
#
# `Say` resta la primitiva "stampa questa riga in questo colore" e serve alle
# righe che non sono messaggi di stato: banner, valori del benchmark, prose.
# Li' il colore e' formattazione, non severita' — il giallo marca sia gli avvisi
# sia l'intestazione, e dedurre la severita' dal colore sbaglierebbe.
#
# Il `tag` e' il CONTESTO (LAB, FPS, TERMICA...), che e' un asse diverso dalla
# severita'. Prima i due finivano nello stesso slot fra parentesi quadre: da li'
# venivano i venti prefissi diversi, con [OK] e [ OK ] che convivevano.
# Aggiungere una severita' nuova ora richiede di scrivere una funzione: e' il
# punto: la prossima persona se ne accorge invece di inventare un prefisso.
function _SayLvl($lvl, $color, $m, $tag) {
  $s = "$m"
  # L'indentazione e gli a-capo iniziali appartengono al chiamante e servono a
  # dare gerarchia alle sotto-voci: il prefisso va dopo, non prima.
  $i = 0
  while ($i -lt $s.Length -and ($s[$i] -eq ' ' -or $s[$i] -eq "`n" -or $s[$i] -eq "`r" -or $s[$i] -eq "`t")) { $i++ }
  $t = ''
  if ($tag) { $t = "[$tag] " }
  Write-Host ($s.Substring(0, $i) + $lvl + ' ' + $t + $s.Substring($i)) -ForegroundColor $color
}
function Say-Ok  ($m, $tag = '') { _SayLvl '[ OK ]' 'Green'      $m $tag }
function Say-Info($m, $tag = '') { _SayLvl '[INFO]' 'DarkGray'   $m $tag }
function Say-Step($m, $tag = '') { _SayLvl '[STEP]' 'Cyan'       $m $tag }
function Say-Warn($m, $tag = '') { _SayLvl '[WARN]' 'DarkYellow' $m $tag }
function Say-Err ($m, $tag = '') { _SayLvl '[ERR ]' 'Red'        $m $tag }
function ConvertTo-HashtableSafe { $h=@{}; foreach($p in $input.PSObject.Properties){ $h[$p.Name]=$p.Value }; return $h }

Say '======================================' 'Yellow'
Say '   FrameForge Agent  (PowerShell)' 'Yellow'
Say '======================================' 'Yellow'

function Test-Admin {
  return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ---------------- Backup helpers ----------------
$script:BK = @{}
# v0.7.3+: fallback lettura vecchio nome per upgrade indolore
$__bkFile = if (Test-Path $BACKUP) { $BACKUP } elseif (Test-Path $BACKUP_LEGACY) { $BACKUP_LEGACY } else { '' }
if ($__bkFile) { try { $script:BK = Get-Content $__bkFile -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe } catch { $script:BK = @{} } }
# v0.7.7: mappa tweak-id -> chiavi di backup che quel tweak ha creato (per revert granulare)
$script:TWKEYS = @{}
if ($script:BK.ContainsKey('__tweak_keys__')) {
  $__tk = $script:BK['__tweak_keys__']
  if ($__tk) { foreach ($p in $__tk.PSObject.Properties) { $script:TWKEYS[$p.Name] = @($p.Value) } }
  $script:BK.Remove('__tweak_keys__')
}
# Quando ogni tweak e' stato applicato. Il backup sapeva gia' COSA era stato
# cambiato e come rimetterlo a posto, ma non QUANDO: senza, la cronologia delle
# modifiche non si puo' raccontare, e la reversibilita' — che e' la cosa che
# distingue davvero questo strumento — resta un bottone invece di una storia.
$script:TWAT = @{}
if ($script:BK.ContainsKey('__applied_at__')) {
  $__ta = $script:BK['__applied_at__']
  if ($__ta) { foreach ($p in $__ta.PSObject.Properties) { $script:TWAT[$p.Name] = "$($p.Value)" } }
  $script:BK.Remove('__applied_at__')
}

function Backup-Reg($path, $name, $type) {
  $key = "$path::$name"
  if ($script:BK.ContainsKey($key)) { return }
  $cur = (Get-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue).$name
  if ($null -eq $cur) { $script:BK[$key] = '__ABSENT__' } else { $script:BK[$key] = "$type|$cur" }
}
# ---------------- SECURITY GUARDRAILS ----------------
# FrameForge non tocca MAI Windows Defender / Firewall / servizi di sicurezza.
$script:FORBIDDEN_SVC = @('WinDefend','WdNisSvc','WdFilter','WdBoot','Sense','SecurityHealthService',
  'wscsvc','mpssvc','MpsSvc','SgrmBroker','SgrmAgent','webthreatdefsvc','webthreatdefusersvc')
$script:FORBIDDEN_REG = @('Windows Defender','WinDefend','Microsoft\Security Center',
  'SecurityHealthService','Microsoft\Windows Security Health','Microsoft\Windows Defender')

function Test-ForbiddenReg($path) {
  foreach ($p in $script:FORBIDDEN_REG) { if ($path -like "*$p*") { return $true } }
  return $false
}
function Test-ForbiddenSvc($name) { return ($script:FORBIDDEN_SVC -contains $name) }

function Set-Reg($path, $name, $type, $value) {
  if (Test-ForbiddenReg $path) { Write-Host "[WARN][SEC] Modifica bloccata (area protetta): $path" -ForegroundColor Yellow; return }
  Backup-Reg $path $name $type
  if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
  New-ItemProperty -Path $path -Name $name -PropertyType $type -Value $value -Force | Out-Null
}
function Disable-ServiceSafe($name) {
  if (Test-ForbiddenSvc $name) { Write-Host "[WARN][SEC] Servizio protetto, non modificato: $name" -ForegroundColor Yellow; return $false }
  $svc = Get-Service $name -ErrorAction SilentlyContinue
  if ($svc -and $svc.Status -eq 'Running' -and -not $script:BK.ContainsKey("svc::$name")) {
    $script:BK["svc::$name"] = "$($svc.StartType)"
    Stop-Service $name -Force 2>$null
    Set-Service $name -StartupType Disabled 2>$null
  }
  return $true
}
function Save-Backup {
  $__out = @{}
  foreach ($k in $script:BK.Keys) { $__out[$k] = $script:BK[$k] }
  if ($script:TWKEYS.Count -gt 0) { $__out['__tweak_keys__'] = $script:TWKEYS }
  if ($script:TWAT.Count -gt 0) { $__out['__applied_at__'] = $script:TWAT }
  $__out | ConvertTo-Json -Depth 6 | Set-Content $BACKUP
  # v0.7.3+: se esiste ancora il legacy, rimuovilo (dopo il primo save su nuovo path)
  if (Test-Path $BACKUP_LEGACY) { Remove-Item $BACKUP_LEGACY -ErrorAction SilentlyContinue }
}

# v0.7.7: applica un tweak tracciando quali chiavi di backup ha creato -> revert granulare
function Invoke-ApplyTracked($t) {
  $__pre = @($script:BK.Keys)
  & $t.apply
  $__new = @($script:BK.Keys | Where-Object { $__pre -notcontains $_ })
  if ($__new.Count -gt 0) {
    $__ex = @(); if ($script:TWKEYS.ContainsKey($t.id)) { $__ex = @($script:TWKEYS[$t.id]) }
    $script:TWKEYS[$t.id] = @(@($__ex + $__new) | Select-Object -Unique)
  }
  $script:TWAT[$t.id] = (Get-Date).ToString('o')
}
function Get-RevertableIds { return @($script:TWKEYS.Keys) }
function Get-BackupIds { if ($script:TWKEYS.Count -gt 0) { return @($script:TWKEYS.Keys) } return @($script:BK.Keys) }

function Get-RegVal($path, $name) { return (Get-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue).$name }

# ---- Stato di un tweak: un codice, non una frase ----
# Quattro stati: ok (gia' ottimale), todo (c'e' da applicare), na (non
# applicabile su questo hardware), unknown (non determinabile).
#
# Il codice lo decide il tweak, non si deduce dal testo: la stessa parola vale
# il contrario a seconda del contesto. 'Attivo' e' ottimale quasi ovunque, ma
# per search_index vuol dire che il servizio di indicizzazione sta girando —
# cioe' che il tweak NON e' applicato. Finche' la GUI classificava con una
# regex sulla frase, mostrava quel tweak in verde e lo contava fra i "gia'
# ottimali" proprio quando non lo era; stesso errore per i due tweak GPU, dove
# 'applicabile' veniva letto come 'applicato'.
#
# L'etichetta resta quella di prima: cambia solo che accanto viaggia il codice.
function Tw($code, $label) { return @{ code = "$code"; label = "$label" } }

function Get-TwState($t) {
  try { $r = & $t.state } catch { return (Tw 'unknown' 'n/d') }
  if ($r -is [hashtable] -and $r.ContainsKey('code')) { return $r }
  # Un tweak che ritorna ancora una stringa libera: si mostra, ma senza fingere
  # di sapere cosa significhi.
  return (Tw 'unknown' "$r")
}
function Get-GpuPnp { $g = Get-CimInstance Win32_VideoController | Where-Object { $_.PNPDeviceID -like 'PCI*' } | Select-Object -First 1; return $g.PNPDeviceID }
function Get-GpuVendor {
  $g = (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -notmatch 'Basic|Virtual|Remote|Meta' } | Select-Object -First 1).Name
  if ($g -match 'NVIDIA|GeForce|RTX|GTX') { return 'NVIDIA' }
  if ($g -match 'AMD|Radeon|RX ') { return 'AMD' }
  if ($g -match 'Intel|Arc|UHD|Iris') { return 'Intel' }
  return 'n/d'
}

# ---------------- Profilo hardware adattivo ----------------
function Get-HwProfile {
  $lap = $false
  $ct = (Get-CimInstance Win32_SystemEnclosure -ErrorAction SilentlyContinue).ChassisTypes
  foreach ($c in @($ct)) { if (@(8,9,10,14,30,31,32) -contains [int]$c) { $lap = $true } }
  if (-not $lap) { if (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue) { $lap = $true } }
  $ram = 0; try { $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB) } catch {}
  $ssd = $false
  try { $mt = (Get-Partition -DriveLetter C -ErrorAction SilentlyContinue | Get-Disk | Get-PhysicalDisk).MediaType; if ("$mt" -match 'SSD') { $ssd = $true } } catch {}
  if (-not $ssd) { try { $bt = (Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object -First 1).BusType; if ($bt -eq 17) { $ssd = $true } } catch {} }
  $b = 0; try { $b = [int](Get-CimInstance Win32_OperatingSystem).BuildNumber } catch {}
  return @{ laptop = $lap; ram = $ram; ssd = $ssd; win11 = ($b -ge 22000); gpu = (Get-GpuVendor) }
}
$script:HW = Get-HwProfile

# ---------------- Precision helpers (LibreHardwareMonitor, VRAM, power, startup) ----------------
$script:LHM_DIR = Join-Path $env:TEMP 'boostpc_lhm'
$script:LHM_ZIP_URL = 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.4/LibreHardwareMonitor-net472.zip'
$script:LHM_COMP = $null
$script:LHM_TRIED = $false
$script:LHM_LAST = ''

function Test-MemoryIntegrity {
  try {
    $ssr = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard' -Name SecurityServicesRunning -ErrorAction SilentlyContinue).SecurityServicesRunning
    if ($ssr -and ($ssr -contains 2)) { return $true }
    $v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity' -Name Enabled -ErrorAction SilentlyContinue).Enabled
    return ($v -eq 1)
  } catch { return $false }
}

function Test-VulnerableDriverBlocklist {
  try {
    $v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Config' -Name VulnerableDriverBlocklistEnable -ErrorAction SilentlyContinue).VulnerableDriverBlocklistEnable
    # On Windows 11 the blocklist is ON by default even when the value is absent.
    if ($null -eq $v) {
      $build = [int]([regex]::Match("$((Get-CimInstance Win32_OperatingSystem).BuildNumber)", '\d+').Value)
      return ($build -ge 22000)
    }
    return ($v -eq 1)
  } catch { return $false }
}

function Get-LhmComputer {
  if ($script:LHM_COMP) { return $script:LHM_COMP }
  if ($script:LHM_TRIED) { return $null }
  $script:LHM_TRIED = $true
  if (-not (Test-Admin)) { return $null }
  try {
    $dll = Join-Path $script:LHM_DIR 'LibreHardwareMonitorLib.dll'
    if (-not (Test-Path $dll)) {
      Say-Info '   Scarico LibreHardwareMonitor (una volta sola)...' 'Sensori'
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      $zip = Join-Path $env:TEMP 'boostpc_lhm.zip'
      Invoke-WebRequest $script:LHM_ZIP_URL -OutFile $zip -UseBasicParsing
      if (Test-Path $script:LHM_DIR) { Remove-Item $script:LHM_DIR -Recurse -Force -ErrorAction SilentlyContinue }
      Expand-Archive -Path $zip -DestinationPath $script:LHM_DIR -Force
      Remove-Item $zip -ErrorAction SilentlyContinue
      Get-ChildItem $script:LHM_DIR -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path $dll)) {
      $found = Get-ChildItem $script:LHM_DIR -Recurse -Filter 'LibreHardwareMonitorLib.dll' -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($found) { $dll = $found.FullName } else { return $null }
    }
    $hid = Get-ChildItem (Split-Path $dll) -Filter 'HidSharp.dll' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hid) { Add-Type -Path $hid.FullName -ErrorAction SilentlyContinue }
    Add-Type -Path $dll
    $c = New-Object LibreHardwareMonitor.Hardware.Computer
    $c.IsCpuEnabled = $true
    $c.IsGpuEnabled = $true
    $c.IsMotherboardEnabled = $true
    $c.IsControllerEnabled = $true
    $c.Open()
    foreach ($hw in $c.Hardware) { $hw.Update(); foreach ($sh in $hw.SubHardware) { $sh.Update() } }
    Start-Sleep -Milliseconds 400
    $script:LHM_COMP = $c
    return $c
  } catch { Say-Warn ('   Errore LibreHardwareMonitor: ' + $_.Exception.Message) 'Sensori'; return $null }
}

function Get-LhmTemps {
  # Real CPU/GPU temperatures + fan RPM + VRM temps + power draw + Vcore
  # from hardware sensors (incl. motherboard SuperIO). Requires admin.
  # v0.7.7: multi-sensor extraction — fan_rpm_max, vrm_temp, cpu_power, gpu_power_lhm, cpu_vcore.
  $r = @{}
  $c = Get-LhmComputer
  if (-not $c) { $r._lhm_state = 'no_lhm'; return $r }
  try {
    $cpuTemps = @{}; $gpuTemps = @{}; $mbTemps = @{}
    $fanRpms = @{}; $cpuPowers = @{}; $gpuPowers = @{}; $vcores = @{}
    $found = New-Object 'System.Collections.Generic.List[string]'
    $all = New-Object 'System.Collections.Generic.List[object]'
    foreach ($hw in $c.Hardware) { [void]$all.Add($hw); foreach ($sh in $hw.SubHardware) { [void]$all.Add($sh) } }
    foreach ($hw in $all) {
      $hw.Update()
      $ht = "$($hw.HardwareType)"
      foreach ($sensor in $hw.Sensors) {
        if ($null -eq $sensor.Value) { continue }
        $st = "$($sensor.SensorType)"
        $sn = "$($sensor.Name)"
        $sv = [double]$sensor.Value
        if ($st -eq 'Temperature') {
          $found.Add(("{0}/T/{1}={2}" -f $ht, $sn, [int][math]::Round($sv)))
          if ($sv -le 0 -or $sv -gt 150) { continue }
          if ($ht -eq 'Cpu') { $cpuTemps[$sn] = $sv }
          elseif ($ht -like 'Gpu*') { $gpuTemps[$sn] = $sv }
          else { $mbTemps[$sn] = $sv }
        } elseif ($st -eq 'Fan') {
          if ($sv -gt 0 -and $sv -lt 10000) { $fanRpms[("{0}/{1}" -f $ht, $sn)] = $sv }
        } elseif ($st -eq 'Power') {
          if ($sv -le 0 -or $sv -gt 1000) { continue }
          if ($ht -eq 'Cpu' -and $sn -match '(?i)package|cpu total|cpu\s*power') { $cpuPowers[$sn] = $sv }
          elseif ($ht -like 'Gpu*' -and $sn -match '(?i)gpu total|gpu power|package|board') { $gpuPowers[$sn] = $sv }
        } elseif ($st -eq 'Voltage') {
          if ($ht -eq 'Cpu' -and $sn -match '(?i)vcore|core\s*#?0|cpu\s*core') {
            if ($sv -gt 0.3 -and $sv -lt 2.0) { $vcores[$sn] = $sv }
          }
        }
      }
    }
    $script:LHM_LAST = ($found -join ', ')
    $cpuVal = $null
    # Prima passata: nomi noti (Intel + Ryzen classic)
    foreach ($k in @('CPU Package', 'Core (Tctl/Tdie)', 'Core (Tctl)', 'Core (Tdie)', 'Core Average', 'Core Max')) {
      if ($cpuTemps.ContainsKey($k)) { $cpuVal = $cpuTemps[$k]; break }
    }
    # v0.7.4d: Ryzen 7000+ / Zen4 espone nomi diversi (es. "Tctl", "Ccd1 (Tdie)", "Package").
    # Regex case-insensitive su qualunque sensore Cpu che contenga tctl/tdie/package/cpu.
    if ($null -eq $cpuVal) {
      foreach ($k in $cpuTemps.Keys) {
        if ($k -match '(?i)tctl|tdie|package|^cpu\s') { $cpuVal = $cpuTemps[$k]; break }
      }
    }
    # Ultima chance: massimo tra tutti i sensori Cpu
    if ($null -eq $cpuVal -and $cpuTemps.Count -gt 0) { $cpuVal = ($cpuTemps.Values | Measure-Object -Maximum).Maximum }
    if ($null -eq $cpuVal) {
      # Motherboard SuperIO fallback: a sensor explicitly named like CPU.
      foreach ($k in $mbTemps.Keys) { if ($k -match '(?i)cpu') { $cpuVal = $mbTemps[$k]; break } }
    }
    if ($null -ne $cpuVal -and $cpuVal -gt 0) { $r.cpu_temp = [int][math]::Round($cpuVal) }
    $gpuVal = $null
    foreach ($k in @('GPU Core', 'GPU Hot Spot', 'GPU')) { if ($gpuTemps.ContainsKey($k)) { $gpuVal = $gpuTemps[$k]; break } }
    if ($null -eq $gpuVal -and $gpuTemps.Count -gt 0) { $gpuVal = ($gpuTemps.Values | Measure-Object -Maximum).Maximum }
    if ($null -ne $gpuVal -and $gpuVal -gt 0) { $r.gpu_temp = [int][math]::Round($gpuVal) }
    # v0.7.7: VRM temp — cerca sensori MB con nomi vrm/vr mos/mos/vcore
    foreach ($k in $mbTemps.Keys) {
      if ($k -match '(?i)vrm|vr mos|^mos\s|vcore|vsoc') {
        $r.vrm_temp = [int][math]::Round($mbTemps[$k]); break
      }
    }
    # v0.7.7: fan RPM max — prendi il valore massimo tra tutti i fan sensor
    if ($fanRpms.Count -gt 0) {
      $r.fan_rpm_max = [int][math]::Round(($fanRpms.Values | Measure-Object -Maximum).Maximum)
      $r.fan_count = $fanRpms.Count
    }
    # v0.7.7: CPU package power (W) — priorità a nome "Package" > "CPU Total" > qualunque
    $cpVal = $null
    foreach ($k in @('CPU Package', 'Package', 'CPU Total', 'CPU Power')) {
      if ($cpuPowers.ContainsKey($k)) { $cpVal = $cpuPowers[$k]; break }
    }
    if ($null -eq $cpVal -and $cpuPowers.Count -gt 0) { $cpVal = ($cpuPowers.Values | Measure-Object -Maximum).Maximum }
    if ($null -ne $cpVal -and $cpVal -gt 0) { $r.cpu_power = [int][math]::Round($cpVal) }
    # v0.7.7: GPU power (W) da LHM — usato come fallback quando nvidia-smi non c'è (es. AMD/Intel dGPU)
    $gpVal = $null
    foreach ($k in @('GPU Total', 'GPU Power', 'Board Power', 'Package')) {
      if ($gpuPowers.ContainsKey($k)) { $gpVal = $gpuPowers[$k]; break }
    }
    if ($null -eq $gpVal -and $gpuPowers.Count -gt 0) { $gpVal = ($gpuPowers.Values | Measure-Object -Maximum).Maximum }
    if ($null -ne $gpVal -and $gpVal -gt 0) { $r.gpu_power_lhm = [int][math]::Round($gpVal) }
    # v0.7.7: CPU Vcore (V) — utile per monitorare overclock/undervolt
    if ($vcores.Count -gt 0) {
      $vv = ($vcores.Values | Measure-Object -Average).Average
      $r.cpu_vcore = [math]::Round($vv, 3)
    }
    # Diagnostica: LHM caricato ma nessun sensore CPU trovato
    if (-not $r.ContainsKey('cpu_temp')) {
      if ($cpuTemps.Count -eq 0) { $r._lhm_state = 'no_cpu_sensors' }
      else { $r._lhm_state = 'cpu_sensors_out_of_range' }
    } else {
      $r._lhm_state = 'ok'
    }
  } catch { $r._lhm_state = 'lhm_exception' }
  return $r
}

function Get-GpuVramGb {
  # 64-bit VRAM from registry (WMI AdapterRAM is capped at 4GB and unreliable).
  try {
    $best = 0.0
    $keys = Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue
    foreach ($k in $keys) {
      $qw = (Get-ItemProperty $k.PSPath -Name 'HardwareInformation.qwMemorySize' -ErrorAction SilentlyContinue).'HardwareInformation.qwMemorySize'
      if ($qw -and [double]$qw -gt $best) { $best = [double]$qw }
    }
    if ($best -gt 0) { return [int][math]::Round($best / 1GB) }
  } catch {}
  return $null
}

function Get-PowerPlanNormalized {
  # Locale-independent: classify by scheme GUID, fallback to localized name.
  $out = "$(powercfg /getactivescheme 2>$null)"
  $guid = ([regex]::Match($out, '([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')).Value.ToLower()
  switch ($guid) {
    '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c' { return 'High performance' }
    'e9a42b02-d5df-448d-aa00-03f14749eb61' { return 'Ultimate Performance' }
    '381b4222-f694-41f0-9685-ff5bb260df2e' { return 'Balanced' }
    'a1841308-3541-4fab-bc81-f71556f20b4a' { return 'Power saver' }
    default { return $out }
  }
}

function Get-StartupCount {
  # Accurate: enabled Run entries (excludes disabled via StartupApproved) + startup folders + third-party logon tasks.
  $names = New-Object 'System.Collections.Generic.HashSet[string]'
  $disabled = New-Object 'System.Collections.Generic.HashSet[string]'
  foreach ($sa in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder')) {
    $p = Get-ItemProperty $sa -ErrorAction SilentlyContinue
    if ($p) {
      foreach ($prop in $p.PSObject.Properties) {
        if ($prop.Name -like 'PS*') { continue }
        $b = $prop.Value
        if ($b -is [byte[]] -and $b.Length -gt 0 -and ($b[0] -band 1)) { [void]$disabled.Add($prop.Name.ToLower()) }
      }
    }
  }
  foreach ($rk in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
                    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
                    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run')) {
    $p = Get-ItemProperty $rk -ErrorAction SilentlyContinue
    if ($p) {
      foreach ($prop in $p.PSObject.Properties) {
        if ($prop.Name -like 'PS*') { continue }
        if (-not $disabled.Contains($prop.Name.ToLower())) { [void]$names.Add($prop.Name.ToLower()) }
      }
    }
  }
  foreach ($sf in @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('CommonStartup'))) {
    if ($sf -and (Test-Path $sf)) {
      foreach ($f in (Get-ChildItem $sf -File -ErrorAction SilentlyContinue)) {
        if ($f.Name -notlike 'desktop.ini' -and -not $disabled.Contains($f.Name.ToLower())) { [void]$names.Add($f.Name.ToLower()) }
      }
    }
  }
  try {
    $tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
      $_.State -ne 'Disabled' -and $_.TaskPath -notlike '\Microsoft\*' -and
      ($_.Triggers | Where-Object { "$($_.CimClass.CimClassName)" -eq 'MSFT_TaskLogonTrigger' })
    }
    foreach ($t in $tasks) { [void]$names.Add(('task:' + $t.TaskName).ToLower()) }
  } catch {}
  return $names.Count
}

function Get-CleanableMb {
  # Broader cleanable footprint: user + system temp, Windows Update cache, prefetch, thumbnails, Recycle Bin.
  $paths = @($env:TEMP, "$env:LOCALAPPDATA\Temp", "$env:SystemRoot\Temp",
             "$env:SystemRoot\SoftwareDistribution\Download", "$env:SystemRoot\Prefetch",
             "$env:LOCALAPPDATA\Microsoft\Windows\Explorer",
             "$env:LOCALAPPDATA\Microsoft\Windows\INetCache") | Select-Object -Unique
  $total = 0.0
  foreach ($p in $paths) {
    if ($p -and (Test-Path $p)) {
      try {
        $sum = (Get-ChildItem $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        if ($sum) { $total += [double]$sum }
      } catch {}
    }
  }
  try {
    # Cestino: lettura diretta dei file (niente oggetti COM shell, vedi nota Defender)
    $rbRoot = Join-Path $env:SystemDrive '$Recycle.Bin'
    if (Test-Path $rbRoot) {
      $sum = (Get-ChildItem $rbRoot -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
      if ($sum) { $total += [double]$sum }
    }
  } catch {}
  return [math]::Round($total / 1MB, 1)
}

function Get-AvgRamPct {
  # Average over 3 samples to avoid a single-instant spike skewing the value.
  $vals = @()
  for ($i = 0; $i -lt 3; $i++) {
    $o = Get-CimInstance Win32_OperatingSystem
    if ($o.TotalVisibleMemorySize -gt 0) { $vals += (($o.TotalVisibleMemorySize - $o.FreePhysicalMemory) / $o.TotalVisibleMemorySize * 100) }
    if ($i -lt 2) { Start-Sleep -Milliseconds 500 }
  }
  if ($vals.Count -eq 0) { return $null }
  return [math]::Round(($vals | Measure-Object -Average).Average)
}


# ---------------- Hardware / health detection ----------------

# v0.7.7: Multi-source cross-validation helpers.
# Ogni componente viene rilevato da >=2 fonti indipendenti (WMI + Registry / nvidia-smi)
# per aumentare l'accuratezza e ridurre falsi positivi su laptop ibridi / OEM custom.
function Get-CpuFromRegistry {
  try {
    $p = Get-ItemProperty 'HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0' -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessorNameString) { return "$($p.ProcessorNameString)".Trim() }
  } catch {}
  return $null
}

function Get-GpuAdaptersFromRegistry {
  # Enumera i display adapter dal registry di Windows (Class GUID {4d36e968...}).
  # Restituisce lista di hashtable {name, driver_version, driver_date, provider}.
  $out = New-Object 'System.Collections.Generic.List[object]'
  try {
    $keys = Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue |
            Where-Object { $_.PSChildName -match '^\d{4}$' }
    foreach ($k in $keys) {
      $p = Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue
      if (-not $p) { continue }
      $n = "$($p.DriverDesc)"
      if (-not $n -or $n -match '(?i)Basic|Virtual|Remote|Meta|Parsec|Citrix|DameWare|Idd') { continue }
      $it = @{
        name           = $n
        driver_version = "$($p.DriverVersion)"
        driver_date    = "$($p.DriverDate)"
        provider       = "$($p.ProviderName)"
      }
      [void]$out.Add($it)
    }
  } catch {}
  return $out
}

function Get-PrimaryStorage {
  # Combina Get-Partition + Get-PhysicalDisk per identificare il disco di sistema (C:).
  # Ritorna {type, bus_type, health, wear_pct, model, size_gb}.
  $r = @{}
  try {
    $part = Get-Partition -DriveLetter 'C' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $part) { return $r }
    $pd = Get-PhysicalDisk -ErrorAction SilentlyContinue | Where-Object { $_.DeviceId -eq $part.DiskNumber } | Select-Object -First 1
    if (-not $pd) { return $r }
    $r.storage_model = "$($pd.FriendlyName)".Trim()
    $r.storage_bus = "$($pd.BusType)"
    $mt = "$($pd.MediaType)"
    # BusType NVMe indica NVMe anche se MediaType dice SSD generico
    if ($r.storage_bus -eq 'NVMe') { $r.storage_type = 'NVMe' }
    elseif ($mt -eq 'SSD') { $r.storage_type = 'SSD' }
    elseif ($mt -eq 'HDD') { $r.storage_type = 'HDD' }
    else { $r.storage_type = $mt }
    $r.storage_health = "$($pd.HealthStatus)"
    if ($pd.Size -gt 0) { $r.storage_size_gb = [int]([math]::Round($pd.Size / 1GB)) }
    # Wearout percent (solo su SSD/NVMe che espongono lo storage reliability counter)
    try {
      $rc = Get-StorageReliabilityCounter -PhysicalDisk $pd -ErrorAction SilentlyContinue
      if ($rc -and $null -ne $rc.Wear) { $r.storage_wear_pct = [int]$rc.Wear }
      if ($rc -and $null -ne $rc.Temperature -and $rc.Temperature -gt 0) { $r.storage_temp = [int]$rc.Temperature }
    } catch {}
  } catch {}
  return $r
}

function Get-Specs {
  $s = @{}
  $os = Get-CimInstance Win32_OperatingSystem
  $s.os = $os.Caption; $s.os_build = "$($os.BuildNumber)"
  $ct = (Get-CimInstance Win32_SystemEnclosure).ChassisTypes -join ','
  $s.form_factor = if ('8','9','10','14','30','31','32' | Where-Object { $ct -match $_ }) { 'Laptop' } else { 'Desktop' }
  $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
  $s.cpu = $cpu.Name; $s.cpu_cores = "$($cpu.NumberOfCores)"; $s.cpu_threads = "$($cpu.NumberOfLogicalProcessors)"
  $s.cpu_clock_ghz = "$([math]::Round($cpu.MaxClockSpeed/1000,2))"
  $s.cpu_socket = "$($cpu.SocketDesignation)"
  # v0.7.7: cross-check CPU name da Registry (fallback + validation).
  $cpuReg = Get-CpuFromRegistry
  $cpuSources = 1
  if ($cpuReg) {
    $cpuSources = 2
    # WMI a volte tronca / restituisce nomi generici — se Registry ha una stringa piu' lunga, preferiscila.
    if ((-not $s.cpu) -or ($cpuReg.Length -gt "$($s.cpu)".Length)) { $s.cpu = $cpuReg }
  }
  # Rilevamento GPU: nvidia-smi > WMI (multi-adapter aware) > Registry.
  # v0.7.7: su laptop ibridi preferiamo sempre la GPU discreta e riportiamo anche la secondaria.
  $gpuSources = 0
  $nv = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null
  if ($nv) {
    $p = ($nv | Select-Object -First 1).Split(',')
    $s.gpu = $p[0].Trim(); $s.gpu_vram_gb = "$([math]::Round([double]$p[1].Trim()/1024))"; $s.gpu_driver_version = $p[2].Trim()
    $s.gpu_provider = 'NVIDIA'
    $gpuSources++
    # PCIe link reale + stato Resizable BAR (BAR1 ~ VRAM => ReBAR ON, 256MB => OFF)
    try {
      $pcieQ = & nvidia-smi --query-gpu=pcie.link.width.current,pcie.link.width.max,pcie.link.gen.max --format=csv,noheader,nounits 2>$null
      if ($pcieQ) {
        $pl = ($pcieQ | Select-Object -First 1).Split(',')
        $s.pcie_width = $pl[0].Trim(); $s.pcie_width_max = $pl[1].Trim()
        $s.pcie_link = ('x{0} (max x{1} Gen{2})' -f $pl[0].Trim(), $pl[1].Trim(), $pl[2].Trim())
      }
      $qFull = (& nvidia-smi -q 2>$null) -join "`n"
      if ($qFull -match 'BAR1 Memory Usage[\s\S]{0,120}?Total\s*:\s*(\d+)\s*MiB') {
        $barMb = [int]$Matches[1]
        $s.rebar_status = $(if ($barMb -ge 1024) { 'on' } else { 'off' })
      }
    } catch {}
  }
  # WMI: prendi tutti i video controller reali (non virtuali).
  $vcAll = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -and $_.Name -notmatch 'Basic|Virtual|Remote|Meta|Parsec|Citrix|DameWare|Idd' }
  if (-not $vcAll) { $vcAll = Get-CimInstance Win32_VideoController }
  # Ordina preferendo discrete (NVIDIA/AMD Radeon RX/Intel Arc) su integrated (UHD/Iris/Vega iGPU).
  $vcSorted = @($vcAll | Sort-Object -Property @{Expression={
    $n = "$($_.Name)"
    if ($n -match '(?i)^NVIDIA|GeForce|Quadro|Tesla|RTX|GTX') { 0 }
    elseif ($n -match '(?i)Radeon\s+(RX|Pro)') { 0 }
    elseif ($n -match '(?i)Intel\s+Arc') { 0 }
    elseif ($n -match '(?i)UHD|Iris|HD Graphics|Vega\s+(3|8|10|11)|Radeon\s+Graphics') { 2 }
    else { 1 }
  }})
  $vcPrimary = $vcSorted | Select-Object -First 1
  if ($vcPrimary) {
    $gpuSources++
    if (-not $s.gpu) {
      $s.gpu = $vcPrimary.Name; $s.gpu_driver_version = $vcPrimary.DriverVersion
      $vram = Get-GpuVramGb
      if ($vram) { $s.gpu_vram_gb = "$vram" }
      elseif ($vcPrimary.AdapterRAM -gt 0) { $s.gpu_vram_gb = "$([math]::Round($vcPrimary.AdapterRAM/1GB))" }
      # Determina provider
      $gn = "$($vcPrimary.Name)"
      if ($gn -match '(?i)nvidia|geforce|quadro|rtx|gtx') { $s.gpu_provider = 'NVIDIA' }
      elseif ($gn -match '(?i)radeon|amd\s') { $s.gpu_provider = 'AMD' }
      elseif ($gn -match '(?i)intel') { $s.gpu_provider = 'Intel' }
    }
  }
  # GPU secondaria (iGPU su laptop / dual-GPU desktop)
  if ($vcSorted.Count -gt 1) {
    $vc2 = $vcSorted[1]
    if ($vc2.Name -and "$($vc2.Name)".Trim() -ne "$($s.gpu)".Trim()) {
      $s.gpu_secondary = "$($vc2.Name)"
    }
  }
  # Registry cross-check
  $regGpus = Get-GpuAdaptersFromRegistry
  if ($regGpus.Count -gt 0) { $gpuSources++ }
  $s.refresh_hz = "$((Get-CimInstance Win32_VideoController | Where-Object {$_.CurrentRefreshRate -gt 0} | Sort-Object CurrentRefreshRate -Descending | Select-Object -First 1).CurrentRefreshRate)"
  $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)
  $s.ram = "$ram GB"
  $pm = Get-CimInstance Win32_PhysicalMemory
  $pm1 = $pm | Select-Object -First 1
  $s.ram_speed_mhz = "$(if ($pm1.ConfiguredClockSpeed -and $pm1.ConfiguredClockSpeed -gt 0) { $pm1.ConfiguredClockSpeed } else { $pm1.Speed })"
  $s.ram_modules = "$(($pm | Measure-Object).Count)"
  $s.ram_type = @{ '20'='DDR'; '21'='DDR2'; '24'='DDR3'; '26'='DDR4'; '34'='DDR5' }["$($pm1.SMBIOSMemoryType)"]
  # v0.7.7: RAM manufacturer (utile per identificare Corsair/G.Skill/Kingston etc)
  $ramMfg = "$($pm1.Manufacturer)".Trim()
  if ($ramMfg -and $ramMfg -notmatch '(?i)^(unknown|to be filled|manufacturer)$' -and $ramMfg.Length -gt 1) {
    $s.ram_manufacturer = $ramMfg
  }
  $ramSources = 2  # Win32_ComputerSystem + Win32_PhysicalMemory concordano
  $b = Get-CimInstance Win32_BaseBoard | Where-Object { $_.Product -and $_.Product -notmatch 'Base Board|Default string|To be filled|None' } | Select-Object -First 1
  if (-not $b) { $b = Get-CimInstance Win32_BaseBoard | Select-Object -First 1 }
  $mfg = "$($b.Manufacturer)"
  $vm = @{ 'micro-star'='MSI'; 'asustek'='ASUS'; 'gigabyte'='Gigabyte'; 'asrock'='ASRock'; 'hewlett'='HP'; 'lenovo'='Lenovo'; 'dell'='Dell' }
  foreach ($k in $vm.Keys) { if ($mfg.ToLower().Contains($k)) { $mfg = $vm[$k]; break } }
  $prod = "$($b.Product)"
  $s.motherboard = if ($prod.ToLower().Contains($mfg.ToLower())) { $prod } else { ("$mfg $prod").Trim() }
  $s.system_model = "$((Get-CimInstance Win32_ComputerSystem).Model)"
  $bi = Get-CimInstance Win32_BIOS | Select-Object -First 1
  $s.bios = "$($bi.Manufacturer) $($bi.SMBIOSBIOSVersion)"
  if ($s.motherboard -match '\b([XZBHA]\d{3}E?)\b') { $s.chipset = $matches[1].ToUpper() }
  if ($s.cpu_socket -notmatch 'AM\d|LGA|sTR|sWRX|SP\d|TR4') {
    switch -Regex ($s.chipset) {
      '^(X570|B550|A520|X470|B450|X370|B350|A320)$' { $s.cpu_socket = 'AM4' }
      '^(X670E?|B650E?|A620)$' { $s.cpu_socket = 'AM5' }
      '^(Z790|B760|H770|H610|Z690|B660|H670)$' { $s.cpu_socket = 'LGA1700' }
      '^(Z590|B560|H570|H510|Z490|B460|H470)$' { $s.cpu_socket = 'LGA1200' }
    }
  }
  $v = Get-CimInstance Win32_VideoController | Select-Object -First 1
  if ($v.CurrentHorizontalResolution) { $s.resolution = "$($v.CurrentHorizontalResolution)x$($v.CurrentVerticalResolution)" }

  # ----- v0.7.7 Hardware Insights: dati extra per consigli mirati -----
  # (a) velocita' nominale RAM (per check XMP: nominale vs configurata)
  if ($pm1.Speed -and $pm1.Speed -gt 0) { $s.ram_speed_nominal_mhz = "$($pm1.Speed)" }
  # (c) refresh massimo supportato dal monitor (EDID)
  try {
    $maxHz = 0
    Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorListedSupportedSourceModes -ErrorAction SilentlyContinue | ForEach-Object {
      foreach ($m in $_.MonitorSourceModes) {
        if ($m.VerticalRefreshRateNumerator -and $m.VerticalRefreshRateDenominator -gt 0) {
          $hz = [math]::Round($m.VerticalRefreshRateNumerator / $m.VerticalRefreshRateDenominator)
          if ($hz -gt $maxHz -and $hz -le 600) { $maxHz = $hz }
        }
      }
    }
    if ($maxHz -gt 0) { $s.max_refresh_hz = "$maxHz" }
  } catch {}
  # (d) dischi fissi: tipo (NVMe/SATA SSD/HDD), dimensione e spazio libero
  try {
    $disks = @()
    foreach ($vol in (Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' })) {
      $dtype = 'Unknown'
      try {
        $part = Get-Partition -DriveLetter $vol.DriveLetter -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($part) {
          $pd = Get-PhysicalDisk -ErrorAction SilentlyContinue | Where-Object { "$($_.DeviceId)" -eq "$($part.DiskNumber)" } | Select-Object -First 1
          if ($pd) {
            if ("$($pd.BusType)" -eq 'NVMe') { $dtype = 'NVMe SSD' }
            elseif ("$($pd.MediaType)" -eq 'SSD') { $dtype = 'SATA SSD' }
            elseif ("$($pd.MediaType)" -eq 'HDD') { $dtype = 'HDD' }
            elseif ("$($pd.MediaType)") { $dtype = "$($pd.MediaType)" }
          }
        }
      } catch {}
      $disks += @{ letter = "$($vol.DriveLetter)"; type = $dtype
                   size_gb = [math]::Round($vol.Size/1GB); free_gb = [math]::Round($vol.SizeRemaining/1GB) }
    }
    if ($disks.Count -gt 0) { $s.disks = $disks }
  } catch {}
  # (d) su quali dischi vivono le librerie Steam
  try {
    $steamP = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if ($steamP) {
      $vdf = Join-Path $steamP 'steamapps\libraryfolders.vdf'
      if (Test-Path $vdf) {
        $gl = @()
        foreach ($mt in ([regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"'))) {
          $L = $mt.Groups[1].Value.Substring(0,1).ToUpper()
          if ($L -match '[A-Z]' -and $gl -notcontains $L) { $gl += $L }
        }
        if ($gl.Count -gt 0) { $s.game_drives = $gl }
      }
    }
  } catch {}
  # (e) Core Isolation / Memory Integrity (HVCI): costa ~5-10% FPS
  try {
    $dg = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard -ErrorAction SilentlyContinue
    if ($dg) { $s.hvci_on = (@($dg.SecurityServicesRunning) -contains 2) }
    else {
      $he = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity' -Name Enabled -ErrorAction SilentlyContinue).Enabled
      if ($null -ne $he) { $s.hvci_on = ($he -eq 1) }
    }
  } catch {}
  # (f) eta' driver GPU e BIOS
  try {
    $vdd = (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -eq $s.gpu } | Select-Object -First 1).DriverDate
    if (-not $vdd) { $vdd = $v.DriverDate }
    if ($vdd) { $s.gpu_driver_date = $vdd.ToString('yyyy-MM-dd') }
  } catch {}
  try { if ($bi.ReleaseDate) { $s.bios_date = $bi.ReleaseDate.ToString('yyyy-MM-dd') } } catch {}

  # v0.7.7: storage primario dettagliato (tipo/salute/wear/temp) — cross-check WMI + Storage cmdlets.
  try {
    $ps = Get-PrimaryStorage
    if ($ps -and $ps.Count -gt 0) {
      foreach ($k in $ps.Keys) { $s[$k] = $ps[$k] }
    }
  } catch {}
  $storageSources = 0
  if ($s.storage_type) { $storageSources++ }
  # WMI Win32_DiskDrive come secondo canale
  try {
    $dd = Get-CimInstance Win32_DiskDrive | Where-Object { $_.MediaType -match '(?i)Fixed|SSD|Solid' } | Select-Object -First 1
    if ($dd) { $storageSources++ }
  } catch {}

  # v0.7.7: hw_confidence — quante fonti indipendenti hanno confermato ogni componente.
  # Il frontend usa questi valori per mostrare un badge "2/2 fonti" o "1/2 fonti" (giallo).
  $s.hw_confidence = @{
    cpu     = $cpuSources
    gpu     = $gpuSources
    ram     = $ramSources
    storage = $storageSources
  }

  return $s
}

function Get-Health {
  $h = @{}
  $h.temp_mb = Get-CleanableMb
  $h.startup_count = Get-StartupCount
  $h.power_plan = Get-PowerPlanNormalized
  $gm = (Get-ItemProperty 'HKCU:\Software\Microsoft\GameBar' -Name AllowAutoGameMode).AllowAutoGameMode
  $h.game_mode = ($gm -eq 1)
  $hags = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode).HwSchMode
  $h.gpu_scheduling = ($hags -eq 2)
  $ram = Get-AvgRamPct
  if ($null -ne $ram) { $h.ram_used_pct = $ram }
  $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
  if ($d) { $h.disk_free_pct = [math]::Round($d.FreeSpace / $d.Size * 100) }
  $vc = Get-CimInstance Win32_VideoController | Select-Object -First 1
  $h.gpu = $vc.Name; $h.gpu_driver_version = $vc.DriverVersion
  if ($vc.DriverDate) { $h.gpu_driver_date = $vc.DriverDate.ToString('yyyy-MM-dd') }
  # Real sensor temps (admin): LibreHardwareMonitor covers CPU package + AMD/Intel GPU.
  $lhm = Get-LhmTemps
  $gt = & nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>$null
  if ($gt) { $h.gpu_temp = [int]($gt | Select-Object -First 1).Trim() }
  elseif ($lhm.ContainsKey('gpu_temp')) { $h.gpu_temp = $lhm.gpu_temp }
  # v0.7.7: precision sensors — fan RPM, VRM temp, CPU power, GPU power (LHM fallback), Vcore
  if ($lhm.ContainsKey('fan_rpm_max')) { $h.fan_rpm_max = $lhm.fan_rpm_max }
  if ($lhm.ContainsKey('fan_count')) { $h.fan_count = $lhm.fan_count }
  if ($lhm.ContainsKey('vrm_temp')) { $h.vrm_temp = $lhm.vrm_temp }
  if ($lhm.ContainsKey('cpu_power')) { $h.cpu_power = $lhm.cpu_power }
  if ($lhm.ContainsKey('gpu_power_lhm') -and -not $h.ContainsKey('gpu_power')) { $h.gpu_power = $lhm.gpu_power_lhm }
  if ($lhm.ContainsKey('cpu_vcore')) { $h.cpu_vcore = $lhm.cpu_vcore }
  if ($lhm.ContainsKey('cpu_temp')) {
    $h.cpu_temp = $lhm.cpu_temp
  } else {
    $tzt = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object -First 1
    if ($tzt -and $tzt.CurrentTemperature -gt 2732) {
      $ct = [math]::Round(($tzt.CurrentTemperature - 2732)/10)
      if ($ct -gt 0) { $h.cpu_temp = $ct }
    }
  }
  # v0.7.4d: se la temp CPU e' assente, diagnostica il motivo per suggerire un fix
  # nell'UI web (banner sotto Health Score). Codici: not_admin | vbs_on | blocklist_on |
  # no_sensors | no_lhm | unknown. Il frontend mostra istruzioni actionable per ognuno.
  if (-not $h.ContainsKey('cpu_temp') -or $null -eq $h.cpu_temp) {
    if (-not (Test-Admin)) {
      $h.cpu_temp_reason = 'not_admin'
    } elseif (Test-MemoryIntegrity) {
      $h.cpu_temp_reason = 'vbs_on'
    } elseif (Test-VulnerableDriverBlocklist) {
      $h.cpu_temp_reason = 'blocklist_on'
    } elseif ($lhm._lhm_state -eq 'no_lhm' -or $lhm._lhm_state -eq 'lhm_exception') {
      # LibreHardwareMonitor non riesce a caricare (driver WinRing0 non firmato sul PC).
      # Il fix e' aprire LHM standalone come Admin una volta -> firma il driver.
      $h.cpu_temp_reason = 'no_lhm'
    } elseif ($lhm._lhm_state -eq 'no_cpu_sensors' -or $lhm._lhm_state -eq 'cpu_sensors_out_of_range') {
      # LHM caricato ma non trova sensori CPU (Ryzen Zen4+ con nomi diversi, o BIOS non li espone).
      $h.cpu_temp_reason = 'no_sensors'
    } else {
      $h.cpu_temp_reason = 'unknown'
    }
  }
  return $h
}

function Get-StartupList {
  # v0.8.1: rilevamento PRO multi-fonte: registry Run (con stato reale StartupApproved),
  # cartelle Esecuzione automatica, task pianificati al logon, servizi auto di terze parti.
  # Per ogni voce: publisher (firma digitale), path exe, RAM corrente se in esecuzione.
  $al = New-Object System.Collections.ArrayList
  $approved = @{}
  foreach ($k in @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32')) {
    try {
      $key = Get-Item $k -ErrorAction SilentlyContinue
      if ($key) {
        foreach ($n in $key.GetValueNames()) {
          $v = $key.GetValue($n)
          if ($v -is [byte[]] -and $v.Length -gt 0) { $approved[$n.ToLower()] = (($v[0] % 2) -eq 0) }
        }
      }
    } catch {}
  }
  $procRam = @{}
  try {
    Get-Process -ErrorAction SilentlyContinue | ForEach-Object {
      $n = $_.ProcessName.ToLower()
      if ($procRam.ContainsKey($n)) { $procRam[$n] += $_.WorkingSet64 } else { $procRam[$n] = $_.WorkingSet64 }
    }
  } catch {}
  $sigCache = @{}
  function _exeFromCmd([string]$cmd) {
    if (-not $cmd) { return $null }
    if ($cmd -match '^"([^"]+\.exe)"') { return $Matches[1] }
    if ($cmd -match '^([^\s]+\.exe)') { return $Matches[1] }
    if ($cmd.ToLower().Contains('.exe')) { $i = $cmd.ToLower().IndexOf('.exe'); return $cmd.Substring(0, $i + 4).Trim('"') }
    return $null
  }
  function _publisher([string]$exe) {
    if (-not $exe) { return $null }
    if ($sigCache.ContainsKey($exe)) { return $sigCache[$exe] }
    $pub = $null
    try {
      if (Test-Path $exe) {
        $sig = Get-AuthenticodeSignature $exe -ErrorAction SilentlyContinue
        if ($sig -and $sig.SignerCertificate -and $sig.SignerCertificate.Subject -match 'CN=("[^"]+"|[^,]+)') { $pub = $Matches[1].Trim('"') }
      }
    } catch {}
    $sigCache[$exe] = $pub
    return $pub
  }
  function _add($name, $cmd, $loc, $src, $usr) {
    if (-not $name) { return }
    foreach ($e in $al) { if ($e.name -eq "$name" -and $e.source -eq $src) { return } }
    $exe = _exeFromCmd "$cmd"
    $ram = $null
    if ($exe) {
      $bn = [System.IO.Path]::GetFileNameWithoutExtension($exe).ToLower()
      if ($procRam.ContainsKey($bn)) { $ram = [math]::Round($procRam[$bn] / 1MB) }
    }
    $en = $null
    if ($approved.ContainsKey("$name".ToLower())) { $en = $approved["$name".ToLower()] }
    [void]$al.Add(@{
      name = "$name"; command = "$cmd"; user = "$usr"; location = "$loc"
      source = $src; enabled = $en; publisher = (_publisher $exe); ram_mb = $ram
    })
  }
  foreach ($rk in @(
    @{ p = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'; u = 'SYSTEM' },
    @{ p = 'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run'; u = 'SYSTEM' },
    @{ p = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'; u = "$env:USERNAME" })) {
    try {
      $key = Get-Item $rk.p -ErrorAction SilentlyContinue
      if ($key) { foreach ($n in $key.GetValueNames()) { _add $n ($key.GetValue($n)) $rk.p 'registry' $rk.u } }
    } catch {}
  }
  # Risoluzione .lnk senza oggetti COM shell (pattern che triggera l'euristica
  # anti-persistenza di Defender): semplice lettura bytes + regex sul path.
  function _lnkTarget([string]$lnk) {
    try {
      $bytes = [System.IO.File]::ReadAllBytes($lnk)
      $uni = [System.Text.Encoding]::Unicode.GetString($bytes)
      if ($uni -match '([A-Za-z]:\\[^\x00-\x1F"<>|?*]+?\.exe)') { return $Matches[1] }
      $asc = [System.Text.Encoding]::ASCII.GetString($bytes)
      if ($asc -match '([A-Za-z]:\\[^\x00-\x1F"<>|?*]+?\.exe)') { return $Matches[1] }
    } catch {}
    return $null
  }
  foreach ($fd in @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('CommonStartup'))) {
    if (-not $fd -or -not (Test-Path $fd)) { continue }
    Get-ChildItem $fd -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'desktop.ini' } | Select-Object -First 15 | ForEach-Object {
      $target = $_.FullName
      if ($_.Extension -eq '.lnk') { $t2 = _lnkTarget $_.FullName; if ($t2) { $target = $t2 } }
      _add $_.BaseName $target $fd 'folder' "$env:USERNAME"
      if ($al.Count -gt 0) {
        # StartupApproved\StartupFolder usa il nome file CON estensione (es. app.lnk)
        $k1 = $_.Name.ToLower(); $k2 = $_.BaseName.ToLower()
        if ($approved.ContainsKey($k1)) { $al[$al.Count - 1].enabled = $approved[$k1] }
        elseif ($approved.ContainsKey($k2)) { $al[$al.Count - 1].enabled = $approved[$k2] }
      }
    }
  }
  try {
    Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
      $_.TaskPath -notlike '\Microsoft*' -and $_.State -ne 'Disabled' -and
      ($_.Triggers | Where-Object { $_.CimClass.CimClassName -match 'Logon|Boot' })
    } | Select-Object -First 15 | ForEach-Object {
      $act = ''
      try { $act = ($_.Actions | Select-Object -First 1).Execute } catch {}
      _add $_.TaskName $act $_.TaskPath 'task' "$env:USERNAME"
      if ($al.Count -gt 0) { $al[$al.Count - 1].enabled = $true }
    }
  } catch {}
  try {
    Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | Where-Object {
      $_.StartMode -eq 'Auto' -and $_.PathName -and $_.PathName -notmatch '(?i)\\Windows\\'
    } | Select-Object -First 15 | ForEach-Object {
      _add $_.DisplayName $_.PathName 'services' 'service' 'SYSTEM'
      if ($al.Count -gt 0) { $al[$al.Count - 1].enabled = ($_.State -eq 'Running') }
    }
  } catch {}
  if ($al.Count -eq 0) {
    try {
      Get-CimInstance Win32_StartupCommand -ErrorAction Stop | Select-Object -First 40 | ForEach-Object {
        _add $_.Name $_.Command $_.Location 'registry' $_.User
      }
    } catch {}
  }
  if ($al.Count -gt 60) {
    $trim = New-Object System.Collections.ArrayList
    foreach ($e in ($al | Select-Object -First 60)) { [void]$trim.Add($e) }
    $al = $trim
  }
  return ,$al
}

function Get-ServicesAudit {
  # Audit servizi per l'analisi 'quali disattivare': stato, tipo avvio, dipendenze
  # reali (quanti servizi dipendono da questo), RAM (solo processi dedicati, non
  # svchost condivisi) e flag Microsoft (path dentro \Windows\).
  $al = New-Object System.Collections.ArrayList
  try {
    $procs = @{}
    Get-Process -ErrorAction SilentlyContinue | ForEach-Object { $procs[[int]$_.Id] = [math]::Round($_.WorkingSet64 / 1MB) }
    $deps = @{}
    Get-Service -ErrorAction SilentlyContinue | ForEach-Object {
      foreach ($d in $_.ServicesDependedOn) {
        $dn = $d.Name.ToLower()
        if ($deps.ContainsKey($dn)) { $deps[$dn]++ } else { $deps[$dn] = 1 }
      }
    }
    Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | Where-Object { $_.StartMode -in @('Auto', 'Manual') } | Select-Object -First 200 | ForEach-Object {
      $shared = ($_.PathName -match '(?i)svchost\.exe\s+-k')
      $ram = $null
      if (-not $shared -and $_.ProcessId -gt 0 -and $procs.ContainsKey([int]$_.ProcessId)) { $ram = $procs[[int]$_.ProcessId] }
      $dn = "$($_.Name)".ToLower()
      [void]$al.Add(@{
        name = "$($_.Name)"; display = "$($_.DisplayName)"; state = "$($_.State)"
        start_mode = "$($_.StartMode)"; shared = $shared; ram_mb = $ram
        dependents = $(if ($deps.ContainsKey($dn)) { [int]$deps[$dn] } else { 0 })
        ms = ([bool]($_.PathName -match '(?i)\\Windows\\'))
      })
    }
  } catch {}
  return ,$al
}

# ---------------- Benchmark ----------------
function Get-CpuBusyPct {
  # Contatore di prestazione: Win32_Processor.LoadPercentage e' aggiornato di
  # rado e mediato su una finestra che non controlliamo.
  try {
    $p = Get-CimInstance -ClassName Win32_PerfFormattedData_PerfOS_Processor `
         -Filter "Name='_Total'" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { return [double]$p.PercentProcessorTime }
  } catch {}
  try { return [double](Get-CimInstance Win32_Processor | Select-Object -First 1).LoadPercentage } catch {}
  return $null
}

function Get-DpcTimePct {
  # Tempo speso nelle DPC: questa e' una misura di DPC, a differenza
  # dell'oversleep di Start-Sleep, che misura la granularita' del timer.
  #
  # Contatori RAW e non formatted: la classe formatted espone la percentuale
  # come intero, e un valore tipico (0.3%) verrebbe restituito come 0. Dai raw
  # si calcola la frazione a mano, con la precisione che serve per accorgersi
  # che un driver e' passato dallo 0.2% al 2%.
  try {
    $a = @(Get-CimInstance -ClassName Win32_PerfRawData_PerfOS_Processor -ErrorAction Stop |
           Where-Object { $_.Name -ne '_Total' })
    if ($a.Count -eq 0) { return $null }
    Start-Sleep -Milliseconds 1200
    $b = @(Get-CimInstance -ClassName Win32_PerfRawData_PerfOS_Processor -ErrorAction Stop |
           Where-Object { $_.Name -ne '_Total' })
    $prev = @{}
    foreach ($x in $a) { $prev[$x.Name] = $x }
    $dt = 0.0; $dpc = 0.0; $isr = 0.0; $cnt = 0.0; $queued = 0.0
    foreach ($x in $b) {
      $p = $prev[$x.Name]
      if (-not $p) { continue }
      $d = [double]($x.Timestamp_Sys100NS - $p.Timestamp_Sys100NS)
      if ($d -le 0) { continue }
      $dt = $d
      $dpc += [double]($x.PercentDPCTime - $p.PercentDPCTime)
      $isr += [double]($x.PercentInterruptTime - $p.PercentInterruptTime)
      $queued += [double]($x.DPCsQueuedPersec - $p.DPCsQueuedPersec)
      $cnt += 1.0
    }
    if ($dt -le 0 -or $cnt -le 0) { return $null }
    $secs = $dt / 1e7
    return @{
      pct = [math]::Round(100.0 * $dpc / ($dt * $cnt), 3)
      isr_pct = [math]::Round(100.0 * $isr / ($dt * $cnt), 3)
      rate = [int][math]::Round($queued / [math]::Max($secs, 0.001))
    }
  } catch {}
  return $null
}

function Get-BenchDriveRoot {
  # Il disco che conta per un giocatore e' quello dove stanno i giochi, non
  # necessariamente quello di sistema dove finisce %TEMP%.
  try {
    $steamP = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if ($steamP) {
      $vdf = Join-Path $steamP 'steamapps\libraryfolders.vdf'
      if (Test-Path $vdf) {
        $m = [regex]::Match((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')
        if ($m.Success) {
          $root = [System.IO.Path]::GetPathRoot(($m.Groups[1].Value -replace '\\\\', '\'))
          if ($root -and (Test-Path $root)) { return $root }
        }
      }
      $root = [System.IO.Path]::GetPathRoot($steamP)
      if ($root -and (Test-Path $root)) { return $root }
    }
  } catch {}
  return "$env:SystemDrive\"
}

function Run-Benchmark {
  $r = @{}
  $r.bench_engine = 'powershell'
  $r.ps_version = "$($PSVersionTable.PSVersion.Major).$($PSVersionTable.PSVersion.Minor)"
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  # Carico di fondo PRIMA di misurare: un antivirus a pieno regime non rende la
  # misura rumorosa, la rende di un'altra macchina.
  $bg = Get-CpuBusyPct
  if ($null -ne $bg) { $r.bg_load_pct = [math]::Round($bg, 1) }
  # Priorita' alta per la durata del benchmark: senza, il risultato dipende da
  # come lo scheduler ha diviso la CPU con il resto del sistema.
  $proc = [System.Diagnostics.Process]::GetCurrentProcess()
  $oldPrio = $proc.PriorityClass
  try { $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High } catch {}
  try {
    # CPU e RAM: 1 giro di riscaldamento scartato + 5 ripetizioni -> mediana e CV.
    # Il primo giro paga la compilazione del ciclo e la cache fredda: tenerlo
    # dentro significava misurare l'avvio, non la macchina.
    $cpuRuns = New-Object System.Collections.ArrayList
    $ramRuns = New-Object System.Collections.ArrayList
    $size = 64MB
    $buf = New-Object byte[] $size; $dst = New-Object byte[] $size
    $reps = 5
    for ($rep = -1; $rep -lt $reps; $rep++) {
      $acc = 0.0
      $sw.Restart(); for ($i = 0; $i -lt 3000000; $i++) { $acc += [math]::Sqrt($i) }; $sw.Stop()
      $cpuVal = [double](3000000 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001) / 1000)
      $sw.Restart(); for ($i = 0; $i -lt 5; $i++) { [Array]::Copy($buf, $dst, $size) }; $sw.Stop()
      $ramVal = [double]((5 * $size / 1MB) / [math]::Max($sw.Elapsed.TotalSeconds, 0.001))
      if ($rep -lt 0) { continue }
      [void]$cpuRuns.Add($cpuVal)
      [void]$ramRuns.Add($ramVal)
    }
    $cpuS = @($cpuRuns | Sort-Object); $ramS = @($ramRuns | Sort-Object)
    $mid = [int][math]::Floor($reps / 2)
    $r.cpu_score = [int][math]::Round($cpuS[$mid])
    $r.ram_mbps = [int][math]::Round($ramS[$mid])
    $cpuAvg = ($cpuRuns | Measure-Object -Average).Average
    $ramAvg = ($ramRuns | Measure-Object -Average).Average
    $cv1 = 0.0; foreach ($x in $cpuRuns) { $cv1 += [math]::Pow($x - $cpuAvg, 2) }
    $cv2 = 0.0; foreach ($x in $ramRuns) { $cv2 += [math]::Pow($x - $ramAvg, 2) }
    # Deviazione campionaria (n-1): con n-1 al denominatore il CV non e'
    # sistematicamente sottostimato come con n.
    $r.cpu_cv_pct = [math]::Round([math]::Sqrt($cv1 / ($reps - 1)) / [math]::Max($cpuAvg, 1) * 100, 1)
    $r.ram_cv_pct = [math]::Round([math]::Sqrt($cv2 / ($reps - 1)) / [math]::Max($ramAvg, 1) * 100, 1)
    $r.bench_runs = $reps
    $r.cv_pct = [math]::Max($r.cpu_cv_pct, $r.ram_cv_pct)
    $r.reliable = ($r.cv_pct -le 10 -and ($null -eq $bg -or $bg -le 25))
    if ($null -ne $bg -and $bg -gt 25) { $r.unreliable_reason = "carico di fondo al $([math]::Round($bg))% durante la misura" }
    elseif ($r.cv_pct -gt 10) { $r.unreliable_reason = "ripetizioni troppo diverse fra loro (CV $($r.cv_pct)%)" }
  } finally {
    try { $proc.PriorityClass = $oldPrio } catch {}
  }
  # Disco: scrittura sequenziale REALE (WriteThrough bypassa la cache, 256MB)
  $benchRoot = Get-BenchDriveRoot
  try {
    $probe = Join-Path $benchRoot ('ff_probe_' + [guid]::NewGuid().ToString('N') + '.tmp')
    [System.IO.File]::WriteAllBytes($probe, (New-Object byte[] 16))
    Remove-Item $probe -Force -ErrorAction SilentlyContinue
  } catch {
    # Radice non scrivibile (permessi, disco di rete): si torna a %TEMP%, ma
    # dichiarandolo, cosi' chi legge sa a quale disco si riferisce il numero.
    $benchRoot = "$env:TEMP"
    $r.disk_drive_fallback = $true
  }
  $r.disk_drive = "$benchRoot"
  $tmp = Join-Path $benchRoot 'forgefps_bench.bin'
  try {
    $chunk = New-Object byte[] (8MB); (New-Object Random).NextBytes($chunk)
    $fs = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 1MB, [System.IO.FileOptions]::WriteThrough)
    $sw.Restart(); for ($i = 0; $i -lt 32; $i++) { $fs.Write($chunk, 0, $chunk.Length) }; $fs.Flush($true); $sw.Stop(); $fs.Close()
    $r.disk_write_mbps = [int]([math]::Round(256 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
    $sw.Restart(); $null = [System.IO.File]::ReadAllBytes($tmp); $sw.Stop()
    $r.disk_read_mbps = [int]([math]::Round(256 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
    $b4 = New-Object byte[] 4096; $rnd = New-Object Random
    $fs2 = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4096, [System.IO.FileOptions]::WriteThrough)
    # 1000 operazioni invece di 200: con duecento campioni il numero ballava di
    # decine di punti percentuali fra una misura e l'altra.
    $ops = 1000
    $sw.Restart()
    for ($i = 0; $i -lt $ops; $i++) { $fs2.Position = 4096 * $rnd.Next(0, 65536); $fs2.Write($b4, 0, 4096) }
    $fs2.Flush($true); $sw.Stop(); $fs2.Close()
    $r.iops_4k = [int]([math]::Round($ops / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
    # Il nome dichiara la profondita' di coda: su un NVMe l'IOPS a QD1 e' un
    # decimo di quello a QD32, e confrontarli come se fossero la stessa cosa
    # e' il modo piu' rapido per credere che un SSD sia rotto.
    $r.iops_4k_qd1 = $r.iops_4k
    $r.disk_note = 'QD1, file da 256MB: puo cadere nella cache SLC di un SSD'
  } catch { if (-not $r.ContainsKey('disk_write_mbps')) { $r.disk_write_mbps = 0 }; if (-not $r.ContainsKey('disk_read_mbps')) { $r.disk_read_mbps = 0 }; $r.iops_4k = 0 }
  Remove-Item $tmp -ErrorAction SilentlyContinue
  # Granularita' del timer di sistema: oversleep p95 su 150 sleep da 1ms.
  # NON e' la latenza DPC (che si misura sotto): questo valore dipende dalla
  # risoluzione del timer, ed e' influenzato dal tweak 'timer' che il Lab
  # applica — chiamarlo dpc_ms faceva sembrare che il tweak curasse le DPC.
  $lat = New-Object System.Collections.Generic.List[double]
  $sw2 = [System.Diagnostics.Stopwatch]::StartNew()
  $prev = $sw2.Elapsed.TotalMilliseconds
  for ($i = 0; $i -lt 150; $i++) {
    Start-Sleep -Milliseconds 1
    $nowMs = $sw2.Elapsed.TotalMilliseconds
    $lat.Add([math]::Max(0, $nowMs - $prev - 1)); $prev = $nowMs
  }
  $sorted = @($lat | Sort-Object)
  $r.timer_jitter_ms = [math]::Round($sorted[[int][math]::Floor($sorted.Count * 0.95)], 1)
  $r.dpc_ms = $r.timer_jitter_ms   # chiave storica: i grafici esistenti la leggono
  $dpc = Get-DpcTimePct
  if ($dpc) { $r.dpc_time_pct = $dpc.pct; $r.dpc_rate = $dpc.rate }
  # Rete: 20 campioni, perdita, p95 e jitter come media delle differenze
  # consecutive (RFC 3550). La deviazione standard usata prima misura la
  # dispersione attorno alla media, non lo sfarfallio fra un pacchetto e il
  # successivo, che e' quello che si sente giocando.
  try {
    $png = New-Object System.Net.NetworkInformation.Ping
    $rtts = New-Object System.Collections.Generic.List[double]
    $sent = 20
    for ($i = 0; $i -lt $sent; $i++) {
      $res = $png.Send('1.1.1.1', 2000)
      if ($res.Status -eq 'Success') { $rtts.Add([double]$res.RoundtripTime) }
      Start-Sleep -Milliseconds 120
    }
    if ($rtts.Count -gt 0) {
      $avg = ($rtts | Measure-Object -Average).Average
      $r.ping_ms = [int]([math]::Round($avg))
      $ps = @($rtts | Sort-Object)
      $r.ping_p95_ms = [int]([math]::Round($ps[[math]::Min($ps.Count - 1, [int][math]::Floor($ps.Count * 0.95))]))
      $r.ping_loss_pct = [math]::Round(100.0 * ($sent - $rtts.Count) / $sent, 1)
      $r.ping_samples = $rtts.Count
      $var = 0.0; foreach ($v in $rtts) { $var += [math]::Pow($v - $avg, 2) }
      $r.jitter_sd_ms = [math]::Round([math]::Sqrt($var / $rtts.Count), 1)
      if ($rtts.Count -ge 2) {
        $d = 0.0
        for ($i = 1; $i -lt $rtts.Count; $i++) { $d += [math]::Abs($rtts[$i] - $rtts[$i - 1]) }
        $r.jitter_ms = [math]::Round($d / ($rtts.Count - 1), 1)
      } else { $r.jitter_ms = 0 }
    } else { $r.ping_ms = 0; $r.jitter_ms = 0; $r.ping_loss_pct = 100.0 }
  } catch { $r.ping_ms = 0; $r.jitter_ms = 0 }
  # Tempo di avvio Windows (event log Diagnostics-Performance 100)
  try {
    $ev = Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-Diagnostics-Performance/Operational'; Id = 100 } -MaxEvents 1 -ErrorAction SilentlyContinue
    if ($ev) {
      $x = [xml]$ev.ToXml()
      $bt = ($x.Event.EventData.Data | Where-Object { $_.Name -eq 'BootTime' }).'#text'
      if ($bt) { $r.boot_s = [math]::Round([double]$bt / 1000, 1) }
    }
  } catch {}
  $o = Get-CimInstance Win32_OperatingSystem
  $r.free_ram_pct = [int]([math]::Round($o.FreePhysicalMemory / $o.TotalVisibleMemorySize * 100))
  # SCORE 0-100 pesato (confrontabile nel tempo)
  $cpuN = [math]::Min(100, $r.cpu_score / 100.0)
  $ramN = [math]::Min(100, $r.ram_mbps / 200.0)
  $dwN = [math]::Min(100, $r.disk_write_mbps / 20.0)
  $drN = [math]::Min(100, $r.disk_read_mbps / 30.0)
  $ioN = [math]::Min(100, $r.iops_4k / 50.0)
  # Quando la misura vera delle DPC c'e', il punteggio usa quella; l'oversleep
  # del timer resta come ripiego sulle macchine dove il contatore non risponde.
  if ($r.ContainsKey('dpc_time_pct')) { $dpcN = [math]::Max(0, 100 - $r.dpc_time_pct * 25) }
  else { $dpcN = [math]::Max(0, 100 - $r.timer_jitter_ms * 20) }
  $pingN = [math]::Max(0, 100 - $r.ping_ms)
  $jitN = [math]::Max(0, 100 - $r.jitter_ms * 10)
  $r.score = [int]([math]::Round($cpuN * 0.20 + $ramN * 0.10 + $dwN * 0.15 + $drN * 0.10 + $ioN * 0.10 + $dpcN * 0.15 + $pingN * 0.15 + $jitN * 0.05))
  # Il termine DPC del punteggio ha cambiato sorgente: due score con versione
  # diversa non vanno messi sulla stessa linea di un grafico come se fossero
  # la stessa misura.
  $r.score_version = 2
  $r.overall = [int]([math]::Round($r.cpu_score + $r.ram_mbps/50.0 + $r.disk_write_mbps/50.0 + $r.disk_read_mbps/50.0 + [math]::Max(0, 120 - $r.ping_ms) + $r.free_ram_pct))
  return $r
}
function Show-Bench($r, $title) {
  Say "`n   [$title]" 'Cyan'
  Say ("   CPU {0} | RAM {1} MB/s | Disco W/R {2}/{3} MB/s | 4K {4} IOPS (QD1, {5})" -f $r.cpu_score, $r.ram_mbps, $r.disk_write_mbps, $r.disk_read_mbps, $r.iops_4k, $r.disk_drive) 'Yellow'
  $dpcTxt = if ($r.ContainsKey('dpc_time_pct')) { "DPC {0}% del tempo" -f $r.dpc_time_pct } else { "DPC non misurabile" }
  $lossTxt = if ($r.ContainsKey('ping_loss_pct') -and $r.ping_loss_pct -gt 0) { ", perdita $($r.ping_loss_pct)%" } else { '' }
  Say ("   Jitter timer {0} ms | {1} | Ping {2} ms (jitter {3} ms{4}){5} | PERFORMANCE SCORE {6}/100" -f $r.timer_jitter_ms, $dpcTxt, $r.ping_ms, $r.jitter_ms, $lossTxt, $(if($r.ContainsKey('boot_s')){" | Avvio $($r.boot_s)s"}else{''}), $r.score) 'Yellow'
  if (-not $r.reliable -and $r.ContainsKey('unreliable_reason')) {
    Say-Warn ("   Misura poco affidabile: {0}. Chiudi le applicazioni pesanti e ripeti." -f $r.unreliable_reason)
  }
  Say-Info '   Il Performance Score misura la velocita del PC ora. Health Score globale su forgefps.dev -> Il mio PC.'
}

# ---------------- Full Benchmark v2 (multi-thread CPU + RAM hierarchy + disk multi-QD + thermal trace) ----------------
# Durata: ~2-4 minuti. Molto piu' preciso del Run-Benchmark quick (5-8s).
# I risultati sono qualitativamente diversi:
#   - cpu_mt_score: MULTI-THREAD (usa tutti i core -> differenzia i5 vs i9)
#   - cpu_sustained_ratio: rapporto CPU sustained/burst (basso = thermal throttling)
#   - ram_bw_l3 / ram_bw_dram: bandwidth memoria a dimensioni diverse
#   - disk_qd8_seq / disk_4k_qd32: pattern realistici moderni
#   - thermal_trace: array di temp CPU/GPU campionati durante il test
function Run-FullBenchmark {
  $out = @{
    version = 2
    started_at = (Get-Date).ToString('o')
  }
  $trace = New-Object System.Collections.Generic.List[hashtable]
  $traceStopFlag = [ref]$false

  # Job in parallelo: thermal sampling ogni 1s per tutta la durata del benchmark.
  # Salva ts (secondi dall'inizio), cpu_temp, gpu_temp, cpu_clock, gpu_clock.
  # GPU: un solo processo nvidia-smi che scrive su file per tutta la durata.
  # Prima veniva lanciato un nvidia-smi al secondo dentro il job: due-trecento
  # avvii di processo nel mezzo di un benchmark che misura proprio quanto la
  # macchina e' reattiva.
  $nvFile = Join-Path $env:TEMP ('ff_bench_nv_' + [guid]::NewGuid().ToString('N') + '.csv')
  $nvProc = $null
  try {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
      $nvProc = Start-Process -FilePath 'nvidia-smi' -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue `
        -ArgumentList ('--query-gpu=temperature.gpu,clocks.gr --format=csv,noheader,nounits -l 1 -f "' + $nvFile + '"')
    }
  } catch {}
  $traceJob = Start-Job -ScriptBlock {
    param($StartTs)
    $samples = New-Object System.Collections.Generic.List[hashtable]
    while ($true) {
      $elapsed = [int]((Get-Date) - $StartTs).TotalSeconds
      $cpuTemp = 0
      try {
        # LibreHardwareMonitor e' gia' in memoria nel processo principale ma non
        # e' riusabile dentro un job. Qui resta MSAcpi_ThermalZoneTemperature,
        # che su molte schede madri riporta la temperatura di una zona ACPI
        # generica e non quella del package: per questo il campione porta con se'
        # la sorgente, invece di far credere che sia una lettura del sensore CPU.
        $t = Get-CimInstance -Namespace 'root/wmi' -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($t) { $cpuTemp = [int](($t.CurrentTemperature - 2732) / 10) }
      } catch {}
      $samples.Add(@{ ts = $elapsed; cpu_temp = $cpuTemp; cpu_temp_source = 'acpi_thermal_zone'; gpu_temp = 0; cpu_clock = 0 })
      Start-Sleep -Seconds 1
    }
  } -ArgumentList (Get-Date)

  try {
    # === TEST 1 — CPU multi-thread burst (30s) + sustained (30s) ===
    Say "`n[STEP 1/4] CPU multi-thread (60s: 30s burst + 30s sustained)..." 'Cyan'
    $ncpu = [Environment]::ProcessorCount
    Say ("         Uso $ncpu thread logici in parallelo.") 'DarkGray'

    $runspace = [runspacefactory]::CreateRunspacePool(1, $ncpu)
    $runspace.Open()
    $mkWorker = {
      param($DurationSec)
      $sw = [System.Diagnostics.Stopwatch]::StartNew()
      $ops = 0
      $acc = 0.0
      while ($sw.Elapsed.TotalSeconds -lt $DurationSec) {
        for ($i = 0; $i -lt 100000; $i++) { $acc += [math]::Sqrt($i + 1) + [math]::Sin($i * 0.001) }
        $ops += 100000
      }
      return $ops
    }

    # Burst
    $burstJobs = @()
    for ($i = 0; $i -lt $ncpu; $i++) {
      $ps = [powershell]::Create().AddScript($mkWorker).AddArgument(30)
      $ps.RunspacePool = $runspace
      $burstJobs += @{ Ps = $ps; Handle = $ps.BeginInvoke() }
    }
    $burstOps = 0
    foreach ($j in $burstJobs) { $burstOps += ($j.Ps.EndInvoke($j.Handle))[0]; $j.Ps.Dispose() }
    $out.cpu_mt_burst_mops = [int]([math]::Round($burstOps / 30 / 1e6))
    Say ("         Burst: {0} Mops/s" -f $out.cpu_mt_burst_mops) 'DarkGreen'

    # Sustained (subito dopo, senza pausa: simula gaming session lunga)
    $sustJobs = @()
    for ($i = 0; $i -lt $ncpu; $i++) {
      $ps = [powershell]::Create().AddScript($mkWorker).AddArgument(30)
      $ps.RunspacePool = $runspace
      $sustJobs += @{ Ps = $ps; Handle = $ps.BeginInvoke() }
    }
    $sustOps = 0
    foreach ($j in $sustJobs) { $sustOps += ($j.Ps.EndInvoke($j.Handle))[0]; $j.Ps.Dispose() }
    $out.cpu_mt_sustained_mops = [int]([math]::Round($sustOps / 30 / 1e6))
    $out.cpu_sustained_ratio = if ($out.cpu_mt_burst_mops -gt 0) { [math]::Round($out.cpu_mt_sustained_mops / $out.cpu_mt_burst_mops, 3) } else { 0 }
    Say ("         Sustained: {0} Mops/s (ratio {1} vs burst)" -f $out.cpu_mt_sustained_mops, $out.cpu_sustained_ratio) 'DarkGreen'
    if ($out.cpu_sustained_ratio -lt 0.85) {
      Say-Warn "         Thermal throttling rilevato: performance CPU scesa >15% dopo 30s. Cooler insufficiente?"
      $out.cpu_thermal_throttle = $true
    } else {
      $out.cpu_thermal_throttle = $false
    }
    $runspace.Close(); $runspace.Dispose()

    # === TEST 2 — RAM hierarchy (10s: 1MB / 32MB / 512MB) ===
    Say "`n[STEP 2/4] RAM hierarchy (L2/L3/DRAM bandwidth)..." 'Cyan'
    foreach ($sz in @(@{name='l2'; bytes=1MB}, @{name='l3'; bytes=32MB}, @{name='dram'; bytes=512MB})) {
      try {
        $b = New-Object byte[] $sz.bytes
        $d = New-Object byte[] $sz.bytes
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $iters = if ($sz.bytes -lt 32MB) { 500 } elseif ($sz.bytes -lt 128MB) { 30 } else { 5 }
        for ($i = 0; $i -lt $iters; $i++) { [Array]::Copy($b, $d, $sz.bytes) }
        $sw.Stop()
        $mbps = [int]([math]::Round(($iters * $sz.bytes / 1MB) / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
        $out."ram_bw_$($sz.name)_mbps" = $mbps
        Say ("         $($sz.name.ToUpper()) ($([math]::Round($sz.bytes/1MB))MB): $mbps MB/s") 'DarkGray'
      } catch { $out."ram_bw_$($sz.name)_mbps" = 0 }
    }

    # === TEST 3 — Disk multi-QD (Seq QD1/QD8 + Rand 4K QD1/QD32 + Mixed 70/30) ===
    Say "`n[STEP 3/4] Disk multi-queue (Seq QD1/QD8, Rand 4K QD1/QD32, Mixed 70/30)..." 'Cyan'
    $tmp = Join-Path $env:TEMP 'forgefps_fullbench.bin'
    try {
      $chunk = New-Object byte[] (128KB); (New-Object Random).NextBytes($chunk)
      # Seq QD1 128KB (32MB)
      $fs = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4KB, [System.IO.FileOptions]::WriteThrough)
      $sw = [System.Diagnostics.Stopwatch]::StartNew()
      for ($i = 0; $i -lt 256; $i++) { $fs.Write($chunk, 0, $chunk.Length) }
      $fs.Flush($true); $sw.Stop(); $fs.Close()
      $out.disk_seq_qd1_mbps = [int]([math]::Round(32 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
      Say ("         Seq QD1 128KB: {0} MB/s" -f $out.disk_seq_qd1_mbps) 'DarkGray'

      # Rand 4K QD1 (300 ops)
      $b4 = New-Object byte[] 4096; $rnd = New-Object Random
      $fs2 = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4096, [System.IO.FileOptions]::WriteThrough)
      $sw.Restart()
      for ($i = 0; $i -lt 300; $i++) { $fs2.Position = 4096 * $rnd.Next(0, 4096); $fs2.Write($b4, 0, 4096) }
      $fs2.Flush($true); $sw.Stop(); $fs2.Close()
      $out.disk_rand_4k_qd1_iops = [int]([math]::Round(300 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
      Say ("         Rand 4K QD1: {0} IOPS" -f $out.disk_rand_4k_qd1_iops) 'DarkGray'

      # Rand 4K QD32 async (600 ops, tasks paralleli)
      $sw.Restart()
      $tasks = @()
      $fs3 = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4096, [System.IO.FileOptions]::WriteThrough -bor [System.IO.FileOptions]::Asynchronous)
      for ($i = 0; $i -lt 600; $i++) {
        $fs3.Position = 4096 * $rnd.Next(0, 4096)
        $tasks += $fs3.WriteAsync($b4, 0, 4096)
      }
      [System.Threading.Tasks.Task]::WaitAll($tasks); $sw.Stop(); $fs3.Close()
      $out.disk_rand_4k_qd32_iops = [int]([math]::Round(600 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
      Say ("         Rand 4K QD32: {0} IOPS" -f $out.disk_rand_4k_qd32_iops) 'DarkGray'
    } catch {
      Say-Warn ("         Disk test parzialmente fallito: {0}" -f $_.Exception.Message)
    }
    Remove-Item $tmp -ErrorAction SilentlyContinue

    # === TEST 4 — Rete estesa (30 ping su 3 endpoint) ===
    Say "`n[STEP 4/4] Rete estesa (30 ping su 3 endpoint)..." 'Cyan'
    $out.network = @{}
    foreach ($host in @('1.1.1.1', '8.8.8.8', 'forgefps.dev')) {
      try {
        $png = New-Object System.Net.NetworkInformation.Ping
        $rtts = New-Object System.Collections.Generic.List[double]
        $lost = 0
        for ($i = 0; $i -lt 30; $i++) {
          $res = $png.Send($host, 1500)
          if ($res -and $res.Status -eq 'Success') { $rtts.Add([double]$res.RoundtripTime) } else { $lost++ }
        }
        if ($rtts.Count -gt 0) {
          $sorted = @($rtts | Sort-Object)
          $avg = ($rtts | Measure-Object -Average).Average
          $out.network[$host] = @{
            avg = [int]([math]::Round($avg))
            min = [int]$sorted[0]
            max = [int]$sorted[-1]
            p95 = [int]$sorted[[int][math]::Floor($sorted.Count * 0.95)]
            loss_pct = [int]([math]::Round($lost * 100.0 / 30))
          }
          Say ("         $host : avg $($out.network[$host].avg)ms | p95 $($out.network[$host].p95)ms | loss $($out.network[$host].loss_pct)%") 'DarkGray'
        }
      } catch {}
    }
  } finally {
    # Stop thermal trace + fold results
    try {
      Stop-Job -Job $traceJob -ErrorAction SilentlyContinue
      $samples = @(Receive-Job -Job $traceJob -ErrorAction SilentlyContinue)
      Remove-Job -Job $traceJob -Force -ErrorAction SilentlyContinue
      if ($nvProc) {
        try { Stop-Process -Id $nvProc.Id -Force -ErrorAction SilentlyContinue } catch {}
        Start-Sleep -Milliseconds 200
        # Le righe di nvidia-smi sono una al secondo come i campioni del job:
        # si allineano per indice.
        $nvLines = @(Get-Content $nvFile -ErrorAction SilentlyContinue)
        for ($i = 0; $i -lt [math]::Min($nvLines.Count, $samples.Count); $i++) {
          $parts = "$($nvLines[$i])".Split(',')
          if ($parts.Count -lt 2) { continue }
          try {
            $samples[$i].gpu_temp = [int]$parts[0].Trim()
            $samples[$i].gpu_clock = [int]$parts[1].Trim()
          } catch {}
        }
        try { Remove-Item $nvFile -Force -ErrorAction SilentlyContinue } catch {}
      }
      if ($samples) {
        $out.thermal_trace = @($samples)
        $cpuT = @($samples | Where-Object { $_.cpu_temp -gt 0 } | ForEach-Object { $_.cpu_temp })
        $gpuT = @($samples | Where-Object { $_.gpu_temp -gt 0 } | ForEach-Object { $_.gpu_temp })
        if ($cpuT.Count -gt 0) { $out.cpu_temp_max = ($cpuT | Measure-Object -Maximum).Maximum; $out.cpu_temp_avg = [math]::Round(($cpuT | Measure-Object -Average).Average, 1) }
        if ($gpuT.Count -gt 0) { $out.gpu_temp_max = ($gpuT | Measure-Object -Maximum).Maximum; $out.gpu_temp_avg = [math]::Round(($gpuT | Measure-Object -Average).Average, 1) }
      }
    } catch {}
  }

  $out.ended_at = (Get-Date).ToString('o')
  $out.duration_s = [int]((Get-Date) - [datetime]$out.started_at).TotalSeconds
  return $out
}

# ---------------- Reporting ----------------
function Send-AgentDiag($event, $detail) {
  # Eventi diagnostici, non telemetria d'uso: servono a decidere con i dati
  # invece che a intuito. Silenziosa per costruzione — una diagnostica che
  # interrompe l'utente e' peggio del problema che sta misurando.
  try {
    $body = @{ event = $event }
    if ($detail) { $body.detail = $detail }
    Invoke-RestMethod -Uri "$BACKEND/api/agent/diag" -Method Post -ContentType 'application/json' `
      -Headers @{ 'X-Agent-Token' = $TOKEN } -Body ($body | ConvertTo-Json -Depth 4 -Compress) -TimeoutSec 8 | Out-Null
  } catch {}
}
function Send-Data($specs, $health, $startup) {
  $body = @{ data = $specs; health = $health; startup = $startup }
  try { $svc = Get-ServicesAudit; if ($svc -and $svc.Count -gt 0) { $body.services_audit = $svc } } catch {}
  $body = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 6 -Compress))
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body | Out-Null } catch {}
}
function Send-Benchmark($rec) {
  $body = [System.Text.Encoding]::UTF8.GetBytes((@{ benchmark = $rec } | ConvertTo-Json -Depth 6 -Compress))
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body | Out-Null } catch {}
}
function Get-Games {
  $games = New-Object System.Collections.Generic.List[string]
  try {
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if (-not $steam) { $steam = 'C:\Program Files (x86)\Steam' }
    $libs = @(Join-Path $steam 'steamapps')
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path $vdf) {
      foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
        $libs += (Join-Path ($m.Groups[1].Value -replace '\\\\', '\') 'steamapps')
      }
    }
    foreach ($lib in ($libs | Select-Object -Unique)) {
      if (Test-Path $lib) {
        foreach ($acf in (Get-ChildItem $lib -Filter 'appmanifest_*.acf' -ErrorAction SilentlyContinue)) {
          $nm = [regex]::Match((Get-Content $acf.FullName -Raw), '"name"\s+"([^"]+)"').Groups[1].Value
          if ($nm) { $games.Add($nm) }
        }
      }
    }
  } catch {}
  try {
    $ep = Join-Path $env:ProgramData 'Epic\EpicGamesLauncher\Data\Manifests'
    if (Test-Path $ep) {
      foreach ($it in (Get-ChildItem $ep -Filter '*.item' -ErrorAction SilentlyContinue)) {
        $j = Get-Content $it.FullName -Raw | ConvertFrom-Json
        if ($j.DisplayName) { $games.Add($j.DisplayName) }
      }
    }
  } catch {}
  try {
    foreach ($k in (Get-ChildItem 'HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games' -ErrorAction SilentlyContinue)) {
      $nm = (Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue).gameName
      if ($nm) { $games.Add($nm) }
    }
  } catch {}
  try {
    $pubs = 'Electronic Arts|Ubisoft|Blizzard|Riot Games|Rockstar|Bethesda|Activision|CD PROJEKT|BANDAI|SQUARE ENIX|CAPCOM|2K|Xbox Game Studios|SEGA|Paradox|FromSoftware|Larian'
    $bad = 'Launcher|Redistributable|Runtime|Framework|Driver|DirectX|Visual C\+\+|Anti-?Cheat|EasyAntiCheat|BattlEye|\bSDK\b|Service|EA app|Origin|Uplay|Ubisoft Connect|Battle\.net|Overwolf|\.NET|Social Club|Rockstar Games Launcher|DisplayName'
    foreach ($rk in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
                      'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
                      'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
      foreach ($e in (Get-ItemProperty $rk -ErrorAction SilentlyContinue)) {
        $dn = "$($e.DisplayName)"; $pb = "$($e.Publisher)"
        if ($dn -and $pb -match $pubs -and $dn -notmatch $bad) { $games.Add($dn) }
      }
    }
  } catch {}
  try {
    foreach ($d in @('C:', 'D:', 'E:', 'F:')) {
      $xg = "$d\XboxGames"
      if (Test-Path $xg) { foreach ($g in (Get-ChildItem $xg -Directory -ErrorAction SilentlyContinue)) { $games.Add($g.Name) } }
    }
  } catch {}
  $skip = @('Steamworks Common Redistributables', 'Steam Linux Runtime', 'Proton EasyAntiCheat Runtime')
  return @($games | Where-Object { $skip -notcontains $_ -and $_ -notmatch 'Proton|Runtime|Redistributable|Anti-?Cheat|Launcher|Redist|DirectX|Visual C\+\+' } | Select-Object -Unique | Select-Object -First 80)
}
function Send-Games($games) {
  $arr = @($games)
  if ($arr.Count -eq 0) { return }
  $items = ($arr | ForEach-Object { '"' + ($_ -replace '\\', '\\' -replace '"', '\"') + '"' }) -join ','
  $body = [System.Text.Encoding]::UTF8.GetBytes('{"games":[' + $items + ']}')
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body | Out-Null } catch {}
}
function Get-RunningApps {
  $cand = @('chrome', 'msedge', 'firefox', 'opera', 'brave', 'Discord', 'Slack', 'Teams', 'Telegram', 'WhatsApp',
            'Skype', 'SkypeApp', 'Spotify', 'Music.UI', 'OneDrive', 'GoogleDriveFS', 'Dropbox', 'EpicGamesLauncher',
            'CCleaner', 'Cortana', 'YourPhone', 'PhoneExperienceHost')
  $run = New-Object System.Collections.Generic.List[string]
  foreach ($a in $cand) { if (Get-Process -Name $a -ErrorAction SilentlyContinue) { $run.Add($a) } }
  return @($run)
}
function Send-Running($apps) {
  $arr = @($apps)
  $items = ($arr | ForEach-Object { '"' + $_ + '"' }) -join ','
  $body = '{"running_apps":[' + $items + ']}'
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body | Out-Null } catch {}
}

# ---------------- Live telemetry ----------------

# v0.7.7: Universal Game Detector. Combina 4 sorgenti:
#  a) Steam RunningAppID (registry)  — 100% affidabile per Steam
#  b) Foreground window + process match contro mappa launcher installati
#  c) Fullscreen exclusive detection (foreground fills primary monitor)
#  d) PresentMon (Get-Fps) — riconosce qualsiasi DX/Vulkan process
# La mappa dei giochi installati (exe -> {name, appid, launcher}) e' costruita una
# sola volta per sessione e cachata in $script:INSTALLED_GAMES.
$script:INSTALLED_GAMES = $null

function Get-InstalledGamesMap {
  if ($null -ne $script:INSTALLED_GAMES) { return $script:INSTALLED_GAMES }
  $map = @{}
  # Steam: legge appmanifest_*.acf per ogni library folder e scansiona common\<installdir>
  try {
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if (-not $steam) { $steam = 'C:\Program Files (x86)\Steam' }
    $libs = @(Join-Path $steam 'steamapps')
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path $vdf) {
      foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
        $libs += (Join-Path ($m.Groups[1].Value -replace '\\\\', '\') 'steamapps')
      }
    }
    foreach ($lib in ($libs | Select-Object -Unique)) {
      if (-not (Test-Path $lib)) { continue }
      foreach ($acf in (Get-ChildItem $lib -Filter 'appmanifest_*.acf' -ErrorAction SilentlyContinue)) {
        try {
          $c = Get-Content $acf.FullName -Raw
          $name = ([regex]::Match($c, '"name"\s+"([^"]+)"')).Groups[1].Value
          $appid = ([regex]::Match($c, '"appid"\s+"(\d+)"')).Groups[1].Value
          $dir = ([regex]::Match($c, '"installdir"\s+"([^"]+)"')).Groups[1].Value
          if (-not $name -or -not $dir) { continue }
          $installPath = Join-Path $lib "common\$dir"
          if (Test-Path $installPath) {
            foreach ($exe in (Get-ChildItem $installPath -Filter '*.exe' -Recurse -Depth 3 -ErrorAction SilentlyContinue)) {
              $k = $exe.Name.ToLower()
              # Skip installer/redist/crash-handler/launcher che non sono il gioco vero
              if ($k -match '(?i)^(unins|redist|vcredist|dxsetup|crash|handler|setup|installer|launcher_help|touchup|updater|eac|be-service|battleye)') { continue }
              if (-not $map.ContainsKey($k)) { $map[$k] = @{ name = $name; appid = $appid; launcher = 'steam' } }
            }
          }
        } catch {}
      }
    }
  } catch {}
  # Epic Games Store: parsing .item JSON manifests
  try {
    $ep = Join-Path $env:ProgramData 'Epic\EpicGamesLauncher\Data\Manifests'
    if (Test-Path $ep) {
      foreach ($it in (Get-ChildItem $ep -Filter '*.item' -ErrorAction SilentlyContinue)) {
        try {
          $j = Get-Content $it.FullName -Raw | ConvertFrom-Json
          if ($j.LaunchExecutable -and $j.DisplayName) {
            $k = (Split-Path $j.LaunchExecutable -Leaf).ToLower()
            if (-not $map.ContainsKey($k)) { $map[$k] = @{ name = "$($j.DisplayName)"; launcher = 'epic' } }
          }
        } catch {}
      }
    }
  } catch {}
  # GOG Galaxy: HKLM registry
  try {
    foreach ($k in (Get-ChildItem 'HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games' -ErrorAction SilentlyContinue)) {
      $p = Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue
      if ($p.exe -and $p.gameName) {
        $key = (Split-Path $p.exe -Leaf).ToLower()
        if (-not $map.ContainsKey($key)) { $map[$key] = @{ name = "$($p.gameName)"; launcher = 'gog' } }
      }
    }
  } catch {}
  # Xbox Game Pass: cartelle in <drive>:\XboxGames\<GameName>\Content\*.exe
  try {
    foreach ($d in @('C:', 'D:', 'E:', 'F:', 'G:')) {
      $xg = "$d\XboxGames"
      if (-not (Test-Path $xg)) { continue }
      foreach ($g in (Get-ChildItem $xg -Directory -ErrorAction SilentlyContinue)) {
        $content = Join-Path $g.FullName 'Content'
        if (-not (Test-Path $content)) { continue }
        foreach ($exe in (Get-ChildItem $content -Filter '*.exe' -Recurse -Depth 3 -ErrorAction SilentlyContinue)) {
          $k = $exe.Name.ToLower()
          if ($k -match '(?i)^(unins|redist|crash|handler|setup|installer)') { continue }
          if (-not $map.ContainsKey($k)) { $map[$k] = @{ name = $g.Name; launcher = 'xbox' } }
        }
      }
    }
  } catch {}
  $script:INSTALLED_GAMES = $map
  return $map
}

function Get-SteamRunningGame {
  # Legge HKCU:\Software\Valve\Steam\RunningAppID + nome da Apps\<id>\Name
  try {
    $rid = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -Name RunningAppID -ErrorAction SilentlyContinue).RunningAppID
    if (-not $rid -or [int]$rid -le 0) { return $null }
    $rid = [int]$rid
    $name = ''
    $ap = Get-ItemProperty "HKCU:\Software\Valve\Steam\Apps\$rid" -Name Name -ErrorAction SilentlyContinue
    if ($ap -and $ap.Name) { $name = "$($ap.Name)" }
    # Fallback nome via mappa installata
    if (-not $name) {
      $map = Get-InstalledGamesMap
      foreach ($v in $map.Values) { if ($v.appid -eq "$rid") { $name = $v.name; break } }
    }
    if (-not $name) { $name = "Steam App $rid" }
    return @{ name = $name; appid = "$rid"; source = 'steam_registry' }
  } catch { return $null }
}

function Get-ForegroundGame {
  # Foreground window + fullscreen detection + risoluzione via launcher map.
  try {
    if (-not ('FFGDWin' -as [type])) {
      Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class FFGDWin {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
}
"@ 2>$null
    }
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    $h = [FFGDWin]::GetForegroundWindow()
    if ($h -eq [IntPtr]::Zero) { return $null }
    $rc = New-Object FFGDWin+RECT
    [void][FFGDWin]::GetWindowRect($h, [ref]$rc)
    $mw = [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize.Width
    $mh = [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize.Height
    $isFull = (($rc.R - $rc.L) -ge ($mw - 2)) -and (($rc.B - $rc.T) -ge ($mh - 2))
    $gp = [uint32]0; [void][FFGDWin]::GetWindowThreadProcessId($h, [ref]$gp)
    $p = Get-Process -Id $gp -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    $skipRe = '(?i)^(explorer|dwm|powershell|pwsh|WindowsTerminal|cmd|chrome|msedge|firefox|opera|brave|Code|devenv|obs64|obs32|Taskmgr|SearchHost|ShellExperienceHost|ApplicationFrameHost|LockApp|vlc|Photos|Netflix|Spotify|Discord|Teams|Slack|WhatsApp|Skype|OneDrive|GoogleDriveFS|Dropbox|WINWORD|EXCEL|POWERPNT|Acrobat|SnippingTool|Notepad|Notepad\+\+|steam|steamwebhelper|EpicGamesLauncher|GalaxyClient|Battle\.net|EADesktop|UbisoftConnect)$'
    if ($p.Name -match $skipRe) { return $null }
    $exeName = "$($p.Name).exe".ToLower()
    $map = Get-InstalledGamesMap
    if ($map.ContainsKey($exeName)) {
      $hit = $map[$exeName]
      return @{
        name = $hit.name
        appid = $hit.appid
        source = ('fg_' + $hit.launcher)
        exe = $p.Name
        is_fullscreen = $isFull
      }
    }
    # Non nella mappa: se fullscreen, e' comunque probabilmente un gioco (indie/portable/emulatore).
    if ($isFull) {
      return @{
        name = ($p.Name -replace '[_\-]+', ' ')
        source = 'fg_fullscreen'
        exe = $p.Name
        is_fullscreen = $true
      }
    }
    return $null
  } catch { return $null }
}

function Get-CurrentGame {
  # Orchestratore: Steam registry > Foreground fullscreen > PresentMon (Get-Fps).
  # Ritorna @{name, appid?, source, exe?, is_fullscreen?} o $null.
  $g = Get-SteamRunningGame
  if ($g) { return $g }
  $g = Get-ForegroundGame
  if ($g) { return $g }
  # PresentMon fallback: se sta gia' catturando FPS, quel processo E' un gioco.
  try {
    $f = Get-Fps
    if ($f -and $f.game -and $f.fps -ge 10) {
      $exeName = "$($f.game).exe".ToLower()
      $map = Get-InstalledGamesMap
      if ($map.ContainsKey($exeName)) {
        $hit = $map[$exeName]
        return @{
          name = $hit.name; appid = $hit.appid
          source = ('pm_' + $hit.launcher); exe = $f.game
        }
      }
      return @{ name = ($f.game -replace '[_\-]+', ' '); source = 'presentmon'; exe = $f.game }
    }
  } catch {}
  return $null
}

function Get-TelemetrySample {
  $s = @{ ts = (Get-Date).ToString('o') }
  # Contatore di prestazione invece di Win32_Processor.LoadPercentage: quello e'
  # aggiornato di rado e mediato su una finestra che non controlliamo, ed e' il
  # numero che finisce nel grafico live e nelle correlazioni del Gameplay Doctor.
  $cpuBusy = Get-CpuBusyPct
  if ($null -ne $cpuBusy) { $s.cpu_util = [int][math]::Round($cpuBusy) }
  $o = Get-CimInstance Win32_OperatingSystem
  $s.ram_used_pct = [int]([math]::Round(($o.TotalVisibleMemorySize - $o.FreePhysicalMemory) / $o.TotalVisibleMemorySize * 100))
  $lhm = Get-LhmTemps
  if ($lhm.ContainsKey('cpu_temp')) { $s.cpu_temp = $lhm.cpu_temp }
  else {
    $tzt = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tzt -and $tzt.CurrentTemperature -gt 2732) {
      $ct = [int]([math]::Round(($tzt.CurrentTemperature - 2732) / 10))
      if ($ct -gt 0) { $s.cpu_temp = $ct }
    }
  }
  # v0.7.7: precision sensors nel sample live (per il grafico + bento "Precision Sensors")
  if ($lhm.ContainsKey('fan_rpm_max')) { $s.fan_rpm_max = $lhm.fan_rpm_max }
  if ($lhm.ContainsKey('vrm_temp')) { $s.vrm_temp = $lhm.vrm_temp }
  if ($lhm.ContainsKey('cpu_power')) { $s.cpu_power = $lhm.cpu_power }
  if ($lhm.ContainsKey('cpu_vcore')) { $s.cpu_vcore = $lhm.cpu_vcore }
  $nv = & nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,clocks.gr,memory.used,memory.total,power.draw --format=csv,noheader,nounits 2>$null
  if ($nv) {
    $p = ($nv | Select-Object -First 1).Split(',')
    $s.gpu_util = [int]($p[0].Trim())
    $s.gpu_temp = [int]($p[1].Trim())
    $s.gpu_clock = [int]($p[2].Trim())
    $mu = [double]$p[3].Trim(); $mt = [double]$p[4].Trim()
    if ($mt -gt 0) { $s.vram_used_pct = [int]([math]::Round($mu / $mt * 100)) }
    $s.gpu_power = [int]([math]::Round([double]$p[5].Trim()))
  }
  elseif ($lhm.ContainsKey('gpu_temp')) {
    $s.gpu_temp = $lhm.gpu_temp
    # v0.7.7: se nvidia-smi non c'è (AMD/Intel), usa LHM anche per gpu_power
    if ($lhm.ContainsKey('gpu_power_lhm')) { $s.gpu_power = $lhm.gpu_power_lhm }
  }
  # v0.7.7: Universal Game Detector — Steam registry / foreground fullscreen / PresentMon
  try {
    $cg = Get-CurrentGame
    if ($cg) {
      $s.game_name = $cg.name
      if ($cg.appid) { $s.steam_appid = $cg.appid }
      if ($cg.source) { $s.game_source = $cg.source }
      if ($cg.exe) { $s.game_exe = $cg.exe }
      if ($null -ne $cg.is_fullscreen) { $s.game_fullscreen = [bool]$cg.is_fullscreen }
    }
  } catch {}
  return $s
}
function Send-Telemetry($sample) {
  $body = @{ sample = $sample } | ConvertTo-Json -Depth 5 -Compress
  try {
    $resp = Invoke-RestMethod -Uri "$BACKEND/api/agent/telemetry" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body
    # Backend signals a graceful stop when the user clicks Stop on the web
    # dashboard. Monitor loop reads this and breaks (see MODE=monitor).
    if ($resp -and $resp.stop) { return $true }
  } catch {}
  return $false
}
function Push-LiveSample {
  # Lightweight sample sent to cloud when Live Sync toggle is ON.
  # Reuses Get-TelemetrySample which already handles CPU/GPU/RAM/temps via WMI+LHM.
  try {
    $sample = Get-TelemetrySample
    if ($sample) { Send-Telemetry $sample | Out-Null }
  } catch {}
}

# ---------------- FPS via PresentMon (opzionale, richiede admin) ----------------
$script:PM_EXE = Join-Path $env:TEMP 'PresentMon.exe'
$script:PM_CSV = Join-Path $env:TEMP 'boostpc_fps.csv'
$script:PM_OUT = Join-Path $env:TEMP 'boostpc_pm_out.log'
$script:PM_ERR = Join-Path $env:TEMP 'boostpc_pm_err.log'
$script:PM_ON  = $false
$script:PM_ROWS = 1
$script:PM_PROC = $null
$script:PM_DIAG_DONE = $false
$script:PM_URL = 'https://github.com/GameTechDev/PresentMon/releases/download/v2.4.1/PresentMon-2.4.1-x64.exe'
function Read-Shared($path) {
  try {
    $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $sr = New-Object System.IO.StreamReader($fs)
    $t = $sr.ReadToEnd(); $sr.Close(); $fs.Close(); return $t
  } catch { return '' }
}
# ---------------- Istogramma dei frametime ----------------
# Stessa suddivisione di lab_stats.py (HIST_BUCKETS = 306): risoluzione fine
# dove i frame sono veloci e i millisecondi contano, grossolana sopra i 100 ms
# dove non interessa piu' a nessuno. Se cambia li' va cambiata anche qui,
# altrimenti il backend calcola percentili su una scala diversa da quella che
# crede di avere.
#   [0,20) 0.1ms | [20,50) 0.5ms | [50,100) 2ms | [100,300) 10ms | >=300 coda
function Get-HistBucket([double]$ms) {
  if ($ms -lt 0) { $ms = 0 }
  if ($ms -lt 20) { return [int][math]::Floor($ms / 0.1) }
  if ($ms -lt 50) { return 200 + [int][math]::Floor(($ms - 20) / 0.5) }
  if ($ms -lt 100) { return 260 + [int][math]::Floor(($ms - 50) / 2.0) }
  if ($ms -lt 300) { return 285 + [int][math]::Floor(($ms - 100) / 10.0) }
  return 305
}
function Get-HistMid([int]$i) {
  if ($i -ge 305) { return 350.0 }
  if ($i -lt 200) { return $i * 0.1 + 0.05 }
  if ($i -lt 260) { return 20.0 + ($i - 200) * 0.5 + 0.25 }
  if ($i -lt 285) { return 50.0 + ($i - 260) * 2.0 + 1.0 }
  return 100.0 + ($i - 285) * 10.0 + 5.0
}

function Test-FpsCapable {
  # 'ok' = ETW consentito (admin, o token con gruppo Performance Log Users S-1-5-32-559)
  # 'relogon' = utente iscritto al gruppo ma token vecchio: serve logout/riavvio
  # 'no' = permessi assenti
  if (Test-Admin) { return 'ok' }
  try { $tok = (whoami /groups) 2>$null; if ($tok -match 'S-1-5-32-559') { return 'ok' } } catch {}
  try {
    $me = $env:USERNAME
    $mem = Get-LocalGroupMember -SID 'S-1-5-32-559' -ErrorAction Stop | Where-Object { $_.Name -like ("*\" + $me) }
    if ($mem) { return 'relogon' }
  } catch {}
  return 'no'
}

function Enable-FpsPermission {
  # Eseguito quando siamo ELEVATI (GUI Ottimizza): iscrive l'utente al gruppo
  # 'Performance Log Users' (SID S-1-5-32-559) cosi PresentMon cattura gli FPS
  # anche SENZA admin. Windows richiede logout/riavvio per aggiornare il token.
  # Necessario da v0.8.0: il monitor non gira piu elevato (fix UAC), quindi la
  # cattura ETW va autorizzata una tantum qui.
  if (-not (Test-Admin)) { return $false }
  $me = $env:USERNAME
  try {
    $already = $null
    try { $already = Get-LocalGroupMember -SID 'S-1-5-32-559' -ErrorAction Stop | Where-Object { $_.Name -like ("*\" + $me) } } catch {}
    if ($already) { return $true }
    try { Add-LocalGroupMember -SID 'S-1-5-32-559' -Member $me -ErrorAction Stop }
    catch {
      $gname = ((New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-559')).Translate([System.Security.Principal.NTAccount]).Value -split '\\')[-1]
      net localgroup "$gname" "$me" /add 2>$null | Out-Null
    }
    Say-Ok '   Permessi cattura FPS attivati (gruppo Performance Log Users): dopo un riavvio o logout il monitor contera gli FPS senza admin.' 'FPS'
    try { WebLog '[FPS] Permessi cattura FPS attivati: riavvia il PC (o fai logout) per renderli effettivi.' } catch {}
    return $true
  } catch { return $false }
}

function Start-Fps {
  $cap = Test-FpsCapable
  if ($cap -eq 'relogon') {
    Say-Warn '   Permessi FPS gia attivati ma serve un riavvio (o logout) di Windows per renderli effettivi. Dopo, gli FPS verranno contati senza admin.' 'FPS'
    return
  }
  if ($cap -eq 'no') {
    Say-Warn '   Cattura FPS non disponibile: apri una volta la GUI FrameForge (doppio click su forgefps-agent.exe -> Ottimizza, con conferma amministratore) per attivare i permessi in automatico, poi riavvia il PC.' 'FPS'
    return
  }
  if (-not (Test-Path $script:PM_EXE)) {
    Say-Info '   Scarico PresentMon (una volta sola)...' 'FPS'
    try {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest $script:PM_URL -OutFile $script:PM_EXE -UseBasicParsing
    } catch { Say-Warn ('   Download PresentMon fallito: ' + $_.Exception.Message) 'FPS'; return }
  }
  Remove-Item $script:PM_CSV, $script:PM_OUT, $script:PM_ERR -ErrorAction SilentlyContinue
  try {
    $script:PM_PROC = Start-Process -FilePath $script:PM_EXE `
      -ArgumentList '--output_stdout', '--stop_existing_session', '--v1_metrics', '--no_console_stats' `
      -WindowStyle Hidden -PassThru -RedirectStandardOutput $script:PM_OUT -RedirectStandardError $script:PM_ERR
    $script:PM_ON = $true
    Start-Sleep -Milliseconds 1500
    if ($script:PM_PROC -and $script:PM_PROC.HasExited) {
      $script:PM_ON = $false
      $err = ''
      if (Test-Path $script:PM_ERR) { $err = (Get-Content $script:PM_ERR -Raw -ErrorAction SilentlyContinue) }
      Say-Warn ('   PresentMon si e chiuso subito (exit ' + $script:PM_PROC.ExitCode + '). Dettaglio: ' + ($err.Trim() -replace "`r?`n", ' | ')) 'FPS'
    } else {
      Say-Info '   Cattura FPS attiva. Avvia un gioco (o uno screensaver 3D) a schermo intero.' 'FPS'
    }
  } catch { Say-Warn ('   Avvio PresentMon fallito: ' + $_.Exception.Message) 'FPS' }
}
function Stop-Fps { if ($script:PM_ON) { Stop-Process -Name PresentMon -Force -ErrorAction SilentlyContinue; $script:PM_ON = $false } }
function Show-FpsDiag {
  if ($script:PM_DIAG_DONE) { return }
  $script:PM_DIAG_DONE = $true
  Say-Warn '   Nessun FPS ancora rilevato. Controllo stato:' 'diag FPS'
  $alive = ($script:PM_PROC -and -not $script:PM_PROC.HasExited)
  Say ("             PresentMon attivo: {0}" -f $(if($alive){'si'}else{'NO'})) 'DarkGray'
  if (Test-Path $script:PM_OUT) {
    $sz = (Get-Item $script:PM_OUT).Length
    Say ("             Output PresentMon: si ({0} byte)" -f $sz) 'DarkGray'
    $raw = Read-Shared $script:PM_OUT
    $ln = $raw -split "`r?`n" | Where-Object { $_ -ne '' }
    Say ("             Righe dati: {0}" -f $ln.Count) 'DarkGray'
    if ($ln.Count -ge 1) { Say ("             Intestazione: " + ($ln[0].Substring(0,[math]::Min(120,$ln[0].Length)))) 'DarkGray' }
  } else {
    Say '             Output PresentMon: NO (nessun dato)' 'DarkGray'
  }
  if (-not $alive) {
    $err = ''
    if (Test-Path $script:PM_ERR) { $err = (Get-Content $script:PM_ERR -Raw -ErrorAction SilentlyContinue) }
    if ($err.Trim()) { Say ('             Errore PresentMon: ' + ($err.Trim() -replace "`r?`n", ' | ')) 'DarkGray' }
  }
  Say-Warn '   Se serve, incolla queste righe in chat. Ricorda: gli FPS compaiono SOLO mentre un app renderizza a schermo (uno screensaver si chiude al primo movimento del mouse).' 'diag FPS'
}
function Get-Fps {
  if (-not $script:PM_ON) { return $null }
  $raw = Read-Shared $script:PM_OUT
  if (-not $raw) { return $null }
  $lines = $raw -split "`r?`n" | Where-Object { $_ -ne '' }
  if (-not $lines -or $lines.Count -le $script:PM_ROWS) { return $null }
  $hdr = $lines[0] -split ','
  $iApp = -1; $iMs = -1; $iLat = -1; $iLatFb = -1
  for ($k = 0; $k -lt $hdr.Count; $k++) {
    $h = $hdr[$k].Trim().ToLower()
    if ($h -eq 'application') { $iApp = $k }
    if ($h -like '*betweenpresents*') { $iMs = $k }
    if ($h -like '*untildisplayed*') { $iLat = $k }
    if ($h -like '*untilrendercomplete*') { $iLatFb = $k }
  }
  if ($iLat -lt 0) { $iLat = $iLatFb }
  if ($iMs -lt 0) { $script:PM_ROWS = $lines.Count; return $null }
  $new = $lines[$script:PM_ROWS..($lines.Count - 1)]
  $script:PM_ROWS = $lines.Count
  $byApp = @{}
  $inv = [Globalization.CultureInfo]::InvariantCulture
  foreach ($ln in $new) {
    $c = $ln -split ','
    if ($c.Count -le $iMs) { continue }
    $app = if ($iApp -ge 0 -and $c.Count -gt $iApp) { $c[$iApp] } else { 'game' }
    try { $ms = [double]::Parse($c[$iMs], $inv) } catch { continue }
    if ($ms -le 0) { continue }
    if (-not $byApp.ContainsKey($app)) { $byApp[$app] = @{ sum = 0.0; n = 0; lsum = 0.0; ln = 0; fr = (New-Object System.Collections.ArrayList) } }
    $byApp[$app].sum += $ms; $byApp[$app].n++
    [void]$byApp[$app].fr.Add($ms)
    if ($iLat -ge 0 -and $c.Count -gt $iLat) {
      try { $lat = [double]::Parse($c[$iLat], $inv); if ($lat -gt 0 -and $lat -lt 1000) { $byApp[$app].lsum += $lat; $byApp[$app].ln++ } } catch {}
    }
  }
  if ($byApp.Count -eq 0) { return $null }
  $top = $byApp.GetEnumerator() | Sort-Object { $_.Value.n } -Descending | Select-Object -First 1
  $avg = $top.Value.sum / $top.Value.n
  if ($avg -le 0) { return $null }
  $lat = if ($top.Value.ln -gt 0) { [int]([math]::Round($top.Value.lsum / $top.Value.ln)) } else { $null }
  # Gameplay Doctor v2: firme frametime per-tick con soglia hitch ADATTIVA
  # (3x mediana di sessione, min 25ms) + CV pacing + istogramma cumulativo di
  # sessione (60 bucket) per 1% / 0.1% low ESATTI lato backend.
  $gd = $null
  $fr = $top.Value.fr
  if ($fr -and $fr.Count -ge 10) {
    # Istogramma a 306 bucket (stessa scala del Lab e di lab_stats.py). Quello
    # a 1 ms usato prima aveva senso a 60 FPS, ma a 200 FPS un frame dura 5 ms:
    # il bucket era il 20% del valore, e la mediana ne ereditava l'incertezza.
    if (-not $script:GD_HIST) { $script:GD_HIST = New-Object 'int[]' 306; $script:GD_N = 0; $script:GD_TICK = 0 }
    foreach ($v in $fr) { $script:GD_HIST[(Get-HistBucket ([double]$v))]++ }
    $script:GD_N += $fr.Count
    $script:GD_TICK++
    $half = $script:GD_N / 2; $cum = 0; $med = 8.0
    for ($b = 0; $b -lt 306; $b++) {
      $cum += $script:GD_HIST[$b]
      if ($cum -ge $half) { $med = (Get-HistMid $b); break }
    }
    $thr = [math]::Max(25.0, 3.0 * $med)
    $sorted = [double[]]$fr.ToArray(); [Array]::Sort($sorted)
    $p99 = $sorted[[math]::Min($sorted.Length - 1, [int][math]::Ceiling(0.99 * $sorted.Length) - 1)]
    $hit = 0; foreach ($v in $sorted) { if ($v -gt $thr) { $hit++ } }
    $mean = 0.0; foreach ($v in $fr) { $mean += $v }; $mean = $mean / $fr.Count
    $sd = 0.0; foreach ($v in $fr) { $sd += ([double]$v - $mean) * ([double]$v - $mean) }
    $cv = if ($mean -gt 0) { [math]::Round([math]::Sqrt($sd / $fr.Count) / $mean, 3) } else { 0 }
    $pd = 0.0
    for ($q = 1; $q -lt $fr.Count; $q++) { $pd += [math]::Abs([double]$fr[$q] - [double]$fr[$q - 1]) }
    $pd = $pd / ($fr.Count - 1)
    $gd = @{ ft_p99 = [math]::Round($p99, 1); ft_worst = [math]::Round($sorted[$sorted.Length - 1], 1); hitches = $hit; pace_dev = [math]::Round($pd, 2); ft_cv = $cv; hitch_thr = [math]::Round($thr, 1) }
    # ogni 30 tick allega l'istogramma cumulativo (compatto: 60 int)
    if (($script:GD_TICK % 30) -eq 0) { $gd.hist = $script:GD_HIST; $gd.hist_n = $script:GD_N }
  }
  return @{ fps = [int]([math]::Round(1000 / $avg)); game = ($top.Key -replace '\.exe$', ''); latency_ms = $lat; gd = $gd }
}

# ---------------- Tweak actions ----------------
function Do-Cleanup {
  Get-ChildItem $env:TEMP -Recurse -Force 2>$null | Remove-Item -Recurse -Force 2>$null
  Stop-Service wuauserv -Force 2>$null
  Get-ChildItem "$env:SystemRoot\SoftwareDistribution\Download" -Recurse -Force 2>$null | Remove-Item -Recurse -Force 2>$null
  Start-Service wuauserv 2>$null
  ipconfig /flushdns | Out-Null
}
function Do-Power {
  $curScheme = (powercfg /getactivescheme)
  if ($curScheme -match '([0-9a-fA-F-]{36})' -and -not $script:BK.ContainsKey('power_plan')) { $script:BK['power_plan'] = $matches[1] }
  if ($script:HW.laptop) {
    # Laptop: High Performance (non Ultimate), niente USB/PCIe power off globale per batteria/temperature
    powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null
    powercfg /setacvalueindex scheme_current sub_processor 893dee8e-2bef-41e0-89c6-b55d0929964c 100 2>$null
    powercfg /setacvalueindex scheme_current sub_processor bc5038f7-23e0-4960-96da-33abaf5935ec 100 2>$null
    powercfg -setactive scheme_current 2>$null
    return
  }
  $ultimate = 'e9a42b02-d5df-448d-aa00-03f14749eb61'
  powercfg -duplicatescheme $ultimate 2>$null | Out-Null
  powercfg -setactive $ultimate 2>$null
  if ($LASTEXITCODE -ne 0) { powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null }
  # min/max processor 100%, core parking off, USB selective suspend off, PCIe ASPM off
  powercfg /setacvalueindex scheme_current sub_processor 893dee8e-2bef-41e0-89c6-b55d0929964c 100 2>$null
  powercfg /setacvalueindex scheme_current sub_processor bc5038f7-23e0-4960-96da-33abaf5935ec 100 2>$null
  powercfg /setacvalueindex scheme_current sub_processor 0cc5b647-c1df-4637-891a-dec35c318583 100 2>$null
  powercfg /setacvalueindex scheme_current 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0 2>$null
  powercfg /setacvalueindex scheme_current 501a4d13-42af-4429-9fd1-a8218c268e20 ee12f906-d277-404b-b6da-e5fa1a576df5 0 2>$null
  powercfg -setactive scheme_current 2>$null
}
function Do-Gaming {
  Set-Reg 'HKCU:\Software\Microsoft\GameBar' 'AllowAutoGameMode' 'DWord' 1
  Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' 'HwSchMode' 'DWord' 2
  Set-Reg 'HKCU:\System\GameConfigStore' 'GameDVR_Enabled' 'DWord' 0
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\GameDVR' 'AllowGameDVR' 'DWord' 0
}
function Do-Priority {
  $sp = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile'
  Set-Reg $sp 'SystemResponsiveness' 'DWord' 0
  Set-Reg $sp 'NetworkThrottlingIndex' 'DWord' 4294967295
  $games = "$sp\Tasks\Games"
  Set-Reg $games 'GPU Priority' 'DWord' 8
  Set-Reg $games 'Priority' 'DWord' 6
  Set-Reg $games 'Scheduling Category' 'String' 'High'
  Set-Reg $games 'SFIO Priority' 'String' 'High'
  Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\PriorityControl' 'Win32PrioritySeparation' 'DWord' 26
}
function Do-Mpo { Set-Reg 'HKLM:\SOFTWARE\Microsoft\Windows\Dwm' 'OverlayTestMode' 'DWord' 5 }
function Do-GpuMsi {
  $pnp = Get-GpuPnp
  if ($pnp) { $p = "HKLM:\SYSTEM\CurrentControlSet\Enum\$pnp\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"; Set-Reg $p 'MSISupported' 'DWord' 1 }
}
function Do-AmdUlps {
  $root = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
  Get-ChildItem $root 2>$null | ForEach-Object {
    $dd = (Get-ItemProperty $_.PSPath -Name DriverDesc -ErrorAction SilentlyContinue).DriverDesc
    if ($dd -match 'AMD|Radeon') { Set-Reg $_.PSPath 'EnableUlps' 'DWord' 0 }
  }
}
function Do-NvidiaTel {
  Get-ScheduledTask -TaskName 'NvTmRep*','NvProfileUpdater*','NvTmMon*','NvTmRepOnLogon*','NvDriverUpdateCheckDaily*' -ErrorAction SilentlyContinue | Disable-ScheduledTask -ErrorAction SilentlyContinue | Out-Null
  Stop-Service 'NvTelemetryContainer' -Force 2>$null
  $svc = Get-Service 'NvTelemetryContainer' -ErrorAction SilentlyContinue
  if ($svc -and -not $script:BK.ContainsKey('svc::NvTelemetryContainer')) { $script:BK['svc::NvTelemetryContainer'] = "$($svc.StartType)"; Set-Service 'NvTelemetryContainer' -StartupType Disabled 2>$null }
}
function Do-Hibernate { if (-not $script:BK.ContainsKey('hib')) { $script:BK['hib'] = 'on' }; powercfg -h off 2>$null }
function Do-Mouse {
  Set-Reg 'HKCU:\Control Panel\Mouse' 'MouseSpeed' 'String' '0'
  Set-Reg 'HKCU:\Control Panel\Mouse' 'MouseThreshold1' 'String' '0'
  Set-Reg 'HKCU:\Control Panel\Mouse' 'MouseThreshold2' 'String' '0'
}
function Do-Timer { Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\kernel' 'GlobalTimerResolutionRequests' 'DWord' 1 }
function Do-Usb {
  Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB' -ErrorAction SilentlyContinue | ForEach-Object {
    Get-ChildItem $_.PSPath -ErrorAction SilentlyContinue | ForEach-Object {
      $dp = Join-Path $_.PSPath 'Device Parameters'
      if (Test-Path $dp) { Set-Reg $dp 'EnhancedPowerManagementEnabled' 'DWord' 0 }
    }
  }
}
function Do-StickyKeys {
  Set-Reg 'HKCU:\Control Panel\Accessibility\StickyKeys' 'Flags' 'String' '506'
  Set-Reg 'HKCU:\Control Panel\Accessibility\Keyboard Response' 'Flags' 'String' '122'
  Set-Reg 'HKCU:\Control Panel\Accessibility\ToggleKeys' 'Flags' 'String' '58'
}
function Do-StartupDelay { Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize' 'StartupDelayInMSec' 'DWord' 0 }
function Do-Visual { Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting' 'DWord' 2 }
function Do-Network {
  $ifRoot = 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces'
  Get-ChildItem $ifRoot 2>$null | ForEach-Object { $p = Join-Path $ifRoot $_.PSChildName; Set-Reg $p 'TcpAckFrequency' 'DWord' 1; Set-Reg $p 'TCPNoDelay' 'DWord' 1 }
  netsh int tcp set global autotuninglevel=normal 2>$null | Out-Null
  netsh int tcp set global ecncapability=enabled 2>$null | Out-Null
  netsh int tcp set global rss=enabled 2>$null | Out-Null
}
function Do-Dns {
  $adapter = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' } | Select-Object -First 1
  if ($adapter -and -not $script:BK.ContainsKey("dns::$($adapter.Name)")) { $script:BK["dns::$($adapter.Name)"] = 'reset'; Set-DnsClientServerAddress -InterfaceAlias $adapter.Name -ServerAddresses ('1.1.1.1','1.0.0.1') 2>$null }
}
function Do-Qos { Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched' 'NonBestEffortLimit' 'DWord' 0 }
function Do-DeliveryOpt {
  Set-Reg 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config' 'DODownloadMode' 'DWord' 0
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization' 'DODownloadMode' 'DWord' 0
}
function Do-ObsPriority {
  foreach ($exe in 'obs64.exe','obs32.exe') { $p = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\$exe\PerfOptions"; Set-Reg $p 'CpuPriorityClass' 'DWord' 3 }
}
function Do-Telemetry {
  Disable-ServiceSafe 'DiagTrack' | Out-Null
}
function Do-Ads {
  $cdm = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager'
  Set-Reg $cdm 'SilentInstalledAppsEnabled' 'DWord' 0
  Set-Reg $cdm 'SystemPaneSuggestionsEnabled' 'DWord' 0
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableWindowsConsumerFeatures' 'DWord' 1
}
function Do-BgApps {
  Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled' 'DWord' 1
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy' 'LetAppsRunInBackground' 'DWord' 2
}
function Do-GamebarRec {
  Set-Reg 'HKCU:\System\GameConfigStore' 'GameDVR_Enabled' 'DWord' 0
  Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' 'AppCaptureEnabled' 'DWord' 0
}
function Do-SearchIndex {
  Disable-ServiceSafe 'WSearch' | Out-Null
}
function Do-Fse {
  $g = 'HKCU:\System\GameConfigStore'
  Set-Reg $g 'GameDVR_FSEBehaviorMode' 'DWord' 2
  Set-Reg $g 'GameDVR_HonorUserFSEBehaviorMode' 'DWord' 1
  Set-Reg $g 'GameDVR_DXGIHonorFSEWindowsCompatible' 'DWord' 1
  Set-Reg $g 'GameDVR_EFSEFeatureFlags' 'DWord' 0
}
function Do-PowerThrottling { Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling' 'PowerThrottlingOff' 'DWord' 1 }
function Do-PagingExec { Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management' 'DisablePagingExecutive' 'DWord' 1 }
function Do-SysMain { Disable-ServiceSafe 'SysMain' | Out-Null }
function Do-Trim { fsutil behavior set DisableDeleteNotify 0 2>$null | Out-Null }
function Do-Ntfs {
  if (-not $script:BK.ContainsKey('ntfs::lastaccess')) {
    $q = (fsutil behavior query disablelastaccess) -join ' '
    $old = '2'; if ($q -match '=\s*(\d)') { $old = $matches[1] }
    $script:BK['ntfs::lastaccess'] = $old
  }
  fsutil behavior set disablelastaccess 1 2>$null | Out-Null
}
function Do-NicPower {
  $root = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}'
  $ups = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' }
  foreach ($a in $ups) {
    Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
      $id = (Get-ItemProperty $_.PSPath -Name NetCfgInstanceId -ErrorAction SilentlyContinue).NetCfgInstanceId
      if ($id -eq $a.InterfaceGuid) {
        Set-Reg $_.PSPath 'PnPCapabilities' 'DWord' 24
        $im = (Get-ItemProperty $_.PSPath -Name '*InterruptModeration' -ErrorAction SilentlyContinue).'*InterruptModeration'
        if ($null -ne $im) { Set-Reg $_.PSPath '*InterruptModeration' 'String' '0' }
      }
    }
  }
}
function Do-EdgePreload {
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Edge' 'StartupBoostEnabled' 'DWord' 0
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Edge' 'BackgroundModeEnabled' 'DWord' 0
}
function Clear-StandbyList {
  if (-not ('FFMem' -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class FFMem {
  [DllImport("ntdll.dll")] public static extern int NtSetSystemInformation(int cls, ref int info, int len);
  [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr h, int acc, out IntPtr tok);
  [DllImport("advapi32.dll", SetLastError=true)] static extern bool LookupPrivilegeValue(string s, string n, out long luid);
  [StructLayout(LayoutKind.Sequential)] struct TP { public int Count; public long Luid; public int Attr; }
  [DllImport("advapi32.dll", SetLastError=true)] static extern bool AdjustTokenPrivileges(IntPtr tok, bool d, ref TP st, int len, IntPtr p, IntPtr r);
  [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
  public static int Purge() {
    IntPtr tok; OpenProcessToken(GetCurrentProcess(), 0x28, out tok);
    long luid; LookupPrivilegeValue(null, "SeProfileSingleProcessPrivilege", out luid);
    TP tp; tp.Count = 1; tp.Luid = luid; tp.Attr = 2;
    AdjustTokenPrivileges(tok, false, ref tp, 0, IntPtr.Zero, IntPtr.Zero);
    int cmd = 4;
    return NtSetSystemInformation(80, ref cmd, 4);
  }
}
"@ 2>$null
  }
  try { [FFMem]::Purge() | Out-Null } catch {}
}
$script:BLOAT = @('Microsoft.549981C3F5F10','Microsoft.BingNews','Microsoft.BingWeather','Microsoft.GetHelp',
  'Microsoft.Getstarted','Microsoft.WindowsFeedbackHub','Microsoft.MicrosoftSolitaireCollection',
  'Microsoft.People','Microsoft.WindowsMaps','Microsoft.3DBuilder','Microsoft.MixedReality.Portal',
  'king.com.CandyCrushSaga','Microsoft.SkypeApp')
function Do-Debloat { foreach ($pkg in $script:BLOAT) { $app = Get-AppxPackage -Name $pkg -ErrorAction SilentlyContinue; if ($app) { $app | Remove-AppxPackage -ErrorAction SilentlyContinue } } }

# ---------------- Bloatware auto-discovery (v0.7.7, allineato a tweaks.py) ----------------
$script:BLOAT_PATTERNS = @('Microsoft.Bing*','Microsoft.Advertising*','Microsoft.OneConnect','*CandyCrush*',
  '*Disney*','*Netflix*','*Facebook*','*Twitter*','*Spotify*','*.DellCustomerConnect','*.DellDigitalDelivery',
  '*.HPPCHardwareDiagnostics*','*HPJumpStart*','*LenovoVantage*','*LenovoUtility*','*Dropbox*Promo*','*McAfee*','*Norton*')
$script:BLOAT_NEVER = @('Microsoft.WindowsStore','Microsoft.WindowsCalculator','Microsoft.Windows.Photos',
  'Microsoft.ScreenSketch','Microsoft.WindowsTerminal','Microsoft.Windows.SecHealthUI','Microsoft.DesktopAppInstaller',
  'Microsoft.WindowsCamera','Microsoft.WindowsSoundRecorder','Microsoft.WindowsNotepad','Microsoft.HEIFImageExtension',
  'Microsoft.WebpImageExtension','Microsoft.RawImageExtension','Microsoft.VP9VideoExtensions','Microsoft.HEVCVideoExtension',
  'Microsoft.AV1VideoExtension','Microsoft.WebMediaExtensions','Microsoft.MPEG2VideoExtension',
  'Microsoft.LanguageExperiencePack*','Microsoft.UI.Xaml*','Microsoft.VCLibs*','Microsoft.NET.Native*')

function Test-BloatProtected($name) {
  foreach ($nr in $script:BLOAT_NEVER) {
    if ($nr.EndsWith('*')) { if ($name -like $nr) { return $true } }
    elseif ($name -ieq $nr) { return $true }
  }
  return $false
}

function Get-BloatCandidates {
  $found = @{}
  foreach ($p in $script:BLOAT) {
    $a = Get-AppxPackage -Name $p -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($a) { $found[$a.Name] = $a }
  }
  foreach ($pat in $script:BLOAT_PATTERNS) {
    Get-AppxPackage -Name $pat -ErrorAction SilentlyContinue | ForEach-Object { $found[$_.Name] = $_ }
  }
  $out = @()
  foreach ($k in @($found.Keys | Sort-Object)) {
    if (Test-BloatProtected $k) { continue }
    $a = $found[$k]
    $sizeMb = 0
    try { if ($a.InstallLocation -and (Test-Path $a.InstallLocation)) {
      $sizeMb = [math]::Round(((Get-ChildItem $a.InstallLocation -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1MB, 1)
    } } catch {}
    $out += @{ name = $a.Name; version = "$($a.Version)"; size_mb = $sizeMb; curated = ($script:BLOAT -contains $a.Name) }
  }
  return ,@($out)
}

# ---------------- Tweak catalogue (cat / id / name / desc / state / apply) ----------------
$script:TWEAKS = @(
  # GAMING & FPS
  @{ cat='gaming'; id='power'; name='Piano energetico prestazioni massime';
     problem='Windows usa un piano energetico bilanciato che rallenta CPU/GPU e parcheggia i core per risparmiare.';
     reason='Con il core parking e il throttling la CPU non gira mai al 100% quando serve, causando cali di FPS e stutter.';
     desc='Attiva Ultimate/High Performance, disattiva core parking, processore al 100%, USB suspend e PCIe ASPM off.';
     impact='+3-8% FPS medi e 1% low piu stabili, meno micro-stutter. Consuma piu energia (irrilevante su desktop).';
     risk='safe';
     fit={ if($script:HW.laptop){'note:Laptop rilevato: applico High Performance (non Ultimate) per proteggere batteria e temperature'}else{'ok'} };
     state={ $p=(powercfg /getactivescheme); if($p -match 'high|ultimate|prestazioni elevate'){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Power } }
  @{ cat='gaming'; id='gaming'; name='Boost gaming (Game Mode, HAGS, Game DVR off)';
     problem='Game DVR registra in background e la GPU scheduling hardware potrebbe essere disattivata.';
     reason='Il Game DVR ruba CPU/GPU durante il gioco; HAGS riduce la latenza di pianificazione dei frame.';
     desc='Attiva Game Mode + Hardware GPU Scheduling, disattiva Game DVR/registrazione in background.';
     impact='+2-5% FPS e frametime piu costante, meno overhead durante il gioco.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\GameBar' 'AllowAutoGameMode') -eq 1){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Gaming } }
  @{ cat='gaming'; id='priority'; name='Priorita GPU/CPU ai giochi (MMCSS)';
     problem='Windows assegna le stesse risorse ai processi in background e al gioco in primo piano.';
     reason='MMCSS/SystemResponsiveness a 0 da priorita reale ai task multimediali e ai giochi attivi.';
     desc='Imposta SystemResponsiveness=0 e priorita GPU/CPU ai giochi in primo piano.';
     impact='Frametime piu regolare, meno spike quando ci sono app in background.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile' 'SystemResponsiveness') -eq 0){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Priority } }
  @{ cat='gaming'; id='mpo'; name='Disabilita MPO (Multi-Plane Overlay)';
     problem='Il Multi-Plane Overlay causa flickering, stutter e SCHERMO NERO in OBS Game Capture.';
     reason='MPO ha bug noti con molti driver: interferisce con la cattura schermo e il DWM.';
     desc='Imposta OverlayTestMode=5 per disattivare MPO nel Desktop Window Manager.';
     impact='Elimina flickering/schermo nero in OBS, meno stutter sul desktop. Richiede riavvio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows\Dwm' 'OverlayTestMode') -eq 5){(Tw 'ok' 'Disabilitato')}else{(Tw 'todo' 'Attivo (da disabilitare)')} }; apply={ Do-Mpo } }
  @{ cat='gaming'; id='gpu_msi'; name='GPU: MSI mode ON (latenza DPC)';
     problem='La GPU usa interrupt line-based, che aumentano la latenza DPC e causano micro-stutter.';
     reason='I Message Signaled Interrupts (MSI) riducono la latenza di interrupt della GPU.';
     desc='Attiva MSISupported=1 nel ramo Interrupt Management della GPU (NVIDIA/AMD).';
     impact='Latenza DPC piu bassa, input piu reattivo. Richiede riavvio.';
     risk='safe';
     state={ $pnp=Get-GpuPnp; if($pnp){ $v=Get-RegVal "HKLM:\SYSTEM\CurrentControlSet\Enum\$pnp\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties" 'MSISupported'; if($v -eq 1){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da attivare')} }else{(Tw 'unknown' 'n/d')} }; apply={ Do-GpuMsi } }
  @{ cat='gaming'; id='amd_ulps'; name='AMD: disabilita ULPS';
     problem='Le Radeon abbassano troppo il clock in idle (Ultra Low Power State), causando stutter.';
     reason='ULPS mette la GPU in stato a bassissimo consumo, con risvegli lenti che generano scatti.';
     desc='Disattiva ULPS nelle chiavi di registro AMD (solo GPU AMD).';
     impact='Meno stutter e latenza su schede AMD, clock piu stabile.';
     risk='safe';
     fit={ if($script:HW.gpu -eq 'AMD'){'ok'}else{"skip:Solo GPU AMD (rilevata $($script:HW.gpu))"} };
     state={ if((Get-GpuVendor) -eq 'AMD'){(Tw 'todo' 'GPU AMD: applicabile')}else{(Tw 'na' 'Solo GPU AMD')} }; apply={ Do-AmdUlps } }
  @{ cat='gaming'; id='nvidia_tel'; name='NVIDIA: disabilita telemetria';
     problem='I driver NVIDIA installano task/servizi di telemetria che girano in background.';
     reason='La telemetria consuma CPU e rete senza alcun beneficio per il gaming.';
     desc='Disattiva i task pianificati e il servizio di telemetria NVIDIA (solo GPU NVIDIA).';
     impact='Meno processi in background, CPU leggermente piu libera.';
     risk='safe';
     fit={ if($script:HW.gpu -eq 'NVIDIA'){'ok'}else{"skip:Solo GPU NVIDIA (rilevata $($script:HW.gpu))"} };
     state={ if((Get-GpuVendor) -eq 'NVIDIA'){(Tw 'todo' 'GPU NVIDIA: applicabile')}else{(Tw 'na' 'Solo GPU NVIDIA')} }; apply={ Do-NvidiaTel } }
  @{ cat='gaming'; id='hibernate'; name='Disabilita ibernazione';
     problem='Il file hiberfil.sys occupa diversi GB di disco anche se non usi mai la sospensione.';
     reason='Su desktop l ibernazione e raramente usata; il file pesa quanto la RAM installata.';
     desc='Esegue powercfg -h off per rimuovere hiberfil.sys (reversibile con -h on).';
     impact='Libera 4-32 GB su disco. Perdi la sospensione ibrida/avvio rapido.';
     risk='caution';
     fit={ if($script:HW.laptop){'warn:Su laptop l ibernazione e utile a batteria scarica: disattivala solo se non la usi mai'}else{'ok'} };
     state={ (Tw 'todo' 'Applica per liberare spazio') }; apply={ Do-Hibernate } }
  # LATENZA & INPUT
  @{ cat='input'; id='mouse'; name='Accelerazione mouse OFF (raw input)';
     problem='L Enhance Pointer Precision di Windows accelera il mouse in modo imprevedibile.';
     reason='L accelerazione rende la mira incoerente: lo stesso movimento fisico da spostamenti diversi.';
     desc='Disattiva MouseSpeed/Threshold per un input 1:1 (raw).';
     impact='Mira piu precisa e costante negli sparatutto. Nessun rischio.';
     risk='safe';
     state={ if("$(Get-RegVal 'HKCU:\Control Panel\Mouse' 'MouseSpeed')" -eq '0'){(Tw 'ok' 'Gia disattivata')}else{(Tw 'todo' 'Attiva (da disattivare)')} }; apply={ Do-Mouse } }
  @{ cat='input'; id='timer'; name='Timer resolution globale';
     problem='Su Windows 11 la timer resolution puo essere variabile, con scheduling meno preciso.';
     reason='Una timer resolution alta e costante rende piu regolari i frametime e la latenza.';
     desc='Attiva GlobalTimerResolutionRequests=1 (richiesta timer globale).';
     impact='Frametime piu costante, meno stutter. Richiede riavvio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\kernel' 'GlobalTimerResolutionRequests') -eq 1){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da attivare')} }; apply={ Do-Timer } }
  @{ cat='input'; id='usb'; name='USB power management OFF';
     problem='Windows sospende le porte USB per risparmiare energia, causando cali di polling.';
     reason='Se il mouse/tastiera vanno in standby, si hanno input drop e micro-freeze.';
     desc='Disattiva il risparmio energetico sui controller USB.';
     impact='Input di mouse/tastiera piu stabile, niente drop. Nessun rischio.';
     risk='safe';
     fit={ if($script:HW.laptop){'warn:Su laptop aumenta il consumo della batteria: attiva solo se giochi collegato alla corrente'}else{'ok'} };
     state={ (Tw 'todo' 'Applica per input stabile') }; apply={ Do-Usb } }
  @{ cat='input'; id='stickykeys'; name='Sticky/Filter/Toggle Keys OFF';
     problem='Premendo Shift ripetutamente compare il popup delle Sticky Keys che ti butta fuori dal gioco.';
     reason='Le funzioni di accessibilita tastiera si attivano per errore durante il gioco.';
     desc='Disattiva Sticky/Filter/Toggle Keys.';
     impact='Niente piu popup che rubano il focus in game. Nessun rischio.';
     risk='safe';
     state={ if("$(Get-RegVal 'HKCU:\Control Panel\Accessibility\StickyKeys' 'Flags')" -eq '506'){(Tw 'ok' 'Disattivati')}else{(Tw 'todo' 'Attivi (da disattivare)')} }; apply={ Do-StickyKeys } }
  @{ cat='input'; id='startupdelay'; name='Startup delay app ridotto';
     problem='Windows ritarda artificialmente l avvio delle app in autostart.';
     reason='Il delay serve a non sovraccaricare l avvio, ma rallenta l accesso al desktop utile.';
     desc='Imposta StartupDelayInMSec=0 per avviare subito le app.';
     impact='Desktop e app pronti prima dopo l accensione. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize' 'StartupDelayInMSec') -eq 0){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-StartupDelay } }
  # RETE & STREAMING
  @{ cat='network'; id='network'; name='Rete: Nagle OFF + TCP tuning';
     problem='L algoritmo di Nagle accumula piccoli pacchetti, aggiungendo latenza nei giochi online.';
     reason='I giochi inviano tanti pacchetti piccoli: Nagle li ritarda, aumentando il ping percepito.';
     desc='Disattiva Nagle sulla scheda attiva e regola autotuning/ECN/RSS.';
     impact='Ping piu basso e stabile online. Reversibile con Ripristina.';
     risk='safe';
     state={ (Tw 'todo' 'Applica per meno lag online') }; apply={ Do-Network } }
  @{ cat='network'; id='dns'; name='DNS veloci (Cloudflare 1.1.1.1)';
     problem='I DNS del provider sono spesso lenti e possono rallentare la risoluzione dei domini.';
     reason='DNS piu veloci riducono i tempi di connessione a server di gioco e matchmaking.';
     desc='Imposta 1.1.1.1 / 1.0.0.1 sulla scheda attiva (reversibile a DHCP).';
     impact='Connessioni piu rapide. Reversibile in un click.';
     risk='safe';
     state={ $a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; if($a){ $d=(Get-DnsClientServerAddress -InterfaceAlias $a.Name -AddressFamily IPv4).ServerAddresses -join ','; if($d -match '1.1.1.1'){(Tw 'ok' 'Gia Cloudflare')}else{(Tw 'todo' "Attuale: $d")} }else{(Tw 'unknown' 'n/d')} }; apply={ Do-Dns } }
  @{ cat='network'; id='qos'; name='Rimuovi 20% banda riservata QoS';
     problem='Windows riserva fino al 20% della banda per il QoS di sistema.';
     reason='Recuperando quella banda hai piu throughput reale per download e streaming.';
     desc='Imposta NonBestEffortLimit=0.';
     impact='Piu banda disponibile per gioco/stream. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched' 'NonBestEffortLimit') -eq 0){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Qos } }
  @{ cat='network'; id='deliveryopt'; name='Delivery Optimization P2P OFF';
     problem='Windows usa la tua banda in upload per distribuire aggiornamenti ad altri PC (P2P).';
     reason='Durante lo streaming quell upload occupa banda e destabilizza il bitrate.';
     desc='Imposta DODownloadMode=0 (nessun P2P).';
     impact='Upload piu libero, stream piu stabile. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config' 'DODownloadMode') -eq 0){(Tw 'ok' 'Disattivato')}else{(Tw 'todo' 'Attivo (da disattivare)')} }; apply={ Do-DeliveryOpt } }
  @{ cat='network'; id='obs_priority'; name='OBS ad alta priorita';
     problem='OBS gira a priorita normale e puo perdere frame in encoding sotto carico.';
     reason='Alzando la priorita CPU di OBS l encoding resta fluido anche con la CPU occupata dal gioco.';
     desc='Imposta CpuPriorityClass alta per obs64/obs32.exe (via Image File Execution Options).';
     impact='Meno frame persi in registrazione/stream. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\obs64.exe\PerfOptions' 'CpuPriorityClass') -eq 3){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da attivare')} }; apply={ Do-ObsPriority } }
  # SISTEMA & DEBLOAT
  @{ cat='system'; id='clean'; name='Pulizia temp + cache Windows Update';
     problem='File temporanei e cache degli aggiornamenti si accumulano e occupano spazio.';
     reason='Ripulire libera disco e puo velocizzare alcune operazioni di sistema.';
     desc='Rimuove temp utente/sistema, cache Windows Update e svuota il DNS.';
     impact='Libera spazio su disco. Nessun file personale toccato.';
     risk='safe';
     state={ $mb=0; Get-ChildItem $env:TEMP -Recurse -File -Force 2>$null | ForEach-Object { $mb+=$_.Length }; (Tw 'todo' "$([math]::Round($mb/1MB)) MB da pulire") }; apply={ Do-Cleanup } }
  @{ cat='system'; id='visual'; name='Effetti visivi: modalita prestazioni';
     problem='Animazioni e trasparenze consumano GPU/CPU e rendono la UI meno reattiva.';
     reason='In modalita prestazioni Windows disattiva gli effetti superflui.';
     desc='Imposta VisualFXSetting=2 (prestazioni).';
     impact='UI piu snella e reattiva. Estetica leggermente piu spartana.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting') -eq 2){(Tw 'ok' 'Prestazioni')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Visual } }
  @{ cat='system'; id='telemetry'; name='Telemetria (DiagTrack) OFF';
     problem='Il servizio DiagTrack invia dati di diagnostica e gira sempre in background.';
     reason='Disattivarlo riduce l uso di CPU e rete senza impatti sulle funzioni essenziali.';
     desc='Ferma e disabilita il servizio DiagTrack (Connected User Experiences).';
     impact='Meno CPU/rete in background. NON tocca Defender ne la sicurezza.';
     risk='caution';
     state={ $s=Get-Service DiagTrack -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){(Tw 'todo' 'Attiva (da disattivare)')}else{(Tw 'ok' 'Disattivata')} }; apply={ Do-Telemetry } }
  @{ cat='system'; id='ads'; name='Suggerimenti/ads di Windows OFF';
     problem='Windows mostra app suggerite e contenuti promozionali nel menu Start e altrove.';
     reason='Sono distrazioni e consumano risorse per scaricare i contenuti suggeriti.';
     desc='Disattiva SilentInstalledApps, suggerimenti e Consumer Features.';
     impact='Start piu pulito, niente app installate a sorpresa. Nessun rischio.';
     risk='safe';
     state={ (Tw 'todo' 'Applica per rimuovere ads') }; apply={ Do-Ads } }
  @{ cat='system'; id='bgapps'; name='App in background OFF (globale)';
     problem='Le app UWP restano attive in background consumando CPU/RAM e rete.';
     reason='Bloccarle libera risorse per il gioco senza disinstallare nulla.';
     desc='Imposta GlobalUserDisabled=1 e LetAppsRunInBackground.';
     impact='Meno consumo di CPU/RAM in background. Alcune notifiche UWP potrebbero ritardare.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled') -eq 1){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-BgApps } }
  @{ cat='system'; id='gamebar_rec'; name='Xbox Game Bar recording OFF';
     problem='La Game Bar registra in background per la funzione clip, usando risorse.';
     reason='Se non usi le clip Xbox, la registrazione continua e uno spreco di CPU/GPU.';
     desc='Disattiva GameDVR_Enabled e AppCaptureEnabled.';
     impact='Meno overhead in game. Perdi la registrazione automatica Xbox.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' 'AppCaptureEnabled') -eq 0){(Tw 'ok' 'Disattivato')}else{(Tw 'todo' 'Attivo (da disattivare)')} }; apply={ Do-GamebarRec } }
  @{ cat='system'; id='debloat'; name='Debloat app superflue (UWP)';
     problem='Windows preinstalla app come Candy Crush, Solitaire, Bing, 3D Builder che non usi.';
     reason='Occupano spazio e alcune girano in background inutilmente.';
     desc='Rimuove una lista curata di app UWP (reinstallabili dallo Store).';
     impact='Sistema piu pulito. Puoi reinstallarle in qualsiasi momento dallo Store.';
     risk='caution';
     state={ $n=0; foreach($p in $script:BLOAT){ if(Get-AppxPackage -Name $p -ErrorAction SilentlyContinue){$n++} }; if($n -eq 0){(Tw 'ok' 'Nessuna app da rimuovere')}else{(Tw 'todo' "$n app rimovibili")} }; apply={ Do-Debloat } }
  @{ cat='system'; id='search_index'; name='Windows Search indexing OFF (invasivo)';
     problem='Il servizio di indicizzazione della ricerca puo generare carico su disco/CPU.';
     reason='Su alcuni PC l indicizzazione rallenta il sistema, ma serve alla ricerca file veloce.';
     desc='Ferma e disabilita il servizio WSearch.';
     impact='Meno carico su disco/CPU, MA la ricerca file diventa piu lenta. Reversibile.';
     risk='caution';
     state={ $s=Get-Service WSearch -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){(Tw 'todo' 'Attivo')}else{(Tw 'ok' 'Disattivato')} }; apply={ Do-SearchIndex } }
  # NUOVI TWEAK (motore adattivo)
  @{ cat='gaming'; id='fse'; name='Fullscreen Optimizations OFF';
     problem='Windows forza il fullscreen ottimizzato (borderless) invece del fullscreen esclusivo reale.';
     reason='Il fullscreen esclusivo bypassa il compositor DWM: input piu diretto e frametime piu pulito.';
     desc='Imposta FSEBehaviorMode=2 e HonorUserFSEBehavior nel GameConfigStore.';
     impact='Input lag ridotto nei giochi a schermo intero. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\System\GameConfigStore' 'GameDVR_FSEBehaviorMode') -eq 2){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Fse } }
  @{ cat='gaming'; id='power_throttling'; name='Power throttling CPU OFF';
     problem='Windows rallenta (throttla) i processi che considera poco importanti per risparmiare energia.';
     reason='A volte il throttling colpisce anche giochi, OBS o launcher, causando cali improvvisi.';
     desc='Imposta PowerThrottlingOff=1: nessun processo viene mai rallentato dal risparmio energetico.';
     impact='CPU sempre reattiva per giochi e streaming. Consuma un po piu di energia.';
     risk='safe';
     fit={ if($script:HW.laptop){'warn:Su laptop il power throttling risparmia batteria: attiva solo se giochi sempre collegato alla corrente'}else{'ok'} };
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling' 'PowerThrottlingOff') -eq 1){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-PowerThrottling } }
  @{ cat='gaming'; id='standby_clear'; name='Svuota RAM standby (azione istantanea)';
     problem='Windows tiene in RAM una cache standby che a volte non viene liberata abbastanza in fretta.';
     reason='Svuotare la standby list prima di giocare rende la memoria subito disponibile per il gioco.';
     desc='Purge della standby memory list via API di sistema (richiede Amministratore). Nessuna modifica permanente.';
     impact='RAM libera immediata prima della sessione di gioco. Azione una tantum, sempre sicura.';
     risk='safe';
     state={ $o=Get-CimInstance Win32_OperatingSystem; (Tw 'todo' "$([math]::Round($o.FreePhysicalMemory/1MB,1)) GB RAM libera ora") }; apply={ Clear-StandbyList } }
  @{ cat='network'; id='nic_power'; name='Scheda di rete a piena potenza';
     problem='Windows puo spegnere la scheda di rete per risparmiare energia e usa interrupt moderation che aggiunge latenza.';
     reason='Il risparmio energetico della NIC causa micro-disconnessioni; la moderazione degli interrupt ritarda i pacchetti.';
     desc='Disattiva il power saving della scheda attiva (PnPCapabilities=24) e la interrupt moderation.';
     impact='Ping piu stabile, niente drop di connessione in game. Richiede riavvio o riconnessione.';
     risk='safe';
     fit={ if($script:HW.laptop){'warn:Su laptop la scheda di rete sempre attiva consuma piu batteria'}else{'ok'} };
     state={ $a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; if(-not $a){(Tw 'unknown' 'n/d')}else{ $ok=$false; Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue | ForEach-Object { $p=Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue; if($p.NetCfgInstanceId -eq $a.InterfaceGuid -and $p.PnPCapabilities -eq 24){$ok=$true} }; if($ok){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} } }; apply={ Do-NicPower } }
  @{ cat='system'; id='paging_exec'; name='Kernel sempre in RAM (16GB+)';
     problem='Windows puo spostare parti del kernel e dei driver nel file di paging su disco.';
     reason='Con abbastanza RAM, tenere il kernel in memoria elimina micro-attese di paging.';
     desc='Imposta DisablePagingExecutive=1 in Memory Management.';
     impact='Sistema piu scattante sotto carico. Consigliato solo con 16 GB o piu.';
     risk='safe';
     fit={ if($script:HW.ram -ge 16){'ok'}else{"skip:Richiede almeno 16 GB di RAM (rilevati $($script:HW.ram) GB)"} };
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management' 'DisablePagingExecutive') -eq 1){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-PagingExec } }
  @{ cat='system'; id='sysmain'; name='SysMain/Superfetch OFF (solo SSD)';
     problem='SysMain precarica app in RAM analizzando l uso del disco: su SSD e superfluo e consuma CPU/disco.';
     reason='Gli SSD sono gia velocissimi in lettura casuale: il preload di SysMain non serve e genera carico.';
     desc='Ferma e disabilita il servizio SysMain (ex Superfetch).';
     impact='Meno attivita disco/CPU in background su SSD. Su HDD invece va lasciato attivo.';
     risk='caution';
     fit={ if($script:HW.ssd){'ok'}else{'skip:Solo con SSD: su HDD SysMain velocizza i caricamenti, meglio lasciarlo attivo'} };
     state={ $s=Get-Service SysMain -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){(Tw 'todo' 'Attivo (da disattivare)')}else{(Tw 'ok' 'Disattivato')} }; apply={ Do-SysMain } }
  @{ cat='system'; id='trim'; name='Verifica TRIM SSD attivo';
     problem='Se il TRIM e disattivato, l SSD rallenta progressivamente con l uso.';
     reason='Il TRIM permette all SSD di riorganizzare le celle libere mantenendo le prestazioni di scrittura.';
     desc='Esegue fsutil behavior set DisableDeleteNotify 0 (TRIM attivo).';
     impact='SSD sempre alla massima velocita nel tempo. Nessun rischio.';
     risk='safe';
     fit={ if($script:HW.ssd){'ok'}else{'skip:Solo per SSD: il TRIM non si applica agli HDD'} };
     state={ $q=(fsutil behavior query DisableDeleteNotify) -join ' '; if($q -match 'DisableDeleteNotify\s*=\s*0'){(Tw 'ok' 'TRIM attivo')}else{(Tw 'todo' 'Da attivare')} }; apply={ Do-Trim } }
  @{ cat='system'; id='ntfs'; name='NTFS: last-access timestamp OFF';
     problem='NTFS aggiorna la data di ultimo accesso di ogni file letto, generando scritture inutili.';
     reason='Disattivarlo riduce le scritture su disco a ogni lettura di file (utile anche per la vita dell SSD).';
     desc='Esegue fsutil behavior set disablelastaccess 1 (con backup del valore precedente).';
     impact='Meno I/O su disco nelle operazioni quotidiane. Nessun rischio.';
     risk='safe';
     state={ $q=(fsutil behavior query disablelastaccess) -join ' '; if($q -match '=\s*[13]'){(Tw 'ok' 'Attivo')}else{(Tw 'todo' 'Da ottimizzare')} }; apply={ Do-Ntfs } }
  @{ cat='system'; id='edge_preload'; name='Edge preload/background OFF';
     problem='Microsoft Edge si precarica all avvio e resta in background anche se non lo usi.';
     reason='Lo startup boost di Edge occupa RAM e CPU all accensione per un browser che magari non apri mai.';
     desc='Imposta StartupBoostEnabled=0 e BackgroundModeEnabled=0 via policy.';
     impact='Avvio piu pulito e RAM libera se non usi Edge. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Policies\Microsoft\Edge' 'StartupBoostEnabled') -eq 0){(Tw 'ok' 'Disattivato')}else{(Tw 'todo' 'Attivo (da disattivare)')} }; apply={ Do-EdgePreload } }
)

$script:PRESETS = @{
  'competitivo' = @('power','gaming','priority','mpo','gpu_msi','amd_ulps','nvidia_tel','fse','power_throttling','standby_clear','mouse','timer','usb','stickykeys','network','nic_power','qos','visual','bgapps','paging_exec','ntfs')
  'streaming'   = @('power','gaming','priority','mpo','gpu_msi','amd_ulps','nvidia_tel','fse','network','dns','nic_power','qos','deliveryopt','obs_priority','telemetry','ads','bgapps','gamebar_rec','edge_preload','paging_exec')
}

# ---------------- Restore ----------------
# v0.7.7: logica per-chiave estratta da Invoke-Restore per il revert granulare.
function Restore-OneKey($k, $v) {
  if ($k -eq '__tweak_keys__') { return }
  if ($k -eq 'power_plan') { if ($v) { powercfg -setactive $v 2>$null }; return }
  if ($k -eq 'hib') { powercfg -h on 2>$null; return }
  if ($k.StartsWith('svc::')) {
    $svcName = $k.Substring(5); $st = "$v"
    $mode = switch -Wildcard ($st) { 'Auto*' {'Automatic'} 'Manual' {'Manual'} 'Disabled' {'Disabled'} default {'Manual'} }
    Set-Service $svcName -StartupType $mode 2>$null
    if ($mode -ne 'Disabled') { Start-Service $svcName 2>$null }
    return
  }
  if ($k -eq 'ntfs::lastaccess') { fsutil behavior set disablelastaccess ([int]$v) 2>$null | Out-Null; return }
  if ($k.StartsWith('dns::')) { Set-DnsClientServerAddress -InterfaceAlias $k.Substring(5) -ResetServerAddresses 2>$null; return }
  $parts = $k -split '::', 2
  if ($parts.Count -ne 2) { return }
  $path = $parts[0]; $name = $parts[1]
  if ($v -eq '__ABSENT__') { Remove-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue }
  else {
    $tv = "$v" -split '\|', 2; $tp = $tv[0]; $vv = $tv[1]
    if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    if ($tp -eq 'DWord') { New-ItemProperty -Path $path -Name $name -PropertyType DWord -Value ([int64]$vv) -Force | Out-Null }
    else { New-ItemProperty -Path $path -Name $name -PropertyType String -Value $vv -Force | Out-Null }
  }
}

# v0.7.7: ripristina SOLO le chiavi di backup create da un singolo tweak.
function Invoke-RestoreTweak($id) {
  if (-not $script:TWKEYS.ContainsKey($id)) { return 'Nessun backup per questo tweak.' }
  $keys = @($script:TWKEYS[$id])
  foreach ($k in $keys) {
    if ($script:BK.ContainsKey($k)) { Restore-OneKey $k $script:BK[$k]; $script:BK.Remove($k) }
  }
  $script:TWKEYS.Remove($id)
  $script:TWAT.Remove($id)
  if ($id -eq 'network') { netsh int tcp set global autotuninglevel=normal 2>$null | Out-Null }
  Save-Backup
  return 'Tweak ripristinato al valore precedente.'
}

function Invoke-Restore {
  # v0.7.3+: legge anche dal file legacy se il nuovo non esiste
  $__rf = if (Test-Path $BACKUP) { $BACKUP } elseif (Test-Path $BACKUP_LEGACY) { $BACKUP_LEGACY } else { '' }
  if (-not $__rf) { return 'Nessun backup trovato.' }
  $b = Get-Content $__rf -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe
  foreach ($k in $b.Keys) {
    if ($k -eq '__tweak_keys__') { continue }
    Restore-OneKey $k $b[$k]
  }
  netsh int tcp set global autotuninglevel=normal 2>$null | Out-Null
  Remove-Item $BACKUP -ErrorAction SilentlyContinue
  Remove-Item $BACKUP_LEGACY -ErrorAction SilentlyContinue
  $script:BK = @{}
  $script:TWKEYS = @{}
  return 'Impostazioni ripristinate ai valori precedenti.'
}

# ---------------- Modern Web GUI (Edge --app + local HTTP server) ----------------
function Show-WebGui {
  # v0.7.7: trova un browser Chromium (Edge/Chrome/Brave, anche installazioni per-utente
  # o via registry App Paths). Se non c'e', fallback al browser predefinito.
  $script:GUI_BROWSER_FALLBACK = $false
  $candidates = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe",
    "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe"
  )
  $edgeExe = $null
  foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { $edgeExe = $c; break } }
  if (-not $edgeExe) {
    foreach ($reg in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe',
                       'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe')) {
      try {
        $p = (Get-ItemProperty -Path $reg -ErrorAction SilentlyContinue).'(default)'
        if ($p -and (Test-Path $p)) { $edgeExe = $p; break }
      } catch {}
    }
  }
  if (-not $edgeExe) {
    Say-Info 'Nessun browser Edge/Chrome trovato: apro la GUI nel browser predefinito.'
    $script:GUI_BROWSER_FALLBACK = $true
  }

  $isAdmin = Test-Admin

  # Prepara mappe tweak / fit
  $script:TWMAP = @{}
  foreach ($t in $script:TWEAKS) { $script:TWMAP[$t.id] = $t }
  $script:FITMAP = @{}
  foreach ($t in $script:TWEAKS) { $f = 'ok'; if ($t.fit) { $f = & $t.fit }; if (-not $f) { $f = 'ok' }; $script:FITMAP[$t.id] = $f }
  $script:WEBLOG = New-Object System.Collections.ArrayList
  $script:APPLYING = $false
  $script:LIVE_SYNC = $false
  $script:LIVE_LAST_TS = 0

  # Session token random per gli endpoint locali
  $chars = [char[]](([byte][char]"A"..[byte][char]"Z") + ([byte][char]"a"..[byte][char]"z") + ([byte][char]"0"..[byte][char]"9"))
  $sessionToken = -join (1..48 | ForEach-Object { $chars | Get-Random })

  # Trova porta libera su localhost
  $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
  $probe.Start(); $port = ($probe.LocalEndpoint).Port; $probe.Stop()

  # Avvia listener SOLO su 127.0.0.1
  $listener = New-Object System.Net.HttpListener
  $listener.Prefixes.Add("http://127.0.0.1:$port/")
  try { $listener.Start() } catch { Say-Warn ("Server GUI locale non avviabile: {0}" -f $_.Exception.Message); return $false }

  function WebLog($m) { [void]$script:WEBLOG.Add(@{ ts=(Get-Date).ToString("HH:mm:ss"); msg=$m }) }
  function Send-Json { param($ctx, $obj, [int]$status=200)
    $json = $obj | ConvertTo-Json -Depth 8 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $ctx.Response.StatusCode = $status
    $ctx.Response.ContentType = "application/json; charset=utf-8"
    $ctx.Response.Headers.Add("Cache-Control","no-store")
    $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $ctx.Response.OutputStream.Close()
  }
  function Send-Html { param($ctx, $html)
    $bytes = [Text.Encoding]::UTF8.GetBytes($html)
    $ctx.Response.StatusCode = 200
    $ctx.Response.ContentType = "text/html; charset=utf-8"
    $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $ctx.Response.OutputStream.Close()
  }
  function Read-Body($ctx) {
    $sr = New-Object System.IO.StreamReader($ctx.Request.InputStream, [Text.Encoding]::UTF8)
    $body = $sr.ReadToEnd(); $sr.Close(); return $body
  }
  function Check-Auth($ctx, $sess) {
    $tk = $ctx.Request.QueryString["tk"]
    if (-not $tk) { $tk = $ctx.Request.Headers["X-FF-Token"] }
    return ($tk -eq $sess)
  }
  function Show-DeviceToast($device) {
    # Native Windows toast for "new device connected" magic-link cross-device scan.
    # Fire in a background thread so the HTTP handler returns instantly.
    $title = 'FrameForge - Nuovo device connesso'
    $body  = "$device ha effettuato l'accesso al tuo account tramite QR"
    try {
      Start-Job -ScriptBlock {
        param($t, $b)
        try {
          if (Get-Command -Name New-BurntToastNotification -ErrorAction SilentlyContinue) {
            New-BurntToastNotification -Text $t, $b | Out-Null
            return
          }
        } catch {}
        try {
          Add-Type -AssemblyName System.Windows.Forms | Out-Null
          $ni = New-Object System.Windows.Forms.NotifyIcon
          $ni.Icon = [System.Drawing.SystemIcons]::Information
          $ni.BalloonTipTitle = $t
          $ni.BalloonTipText  = $b
          $ni.Visible = $true
          $ni.ShowBalloonTip(6000)
          Start-Sleep -Seconds 7
          $ni.Visible = $false
          $ni.Dispose()
        } catch {}
      } -ArgumentList $title, $body | Out-Null
    } catch {}
  }
  function Get-TweakDto {
    $arr = @()
    foreach ($t in $script:TWEAKS) {
      $fit = $script:FITMAP[$t.id]
      $skip = $fit -like "skip:*"; $warn = $fit -like "warn:*"; $note = $fit -like "note:*"
      $hint = ""; if ($skip -or $warn -or $note) { $hint = ($fit -split ":", 2)[1] }
      $st = Get-TwState $t
      $arr += @{
        id = $t.id; cat = $t.cat; name = $t.name; problem = $t.problem
        reason = $t.reason; desc = $t.desc; impact = $t.impact; risk = $t.risk
        # `state` resta il testo per l'utente, `state_code` e' quello su cui la
        # GUI decide colore e conteggi: prima li deduceva dal testo con una regex.
        state = $st.label; state_code = $st.code
        fit = @{ ok = (-not $skip); warn = [bool]$warn; note = [bool]$note; skip = [bool]$skip; hint = $hint }
      }
    }
    return $arr
  }

  # HTML della GUI (in singola-quote here-string: nessuna $-expansion PS; JS usa " e backtick)
  $html = @'
__GUI_HTML__
'@
  $html = $html.Replace('__TOKEN__', $sessionToken)

  # Directory temp per il profilo Edge (isolato)
  $tmpDir = Join-Path $env:TEMP "forgefps-gui"
  if (-not (Test-Path $tmpDir)) { New-Item -ItemType Directory -Path $tmpDir | Out-Null }
  $profileDir = Join-Path $tmpDir 'edge-profile'

  # Niente token nell'URL: la pagina `/` viene servita senza controllo (il token
  # e' gia' dentro l'HTML, sostituito qui sotto), quindi in barra degli indirizzi
  # non serviva a nulla — ci finiva soltanto, e da li' nella cronologia del
  # browser e sotto gli occhi di qualsiasi estensione con accesso alle schede.
  $localUrl = "http://127.0.0.1:$port/"
  Say-Step "GUI locale su $localUrl"
  Say "       (se la finestra non si apre, incolla l'URL sopra in un browser)" 'DarkGray'

  # Lancia Edge in modalita app (chromeless)
  $edgeArgs = @(
    "--app=$localUrl",
    "--user-data-dir=`"$profileDir`"",
    "--window-size=1280,860",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-features=Translate,BackForwardCache"
  )
  try {
    if ($script:GUI_BROWSER_FALLBACK) {
      $edge = $null
      Start-Process $localUrl | Out-Null
    } else {
      $edge = Start-Process -FilePath $edgeExe -ArgumentList $edgeArgs -PassThru
    }
  } catch {
    # Ultimo tentativo: browser predefinito
    try { $edge = $null; Start-Process $localUrl | Out-Null }
    catch { Say-Warn ("Impossibile aprire il browser: {0}" -f $_.Exception.Message); try { $listener.Stop() } catch {}; return $false }
  }

  # Il launcher msedge.exe fa "hop and exit" se c'e' gia' un'istanza Edge attiva.
  # Cerco il process reale (quello con il nostro user-data-dir) dopo un breve wait.
  Start-Sleep -Milliseconds 1800
  $realEdge = $null
  if (-not $script:GUI_BROWSER_FALLBACK) {
    $browserName = [System.IO.Path]::GetFileName($edgeExe)
    try {
      $procs = Get-CimInstance Win32_Process -Filter "Name='$browserName'" -ErrorAction SilentlyContinue
      foreach ($p in $procs) {
        if ($p.CommandLine -and $p.CommandLine -like "*$profileDir*") {
          $realEdge = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
          break
        }
      }
    } catch {}
  }
  if (-not $realEdge -and $edge -and -not $edge.HasExited) { $realEdge = $edge }
  # Se ancora non c'e' un process vivo, uso un inactivity timeout come safety net.

  # Loop richieste (async con timeout per rilevare chiusura Edge)
  $ar = $listener.BeginGetContext($null, $null)
  $lastActivity = Get-Date
  while ($listener.IsListening) {
    # Uscita: se ho un process reale e non e' piu' attivo, oppure inattivita' > 30s
    $edgeAlive = if ($realEdge) { -not $realEdge.HasExited } else { ((Get-Date) - $lastActivity).TotalSeconds -lt 30 }
    if (-not $edgeAlive) { break }
    if ($ar.AsyncWaitHandle.WaitOne(180)) {
      try {
        $ctx = $listener.EndGetContext($ar)
      } catch { break }
      $ar = $listener.BeginGetContext($null, $null)
      $lastActivity = Get-Date
      $req = $ctx.Request
      $path = $req.Url.AbsolutePath
      $method = $req.HttpMethod
      try {
        if ($path -eq '/' -or $path -eq '/index.html') {
          Send-Html $ctx $html
        }
        elseif (-not (Check-Auth $ctx $sessionToken)) {
          Send-Json $ctx @{ err = 'auth' } 401
        }
        elseif ($path -eq '/api/state' -and $method -eq 'GET') {
          $dto = @{
            hw = $script:HW; admin = $isAdmin; backup = $script:BK.Count
            backup_ids = (Get-BackupIds)
            revertable = (Get-RevertableIds)
            agent = @{ installed = $INSTALLED_VER; latest = $LATEST_VER; dl = $AGENT_DL_URL }
            tweaks = Get-TweakDto
            presets = @{
              competitive = @($script:PRESETS.competitivo)
              streaming   = @($script:PRESETS.streaming)
              complete    = @($script:TWEAKS | ForEach-Object { $_.id })
            }
          }
          Send-Json $ctx $dto
        }
        elseif ($path -eq '/api/log' -and $method -eq 'GET') {
          $since = 0; try { $since = [int]$req.QueryString['since'] } catch {}
          $slice = @()
          if ($script:WEBLOG.Count -gt $since) {
            $slice = @($script:WEBLOG.GetRange($since, $script:WEBLOG.Count - $since))
          }
          # Opportunistic live-telemetry push (throttled 3s).
          if ($script:LIVE_SYNC) {
            $now = [int](Get-Date -UFormat %s)
            if (($now - $script:LIVE_LAST_TS) -ge 3) {
              $script:LIVE_LAST_TS = $now
              try { Push-LiveSample } catch {}
            }
          }
          Send-Json $ctx @{ logs = $slice; total = $script:WEBLOG.Count; applying = $script:APPLYING; live_sync = $script:LIVE_SYNC }
        }
        elseif ($path -eq '/api/apply' -and $method -eq 'POST') {
          $body = Read-Body $ctx | ConvertFrom-Json
          $script:APPLYING = $true
          $ids = @($body.ids)
          $bench = [bool]$body.benchmark
          $before = $null; $after = $null
          if ($bench) { WebLog 'Benchmark PRIMA in corso...'; $before = Run-Benchmark; WebLog ("  Performance Score PRIMA: {0}" -f $before.overall) }
          foreach ($id in $ids) {
            $t = $script:TWMAP[$id]; if (-not $t) { continue }
            WebLog ("-> {0}" -f $t.name); Invoke-ApplyTracked $t
          }
          Save-Backup
          if ($bench) {
            WebLog 'Benchmark DOPO in corso...'; $after = Run-Benchmark
            $pct = 0; if ($before.overall) { $pct = [math]::Round(($after.overall - $before.overall) / $before.overall * 100) }
            WebLog ("  Performance Score DOPO: {0}  (variazione {1}%)" -f $after.overall, $pct)
            Send-Benchmark @{ before = $before; after = $after; ts = (Get-Date).ToString('o') }
          }
          Send-Data (Get-Specs) (Get-Health) (Get-StartupList)
          WebLog '[ OK ] Ottimizzazioni applicate. Dati inviati a FrameForge. Riavvio consigliato.'
          $script:APPLYING = $false
          Send-Json $ctx @{ ok = $true; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = (Get-BackupIds); revertable = (Get-RevertableIds); before = $before; after = $after }
        }
        elseif ($path -eq '/api/apply-one' -and $method -eq 'POST') {
          $body = Read-Body $ctx | ConvertFrom-Json
          $t = $script:TWMAP[$body.id]
          if ($t) { WebLog ("-> {0}" -f $t.name); Invoke-ApplyTracked $t; Save-Backup }
          Send-Json $ctx @{ ok = $true; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = (Get-BackupIds); revertable = (Get-RevertableIds) }
        }
        elseif ($path -eq '/api/changes' -and $method -eq 'GET') {
          # Cronologia delle modifiche fatte da FrameForge su questo PC.
          # Il dato c'era gia' tutto nel file di backup: cosa e' stato cambiato,
          # con che valore precedente, e da quale tweak. Mancava solo un posto
          # dove leggerlo — il log della GUI vive in memoria e muore con la
          # finestra, quindi "cosa mi ha toccato e come lo annullo" non era
          # rispondibile da nessuna parte.
          $items = @()
          foreach ($id in @($script:TWKEYS.Keys)) {
            $tw = $script:TWMAP[$id]
            $keys = @()
            foreach ($k in @($script:TWKEYS[$id])) {
              $prev = "$($script:BK[$k])"
              $parts = $prev.Split('|', 2)
              $keys += @{
                key = "$k"
                previous = if ($prev -eq '__ABSENT__') { 'non esisteva' } else { $parts[-1] }
              }
            }
            $items += @{
              id = "$id"
              name = if ($tw) { $tw.name } else { "$id" }
              cat = if ($tw) { $tw.cat } else { '' }
              applied_at = "$($script:TWAT[$id])"
              keys = $keys
            }
          }
          Send-Json $ctx @{ ok = $true; items = $items; backup_file = "$BACKUP" }
        }
        elseif ($path -eq '/api/restore-one' -and $method -eq 'POST') {
          # v0.7.7: revert granulare di un singolo tweak dalle chiavi tracciate
          $body = Read-Body $ctx | ConvertFrom-Json
          $t = $script:TWMAP[$body.id]
          $tname = if ($t) { $t.name } else { "$($body.id)" }
          WebLog ("Ripristino singolo tweak: {0}" -f $tname)
          $msg = Invoke-RestoreTweak "$($body.id)"
          WebLog ('  ' + $msg)
          Send-Json $ctx @{ ok = $true; message = $msg; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = (Get-BackupIds); revertable = (Get-RevertableIds) }
        }
        elseif ($path -eq '/api/telemetry-local' -and $method -eq 'GET') {
          # v0.7.7: sample telemetria per il pannello Monitor Live della GUI
          $s = Get-TelemetrySample
          Send-Json $ctx $s
        }
        elseif ($path -eq '/api/bloatware' -and $method -eq 'GET') {
          # v0.7.7: auto-discovery bloatware (curated list + pattern OEM/promo)
          $apps = Get-BloatCandidates
          Send-Json $ctx @{ apps = $apps }
        }
        elseif ($path -eq '/api/bloatware/remove' -and $method -eq 'POST') {
          $body = Read-Body $ctx | ConvertFrom-Json
          $names = @($body.names)
          $removed = 0
          foreach ($n in $names) {
            $n = "$n"
            if (-not $n -or (Test-BloatProtected $n)) { continue }
            $app = Get-AppxPackage -Name $n -ErrorAction SilentlyContinue
            if ($app) {
              WebLog ("Rimuovo bloatware: {0}" -f $n)
              $app | Remove-AppxPackage -ErrorAction SilentlyContinue
              if (-not (Get-AppxPackage -Name $n -ErrorAction SilentlyContinue)) { $removed++ }
            }
          }
          WebLog ("[ OK ] Bloatware: {0}/{1} app rimosse (reinstallabili dallo Store)." -f $removed, $names.Count)
          Send-Json $ctx @{ ok = $true; removed = $removed; apps = (Get-BloatCandidates) }
        }
        elseif ($path -eq '/api/client-error' -and $method -eq 'POST') {
          # GUI v3.1: gli errori JS della GUI finiscono nel log visibile (debug remoto)
          try { $cerr = Read-Body $ctx | ConvertFrom-Json; WebLog ("[GUI-ERROR] " + $cerr.msg) } catch {}
          Send-Json $ctx @{ ok = $true }
        }
        elseif ($path -eq '/api/reboot' -and $method -eq 'POST') {
          # v0.7.7 fix: il bottone 'Riavvia ora' puntava a un endpoint inesistente (404)
          WebLog 'Riavvio del PC tra 5 secondi...'
          Send-Json $ctx @{ ok = $true }
          shutdown /r /t 5 /c "FrameForge: riavvio per attivare le ottimizzazioni" 2>$null
        }
        elseif ($path -eq '/api/profiles-cloud' -and $method -eq 'GET') {
          # Proxy to FrameForge cloud: /api/agent/profiles (X-Agent-Token auth).
          try {
            $resp = Invoke-RestMethod -Uri "$BACKEND/api/agent/profiles" -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -TimeoutSec 8
            Send-Json $ctx $resp
          } catch {
            Send-Json $ctx @{ err = "cloud unreachable"; profiles = @(); templates = @(); catalog = @() }
          }
        }
        elseif ($path -eq '/api/live-sync' -and $method -eq 'POST') {
          # Toggle live telemetry stream to cloud on/off.
          $body = Read-Body $ctx | ConvertFrom-Json
          $script:LIVE_SYNC = [bool]$body.enabled
          Send-Json $ctx @{ ok = $true; enabled = $script:LIVE_SYNC }
        }
        elseif ($path -eq '/api/mobile-handoff/generate' -and $method -eq 'POST') {
          # Proxy to cloud: generate a 5-min single-use magic-link for mobile QR handoff.
          try {
            $resp = Invoke-RestMethod -Uri "$BACKEND/api/agent/magic-link" -Method Post -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -TimeoutSec 10
            Send-Json $ctx $resp
          } catch {
            $code = try { [int]$_.Exception.Response.StatusCode.value__ } catch { 0 }
            if ($code -eq 429) { Send-Json $ctx @{ err = 'rate_limited' } 429 }
            else { Send-Json $ctx @{ err = 'cloud_unreachable' } 502 }
          }
        }
        elseif ($path -eq '/api/mobile-handoff/qr' -and $method -eq 'GET') {
          # Proxy to cloud: fetch QR SVG for the magic token.
          $magic = $req.QueryString['token']
          if ([string]::IsNullOrWhiteSpace($magic)) { $ctx.Response.StatusCode = 400; $ctx.Response.Close() }
          else {
            try {
              # NOTA: Invoke-RestMethod auto-parsa image/svg+xml come [xml] object e
              # perde il markup. Usiamo Invoke-WebRequest -UseBasicParsing per ottenere
              # i bytes raw del SVG e inoltrarli intatti al browser.
              $resp = Invoke-WebRequest -Uri "$BACKEND/api/agent/magic-qr?token=$([Uri]::EscapeDataString($magic))" -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -TimeoutSec 10 -UseBasicParsing
              $bytes = if ($resp.RawContentStream) { $resp.RawContentStream.ToArray() } else { [System.Text.Encoding]::UTF8.GetBytes([string]$resp.Content) }
              $ctx.Response.ContentType = 'image/svg+xml'
              $ctx.Response.Headers.Add('Cache-Control','no-store')
              $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
              $ctx.Response.Close()
            } catch { $ctx.Response.StatusCode = 502; $ctx.Response.Close() }
          }
        }
        elseif ($path -eq '/api/mobile-handoff/status' -and $method -eq 'GET') {
          # Public poll: has the magic link been consumed yet?
          $magic = $req.QueryString['magic']
          if ([string]::IsNullOrWhiteSpace($magic)) { Send-Json $ctx @{ err = 'missing_token' } 400 }
          else {
            try {
              $resp = Invoke-RestMethod -Uri "$BACKEND/api/auth/magic-status/$([Uri]::EscapeDataString($magic))" -TimeoutSec 6
              Send-Json $ctx $resp
            } catch { Send-Json $ctx @{ err = 'cloud_unreachable' } 502 }
          }
        }
        elseif ($path -eq '/api/mobile-handoff/notify' -and $method -eq 'POST') {
          # Fire a native Windows toast notification (BurntToast if available, else balloon).
          $device = $req.QueryString['device']; if ([string]::IsNullOrWhiteSpace($device)) { $device = 'Dispositivo' }
          try { Show-DeviceToast $device } catch {}
          Send-Json $ctx @{ ok = $true }
        }
        elseif ($path -eq '/api/restore' -and $method -eq 'POST') {
          WebLog 'Ripristino dal backup...'; $msg = Invoke-Restore; WebLog ('  ' + $msg)
          Send-Json $ctx @{ ok = $true; message = $msg; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = (Get-BackupIds); revertable = (Get-RevertableIds) }
        }
        elseif ($path -eq '/api/close') {
          Send-Json $ctx @{ ok = $true }
          try { if ($realEdge -and -not $realEdge.HasExited) { $realEdge.CloseMainWindow() | Out-Null } } catch {}
          break
        }
        elseif ($path -eq '/api/logout' -and $method -eq 'POST') {
          # Rimuove il token persistente (%APPDATA%\FrameForge\token.dat) e chiude la GUI.
          # Al prossimo doppio-click sull'.exe verra' richiesto un nuovo token.
          $removed = $false
          try {
            $tokFile = Join-Path $env:APPDATA 'FrameForge\token.dat'
            if (Test-Path $tokFile) { Remove-Item $tokFile -Force -ErrorAction SilentlyContinue; $removed = $true }
          } catch {}
          WebLog ('Token rimosso dal PC. Al prossimo avvio l''agent chiedera'' un nuovo token.')
          Send-Json $ctx @{ ok = $true; removed = $removed }
          Start-Sleep -Milliseconds 500
          try { if ($realEdge -and -not $realEdge.HasExited) { $realEdge.CloseMainWindow() | Out-Null } } catch {}
          break
        }
        else {
          $ctx.Response.StatusCode = 404; $ctx.Response.Close()
        }
      } catch {
        try { Send-Json $ctx @{ err = $_.ToString() } 500 } catch {}
      }
    }
  }
  try { $listener.Stop() } catch {}
  try { $listener.Close() } catch {}
  return $true
}

# ---------------- GUI (legacy WinForms fallback) ----------------
function Show-Gui {
  try { Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing } catch { return $false }
  [System.Windows.Forms.Application]::EnableVisualStyles()
  $isAdmin = Test-Admin

  $bg     = [System.Drawing.Color]::FromArgb(9,9,11)
  $bg2    = [System.Drawing.Color]::FromArgb(13,13,16)
  $cardBg = [System.Drawing.Color]::FromArgb(18,18,22)
  $acc    = [System.Drawing.Color]::FromArgb(229,255,0)
  $green  = [System.Drawing.Color]::FromArgb(0,255,102)
  $red    = [System.Drawing.Color]::FromArgb(255,59,48)
  $orange = [System.Drawing.Color]::FromArgb(255,170,0)
  $blue   = [System.Drawing.Color]::FromArgb(0,224,255)
  $gray   = [System.Drawing.Color]::FromArgb(150,150,160)
  $light  = [System.Drawing.Color]::FromArgb(220,220,225)
  $white  = [System.Drawing.Color]::White

  $script:TWMAP = @{}
  foreach ($t in $script:TWEAKS) { $script:TWMAP[$t.id] = $t }
  $script:FITMAP = @{}
  foreach ($t in $script:TWEAKS) { $f = 'ok'; if ($t.fit) { $f = & $t.fit }; if (-not $f) { $f = 'ok' }; $script:FITMAP[$t.id] = $f }
  $script:CHECKS = @{}
  $script:STATUS = @{}

  $form = New-Object System.Windows.Forms.Form
  $form.Text = 'FrameForge Agent - Ottimizzazioni'
  $form.Size = New-Object System.Drawing.Size(800, 962)
  $form.StartPosition = 'CenterScreen'
  $form.BackColor = $bg; $form.ForeColor = $white
  $form.Font = New-Object System.Drawing.Font('Segoe UI', 9)

  # ---- Header ----
  $head = New-Object System.Windows.Forms.Panel
  $head.Location = New-Object System.Drawing.Point(0, 0); $head.Size = New-Object System.Drawing.Size(800, 150); $head.BackColor = $bg2
  $form.Controls.Add($head)

  $bolt = New-Object System.Windows.Forms.Label
  $bolt.Text = 'FRAMEFORGE AGENT'; $bolt.ForeColor = $acc
  $bolt.Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
  $bolt.Location = New-Object System.Drawing.Point(18, 12); $bolt.AutoSize = $true
  $head.Controls.Add($bolt)

  $sub = New-Object System.Windows.Forms.Label
  $sub.Text = 'Trova i colli di bottiglia. Ottimizza in sicurezza.'; $sub.ForeColor = $gray
  $sub.Location = New-Object System.Drawing.Point(20, 46); $sub.AutoSize = $true
  $head.Controls.Add($sub)

  $sec = New-Object System.Windows.Forms.Label
  $sec.Text = "SICUREZZA  -  Non tocchiamo mai Windows Defender, Firewall o servizi di sicurezza. Ogni modifica ha un backup automatico ed e reversibile."
  $sec.ForeColor = $green; $sec.Location = New-Object System.Drawing.Point(20, 70)
  $sec.MaximumSize = New-Object System.Drawing.Size(760, 0); $sec.AutoSize = $true
  $head.Controls.Add($sec)

  $hwLbl = New-Object System.Windows.Forms.Label
  $hwLbl.Text = ("PC RILEVATO: {0}  |  GPU {1}  |  RAM {2} GB  |  {3}{4}   ->  tweak adattati automaticamente al tuo hardware" -f $(if($script:HW.laptop){'Laptop'}else{'Desktop'}), $script:HW.gpu, $script:HW.ram, $(if($script:HW.ssd){'SSD'}else{'HDD'}), $(if($script:HW.win11){'  |  Win 11'}else{''}))
  $hwLbl.ForeColor = $blue; $hwLbl.Location = New-Object System.Drawing.Point(20, 100); $hwLbl.AutoSize = $true
  $head.Controls.Add($hwLbl)

  $adminLbl = New-Object System.Windows.Forms.Label
  $adminLbl.Location = New-Object System.Drawing.Point(20, 124); $adminLbl.AutoSize = $true
  if ($isAdmin) { $adminLbl.Text = 'Amministratore: SI - tutte le ottimizzazioni disponibili.'; $adminLbl.ForeColor = $green }
  else { $adminLbl.Text = 'Amministratore: NO - alcune opzioni non verranno applicate. Usa "Riavvia come Amministratore" in basso.'; $adminLbl.ForeColor = $red }
  $head.Controls.Add($adminLbl)

  $bkLbl = New-Object System.Windows.Forms.Label
  $bkLbl.ForeColor = $blue; $bkLbl.Location = New-Object System.Drawing.Point(470, 124); $bkLbl.AutoSize = $true
  $head.Controls.Add($bkLbl); $script:BKLBL = $bkLbl

  # ---- Preset row ----
  $presetLbl = New-Object System.Windows.Forms.Label
  $presetLbl.Text = 'Preset rapidi:'; $presetLbl.Location = New-Object System.Drawing.Point(18, 160); $presetLbl.AutoSize = $true; $presetLbl.ForeColor = $gray
  $form.Controls.Add($presetLbl)
  function New-Preset($text, $x, $key) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text; $b.Location = New-Object System.Drawing.Point($x, 180); $b.Size = New-Object System.Drawing.Size(170, 32)
    $b.FlatStyle = 'Flat'; $b.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(42,42,53)
    $b.ForeColor = $white; $b.BackColor = [System.Drawing.Color]::FromArgb(28,28,36)
    $b.Tag = $key
    $b.Add_Click({
      $k = $this.Tag
      foreach ($t in $script:TWEAKS) {
        if ($script:FITMAP[$t.id] -like 'skip:*') { $script:CHECKS[$t.id].Checked = $false; continue }
        if ($k -eq 'completo') { $script:CHECKS[$t.id].Checked = $true }
        else { $script:CHECKS[$t.id].Checked = ($script:PRESETS[$k] -contains $t.id) }
      }
    })
    $form.Controls.Add($b)
  }
  New-Preset 'Competitivo' 120 'competitivo'
  New-Preset 'Streaming' 300 'streaming'
  New-Preset 'Completo' 480 'completo'

  # ---- log (defined early so GuiLog works in handlers) ----
  $out = New-Object System.Windows.Forms.TextBox
  $out.Multiline = $true; $out.ReadOnly = $true; $out.ScrollBars = 'Vertical'
  $out.Location = New-Object System.Drawing.Point(16, 658); $out.Size = New-Object System.Drawing.Size(760, 150)
  $out.BackColor = [System.Drawing.Color]::Black; $out.ForeColor = $green
  $out.Font = New-Object System.Drawing.Font('Consolas', 9); $out.BorderStyle = 'FixedSingle'
  $form.Controls.Add($out); $script:OUT = $out
  function GuiLog($m) { $script:OUT.AppendText("$m`r`n"); [System.Windows.Forms.Application]::DoEvents() }

  function Set-Stat($id) {
    $t = $script:TWMAP[$id]; if (-not $t) { return }
    $s = Get-TwState $t
    $lbl = $script:STATUS[$id]; if (-not $lbl) { return }
    $lbl.Text = "Stato attuale: $($s.label)"
    if ($s.code -eq 'ok') { $lbl.ForeColor = $script:C_GREEN } else { $lbl.ForeColor = $script:C_ACC }
  }
  function Refresh-Status {
    foreach ($id in @($script:STATUS.Keys)) { Set-Stat $id }
    if ($script:BKLBL) { $script:BKLBL.Text = ("Backup: {0} modifiche reversibili" -f $script:BK.Count) }
  }
  $script:C_ACC = $acc; $script:C_GREEN = $green

  # ---- Tabs with cards ----
  $tc = New-Object System.Windows.Forms.TabControl
  $tc.Location = New-Object System.Drawing.Point(14, 222); $tc.Size = New-Object System.Drawing.Size(766, 396)
  $cats = @(
    @{ key='gaming';  title='Gaming & FPS' },
    @{ key='input';   title='Latenza & Input' },
    @{ key='network'; title='Rete & Streaming' },
    @{ key='system';  title='Sistema & Debloat' }
  )

  function New-TweakCard($t, $flow) {
    $fit = $script:FITMAP[$t.id]; if (-not $fit) { $fit = 'ok' }
    $isSkip = $fit -like 'skip:*'; $isWarn = $fit -like 'warn:*'
    $h = 176; if ($fit -ne 'ok') { $h = 200 }
    $card = New-Object System.Windows.Forms.Panel
    $card.Size = New-Object System.Drawing.Size(710, $h)
    $card.Margin = New-Object System.Windows.Forms.Padding(4, 4, 4, 8)
    $card.BackColor = $script:C_CARD

    $bar = New-Object System.Windows.Forms.Panel
    $bar.Location = New-Object System.Drawing.Point(0, 0); $bar.Size = New-Object System.Drawing.Size(4, $h)
    if ($isSkip) { $bar.BackColor = $script:C_GRAY }
    elseif ($t.risk -eq 'caution') { $bar.BackColor = $script:C_ORANGE } else { $bar.BackColor = $script:C_ACC }
    $card.Controls.Add($bar)

    $cb = New-Object System.Windows.Forms.CheckBox
    if ($isSkip) { $cb.Checked = $false; $cb.Enabled = $false }
    elseif ($script:PROFILE.Count -gt 0) { $cb.Checked = ($script:PROFILE -contains $t.id) }
    elseif ($isWarn) { $cb.Checked = $false }
    else { $cb.Checked = ($t.risk -ne 'caution') }
    $cb.Text = $t.name; $cb.ForeColor = $script:C_WHITE
    $cb.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
    $cb.Location = New-Object System.Drawing.Point(14, 10); $cb.AutoSize = $true
    $card.Controls.Add($cb); $script:CHECKS[$t.id] = $cb

    if ($t.risk -eq 'caution') {
      $rb = New-Object System.Windows.Forms.Label
      $rb.Text = 'CAUTELA'; $rb.ForeColor = $script:C_ORANGE
      $rb.Font = New-Object System.Drawing.Font('Segoe UI', 8, [System.Drawing.FontStyle]::Bold)
      $rb.Location = New-Object System.Drawing.Point(560, 12); $rb.AutoSize = $true
      $card.Controls.Add($rb)
    }

    $st = New-Object System.Windows.Forms.Label
    $st.ForeColor = $script:C_ACC; $st.Location = New-Object System.Drawing.Point(32, 34); $st.AutoSize = $true
    $st.Font = New-Object System.Drawing.Font('Segoe UI', 8, [System.Drawing.FontStyle]::Bold)
    $card.Controls.Add($st); $script:STATUS[$t.id] = $st

    function New-Line($prefix, $text, $y, $col) {
      $l = New-Object System.Windows.Forms.Label
      $l.Text = "$prefix  $text"; $l.ForeColor = $col
      $l.Location = New-Object System.Drawing.Point(32, $y); $l.MaximumSize = New-Object System.Drawing.Size(660, 0); $l.AutoSize = $true
      return $l
    }
    $card.Controls.Add((New-Line 'Problema:' $t.problem 56 $script:C_ORANGE))
    $card.Controls.Add((New-Line 'Motivo:'   $t.reason  84 $script:C_GRAY))
    $card.Controls.Add((New-Line 'Modifica:' $t.desc    112 $script:C_LIGHT))
    $card.Controls.Add((New-Line 'Impatto:'  $t.impact  140 $script:C_GREEN))

    if ($fit -ne 'ok') {
      $an = New-Object System.Windows.Forms.Label
      $msg = $fit.Substring($fit.IndexOf(':') + 1)
      $an.Text = "ADATTIVO:  $msg"
      if ($isSkip) { $an.ForeColor = $script:C_GRAY } elseif ($isWarn) { $an.ForeColor = $script:C_ORANGE } else { $an.ForeColor = $script:C_BLUE }
      $an.Font = New-Object System.Drawing.Font('Segoe UI', 8, [System.Drawing.FontStyle]::Bold)
      $an.Location = New-Object System.Drawing.Point(32, 164); $an.MaximumSize = New-Object System.Drawing.Size(660, 0); $an.AutoSize = $true
      $card.Controls.Add($an)
    }

    $ab = New-Object System.Windows.Forms.Button
    $ab.Text = 'Applica'; $ab.Tag = $t.id
    $ab.Location = New-Object System.Drawing.Point(576, 34); $ab.Size = New-Object System.Drawing.Size(118, 32)
    $ab.FlatStyle = 'Flat'; $ab.BackColor = $script:C_ACC; $ab.ForeColor = [System.Drawing.Color]::Black
    $ab.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
    $ab.Add_Click({
      $id = $this.Tag; $tw = $script:TWMAP[$id]; if (-not $tw) { return }
      GuiLog ("-> Applico: {0}" -f $tw.name)
      & $tw.apply
      Save-Backup
      Refresh-Status
      GuiLog ("   OK - backup aggiornato ({0} modifiche reversibili)." -f $script:BK.Count)
    })
    if ($isSkip) { $ab.Enabled = $false }
    $card.Controls.Add($ab)

    $flow.Controls.Add($card)
  }

  $script:C_CARD = $cardBg; $script:C_WHITE = $white; $script:C_ORANGE = $orange; $script:C_BLUE = $blue
  $script:C_GRAY = $gray; $script:C_LIGHT = $light

  foreach ($c in $cats) {
    $tp = New-Object System.Windows.Forms.TabPage; $tp.Text = $c.title; $tp.BackColor = $bg2
    $flow = New-Object System.Windows.Forms.FlowLayoutPanel
    $flow.Dock = 'Fill'; $flow.FlowDirection = 'TopDown'; $flow.WrapContents = $false
    $flow.AutoScroll = $true; $flow.BackColor = $bg2; $flow.Padding = New-Object System.Windows.Forms.Padding(6)
    foreach ($t in $script:TWEAKS) { if ($t.cat -eq $c.key) { New-TweakCard $t $flow } }
    $tp.Controls.Add($flow); $tc.TabPages.Add($tp)
  }
  $form.Controls.Add($tc)
  Refresh-Status

  # ---- benchmark toggle ----
  $benchCb = New-Object System.Windows.Forms.CheckBox
  $benchCb.Text = 'Esegui benchmark PRIMA/DOPO per misurare il guadagno reale'
  $benchCb.Checked = $true; $benchCb.ForeColor = $blue
  $benchCb.Location = New-Object System.Drawing.Point(18, 628); $benchCb.AutoSize = $true
  $form.Controls.Add($benchCb); $script:BENCHCB = $benchCb

  # ---- action buttons ----
  $applyBtn = New-Object System.Windows.Forms.Button
  $applyBtn.Text = 'APPLICA SELEZIONATI'; $applyBtn.Location = New-Object System.Drawing.Point(16, 822); $applyBtn.Size = New-Object System.Drawing.Size(240, 46)
  $applyBtn.FlatStyle = 'Flat'; $applyBtn.BackColor = $acc; $applyBtn.ForeColor = [System.Drawing.Color]::Black
  $applyBtn.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
  $form.Controls.Add($applyBtn); $script:APPLYBTN = $applyBtn
  $applyBtn.Add_Click({
    $script:APPLYBTN.Enabled = $false
    $before = $null
    if ($script:BENCHCB.Checked) { GuiLog 'Benchmark PRIMA in corso...'; $before = Run-Benchmark; GuiLog ("  Performance Score PRIMA: {0}" -f $before.overall) }
    foreach ($t in $script:TWEAKS) { if ($script:CHECKS[$t.id].Checked) { GuiLog ("-> {0}" -f $t.name); & $t.apply } }
    Save-Backup
    if ($script:BENCHCB.Checked) {
      GuiLog 'Benchmark DOPO in corso...'; $after = Run-Benchmark
      $pct = $(if ($before.overall) { [math]::Round(($after.overall - $before.overall) / $before.overall * 100) } else { 0 })
      GuiLog ("  Performance Score DOPO: {0}  (variazione {1}%)" -f $after.overall, $pct)
      Send-Benchmark @{ before = $before; after = $after; ts = (Get-Date).ToString('o') }
    }
    Refresh-Status
    Send-Data (Get-Specs) (Get-Health) (Get-StartupList)
    GuiLog 'FATTO. Dati inviati a FrameForge. Riavvio consigliato.'
    $script:APPLYBTN.Enabled = $true
  })

  $restoreBtn = New-Object System.Windows.Forms.Button
  $restoreBtn.Text = 'RIPRISTINA TUTTO'; $restoreBtn.Location = New-Object System.Drawing.Point(266, 822); $restoreBtn.Size = New-Object System.Drawing.Size(180, 46)
  $restoreBtn.FlatStyle = 'Flat'; $restoreBtn.FlatAppearance.BorderColor = $red; $restoreBtn.ForeColor = $red
  $restoreBtn.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
  $restoreBtn.Add_Click({ GuiLog 'Ripristino dal backup...'; GuiLog ('  ' + (Invoke-Restore)); Refresh-Status })
  $form.Controls.Add($restoreBtn)

  if (-not $isAdmin) {
    $elevBtn = New-Object System.Windows.Forms.Button
    $elevBtn.Text = 'Riavvia come Amministratore'; $elevBtn.Location = New-Object System.Drawing.Point(456, 822); $elevBtn.Size = New-Object System.Drawing.Size(224, 46)
    $elevBtn.FlatStyle = 'Flat'; $elevBtn.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(42,42,53); $elevBtn.ForeColor = $white
    $elevBtn.Add_Click({
      if ($PSCommandPath) {
        Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-Token',$TOKEN,'-Mode','optimize' 2>$null
      } else {
        $ff = Join-Path $env:TEMP 'forgefps.ps1'
        try { Invoke-RestMethod -Uri "$BACKEND/api/agent/script?t=$TOKEN" -OutFile $ff } catch {}
        Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$ff,'-Token',$TOKEN,'-Mode','optimize' 2>$null
      }
      $form.Close()
    })
    $form.Controls.Add($elevBtn)
  }

  [void]$form.ShowDialog()
  return $true
}

# ---------------- Main ----------------
if ($MODE -eq 'autopilot' -or $MODE -eq 'cleanup') {
  Say "`n[AUTO-PILOT] Analisi del sistema in corso..." 'Cyan'
  $__apBefore = $null; try { $__apBefore = Get-Health } catch {}
  $__apApplied = @()
  foreach ($t in $script:TWEAKS) {
    if ($t.risk -ne 'safe') { continue }
    $__fit = 'ok'; if ($t.fit) { try { $__fit = & $t.fit } catch { $__fit = 'ok' }; if (-not $__fit) { $__fit = 'ok' } }
    if ("$__fit" -like 'skip*') { continue }
    $__st = 'n/d'; try { $__st = & $t.state } catch { $__st = 'n/d' }
    if ("$__st" -match '^(Attivo|Disabilitato|n/d)$') { continue }
    try {
      Invoke-ApplyTracked $t
      $__apApplied += $t.id
      Say-Ok ("  {0}" -f $t.name)
    } catch { Say-Warn ("  {0}" -f $t.name) }
  }
  Save-Backup
  Say ("`n[AUTO-PILOT] {0} tweak applicati. Misuro il dopo..." -f $__apApplied.Count) 'Cyan'
  Start-Sleep -Seconds 2
  $__apAfter = $null; try { $__apAfter = Get-Health } catch {}
  try {
    $__apBody = @{ applied = $__apApplied; before = $__apBefore; after = $__apAfter } | ConvertTo-Json -Depth 6 -Compress
    $__apBytes = [System.Text.Encoding]::UTF8.GetBytes($__apBody)
    Invoke-WebRequest -Uri "$BACKEND/api/autopilot/agent/result" -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $__apBytes -UseBasicParsing -TimeoutSec 20 | Out-Null
    Say "[AUTO-PILOT] Rapporto inviato al dashboard." 'Green'
  } catch { Say ("[AUTO-PILOT] Invio rapporto fallito: {0}" -f $_.Exception.Message) 'Red' }
  try { Send-Data (Get-Specs) $__apAfter (Get-StartupList) } catch {}
  Say "`n[DONE] Auto-Pilot completato. Controlla il rapporto sul dashboard." 'Green'
  Start-Sleep -Seconds 3
  return
}

if ($MODE -eq 'restore') { Say "`n[STEP] Ripristino dal backup..." 'Cyan'; Say ('   ' + (Invoke-Restore)) 'Green'; try { Invoke-RestMethod -Uri "$BACKEND/api/autopilot/agent/restore-done" -Method Post -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -TimeoutSec 10 | Out-Null } catch {}; return }

if ($MODE -eq 'benchmark') {
  Say "`n[STEP] Benchmark (CPU / RAM / Disco / Rete)..." 'Cyan'
  $bench = Run-Benchmark; Show-Bench $bench 'BENCHMARK'
  Send-Benchmark @{ after = $bench; ts = (Get-Date).ToString('o') }
  Say "`n[ OK ] Benchmark inviato! Vedi il confronto in FrameForge -> Il mio PC." 'Green'
  return
}

if ($MODE -eq 'fullbench') {
  # v0.7.4: Full Benchmark v2 (multi-thread CPU + RAM hierarchy + Disk multi-QD + thermal trace).
  # Durata ~2-4 minuti. Piu' preciso del Run-Benchmark quick — differenzia i5/i9,
  # rileva thermal throttling, misura pattern disk realistici.
  Say "`n==============================================" 'Yellow'
  Say "  FULL BENCHMARK v2  (~2-4 minuti, non chiudere)" 'Yellow'
  Say "==============================================" 'Yellow'
  Say '   Sto misurando: CPU multi-thread burst+sustained, RAM L2/L3/DRAM,' 'DarkGray'
  Say '   Disco Seq QD1/8 + Rand 4K QD1/32, Rete estesa, Thermal trace.' 'DarkGray'
  Say '   Chiudi giochi e app pesanti per risultati piu accurati.' 'DarkGray'
  $fb = Run-FullBenchmark
  Send-Benchmark @{ full = $fb; ts = (Get-Date).ToString('o') }
  Say "`n==============================================" 'Yellow'
  Say-Ok ("Full Benchmark completato in {0}s. Dati inviati al cloud." -f $fb.duration_s)
  Say "        Apri FrameForge -> Il mio PC per il report completo." 'Green'
  Say "==============================================" 'Yellow'
  return
}

if ($MODE -eq 'optimize') {
  # v0.8.0-fps: se elevati, autorizza una tantum la cattura FPS non-admin
  # (gruppo Performance Log Users) per il monitor senza UAC.
  try { Enable-FpsPermission | Out-Null } catch {}
  # v0.7.4c: first-scan CONDIZIONALE. Il primo scan e' utile SOLO se i dati cloud
  # sono stantii o assenti (utente nuovo, o non ha aperto la GUI da giorni).
  # Se pc-specs.updated_at e' recente (< 15 min) saltiamo: risparmiamo 3-5s
  # di attesa ad ogni apertura e togliamo l'effetto "primo scan a ogni apertura".
  $__skipFirstScan = $false
  try {
    $__specsResp = Invoke-RestMethod -Uri "$BACKEND/api/pc-specs-agent" -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -TimeoutSec 6 -ErrorAction Stop
    if ($__specsResp -and $__specsResp.updated_at) {
      $__lastSync = [DateTime]::Parse($__specsResp.updated_at)
      $__ageMin = ((Get-Date).ToUniversalTime() - $__lastSync.ToUniversalTime()).TotalMinutes
      if ($__ageMin -lt 15) {
        $__skipFirstScan = $true
        Say ("`n[SKIP] Ultima sync cloud: {0:F1} min fa (< 15 min). Salto il primo scan e vado alla GUI." -f $__ageMin) 'DarkGray'
      }
    }
  } catch {
    # 404 = utente senza dati (mai sincronizzato) -> primo scan e' giustificato.
    # Qualsiasi altro errore -> facciamo il primo scan per sicurezza.
  }

  if (-not $__skipFirstScan) {
  # v0.7.4: first-scan al primo avvio della GUI (mode=optimize di default al doppio-click).
  # Prima venivano inviati solo dopo apply/benchmark, quindi un utente nuovo che apre
  # e chiude la GUI senza applicare nulla lasciava il dashboard cloud completamente vuoto.
  # Ora invece: specs / health / startup / running / games sincronizzati SEMPRE all'apertura.
  #
  # v0.7.4b: POST verbosi con status code visibile — le helper Send-Data/Send-Running/
  # Send-Games erano wrapped in try/catch silente, quindi un 401 (token invalido) o 500
  # (backend crash) mostrava lo stesso "[OK] Primo scan completato" ma il DB restava vuoto.
  # Ora ogni POST logga byte inviati + HTTP status + eventuale errore.
  Say "`n[STEP] Primo scan hardware in corso (rilevo CPU, GPU, RAM, salute, avvio)..." 'Cyan'

  function __FsPost($body, $label) {
    $json = $body | ConvertTo-Json -Depth 8 -Compress
    # v0.8.1: UTF-8 esplicito. PS 5.1 invia il body in Latin-1 senza charset e i nomi
    # dei servizi Windows in italiano (lettere accentate) rompevano il parse -> HTTP 400.
    $__b = [System.Text.Encoding]::UTF8.GetBytes($json)
    try {
      $resp = Invoke-WebRequest -Uri "$BACKEND/api/agent/report-specs" -Method Post `
        -ContentType 'application/json; charset=utf-8' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } `
        -Body $__b -UseBasicParsing -TimeoutSec 20
      Say-Ok ("  {0}: {1} bytes -> HTTP {2}" -f $label, $json.Length, $resp.StatusCode)
      return $true
    } catch {
      $status = 0
      try { $status = $_.Exception.Response.StatusCode.value__ } catch {}
      $errMsg = $_.Exception.Message
      Say-Err ("  {0} -> HTTP {1}: {2}" -f $label, $status, $errMsg)
      if ($status -eq 401) {
        Say "         Token agent non valido. Riscarica il ZIP personalizzato dalla pagina 'FrameForge Agent'." 'Yellow'
      } elseif ($status -eq 0) {
        Say ("         Backend non raggiungibile: {0}. Firewall/proxy? Connessione internet?" -f $BACKEND) 'Yellow'
      }
      return $false
    }
  }

  $__scanSpecs = $null; $__scanHealth = $null; $__scanStartup = $null; $__scanSvc = $null
  try { $__scanSpecs = Get-Specs;         Say ("  specs: CPU={0}, GPU={1}, RAM={2}" -f $__scanSpecs.cpu, $__scanSpecs.gpu, $__scanSpecs.ram) 'DarkGray' } catch { Say ("  Get-Specs FAIL: {0}" -f $_.Exception.Message) 'Red' }
  try { $__scanHealth = Get-Health;       Say ("  health: {0} chiavi" -f $__scanHealth.Count) 'DarkGray' } catch { Say ("  Get-Health FAIL: {0}" -f $_.Exception.Message) 'Yellow' }
  try { $__scanStartup = Get-StartupList; Say ("  startup: {0} app all'avvio" -f $__scanStartup.Count) 'DarkGray' } catch { Say ("  Get-StartupList FAIL: {0}" -f $_.Exception.Message) 'Yellow' }
  try { $__scanSvc = Get-ServicesAudit;   Say ("  servizi: {0} controllati" -f $__scanSvc.Count) 'DarkGray' } catch { Say ("  Get-ServicesAudit FAIL: {0}" -f $_.Exception.Message) 'Yellow' }

  if ($__scanSpecs) {
    $__body = @{}
    if ($__scanSpecs)   { $__body.data    = $__scanSpecs }
    if ($__scanHealth)  { $__body.health  = $__scanHealth }
    if ($__scanStartup) { $__body.startup = $__scanStartup }
    if ($__scanSvc -and $__scanSvc.Count -gt 0) { $__body.services_audit = $__scanSvc }
    $__ok = __FsPost $__body 'specs+health+startup'
    if ($__ok) {
      Say-Ok ("Primo scan completato: {0} | GPU {1} | RAM {2}. Dati inviati al cloud." -f $__scanSpecs.cpu, $__scanSpecs.gpu, $__scanSpecs.ram)
    } else {
      Say-Err "Primo scan: dati NON inviati. La GUI continua ma la dashboard restera' vuota finche' non risolvi l'errore sopra."
    }
    try {
      $__scanRun = Get-RunningApps
      if ($__scanRun.Count -gt 0) { __FsPost @{ running_apps = $__scanRun } ("running_apps ({0})" -f $__scanRun.Count) | Out-Null }
    } catch { Say ("  Get-RunningApps FAIL: {0}" -f $_.Exception.Message) 'Yellow' }
    try {
      $__scanGames = Get-Games
      if ($__scanGames.Count -gt 0) { __FsPost @{ games = $__scanGames } ("games ({0})" -f $__scanGames.Count) | Out-Null }
    } catch { Say ("  Get-Games FAIL: {0}" -f $_.Exception.Message) 'Yellow' }
  } else {
    Say-Err "Impossibile raccogliere le specs, invio saltato. Riprova come Amministratore."
  }
  }  # end if -not $__skipFirstScan

  Say "`n[STEP] Apro il pannello ottimizzazioni..." 'Cyan'
  $ok = $false
  $guiErr = ''
  # Un secondo tentativo prima di arrendersi: la porta viene chiesta al sistema
  # e poi rilasciata un istante prima di legarla, quindi l'unica causa plausibile
  # di fallimento e' che qualcuno l'abbia presa in quella finestra. Ritentare
  # costa niente e copre proprio quel caso.
  foreach ($try in 1, 2) {
    try { $ok = Show-WebGui } catch { $guiErr = "$($_.Exception.Message) (riga $($_.InvocationInfo.ScriptLineNumber))"; $ok = $false }
    if ($ok) { break }
    if ($try -eq 1) { Say-Info 'Server locale non avviato, riprovo su un altra porta...'; Start-Sleep -Milliseconds 400 }
  }
  if (-not $ok) {
    if (-not $guiErr) { $guiErr = 'il server locale non si e avviato (nessuna eccezione)' }
    Say-Warn ("Interfaccia web non disponibile: {0}" -f $guiErr)
    Say-Warn 'Uso la GUI classica: ha meno funzioni della finestra normale.'
    # Registrato per poter decidere con i dati se la GUI classica valga le 451
    # righe che costa: oggi nessuno sa quanto scatti davvero.
    try {
      Send-AgentDiag 'gui_web_failed' @{ error = $guiErr; admin = (Test-Admin); os = "$([Environment]::OSVersion.Version)" }
    } catch {}
    $ok = Show-Gui
  }
  if (-not $ok) {
    Say-Warn 'Interfaccia grafica non disponibile. Applico i preset Completo...'
    $before = Run-Benchmark; Show-Bench $before 'PRIMA'
    Say-Info ("{0} | GPU {1} | RAM {2} GB | {3} -> tweak adattati" -f $(if($script:HW.laptop){'Laptop'}else{'Desktop'}), $script:HW.gpu, $script:HW.ram, $(if($script:HW.ssd){'SSD'}else{'HDD'})) 'HW'
    foreach ($t in $script:TWEAKS) {
      $f = 'ok'; if ($t.fit) { $f = & $t.fit }
      if ($t.id -eq 'search_index' -or $f -like 'skip:*' -or $f -like 'warn:*') { Say ("   -- saltato (adattivo): {0}" -f $t.name) 'DarkGray'; continue }
      Say ("   -> {0}" -f $t.name); & $t.apply
    }
    Save-Backup
    $after = Run-Benchmark; Show-Bench $after 'DOPO'
    Send-Benchmark @{ before = $before; after = $after; ts = (Get-Date).ToString('o') }
    Send-Data (Get-Specs) (Get-Health) (Get-StartupList)
  }
  return
}

function Measure-Ping($target, $count, $interval, $timeout) {
  $p = New-Object System.Net.NetworkInformation.Ping
  $rtts = New-Object 'System.Collections.Generic.List[double]'
  $sent = 0; $lost = 0
  $sw = New-Object System.Diagnostics.Stopwatch
  for ($i = 0; $i -lt $count; $i++) {
    $sent++
    try {
      $sw.Restart()
      $reply = $p.Send($target, $timeout)
      $sw.Stop()
      if ($reply.Status -eq 'Success') { $rtts.Add([math]::Round($sw.Elapsed.TotalMilliseconds, 2)) } else { $lost++ }
    } catch { $lost++ }
    Start-Sleep -Milliseconds $interval
  }
  return @{ rtts = $rtts; sent = $sent; lost = $lost }
}
function Percentile($list, $q) {
  if ($list.Count -eq 0) { return $null }
  $sorted = @($list | Sort-Object)
  $idx = [int][math]::Floor($q * ($sorted.Count - 1))
  if ($idx -lt 0) { $idx = 0 }
  return [math]::Round($sorted[$idx], 1)
}
function Jitter($list) {
  if ($list.Count -lt 2) { return $null }
  $m = ($list | Measure-Object -Average).Average
  $v = ($list | ForEach-Object { ($_ - $m) * ($_ - $m) } | Measure-Object -Average).Average
  return [math]::Round([math]::Sqrt($v), 1)
}
function Send-NetResult($res) {
  $items = ($res.GetEnumerator() | ForEach-Object {
      $v = if ($null -eq $_.Value) { 'null' } else { $_.Value }
      '"' + $_.Key + '":' + $v
    }) -join ','
  $body = '{"result":{' + $items + '}}'
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/netresult" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body | Out-Null } catch {}
}
$script:DL_BLOCK = {
  param($u)
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    [Net.ServicePointManager]::DefaultConnectionLimit = 16
    while ($true) {
      $req = [System.Net.HttpWebRequest]::Create($u); $req.Timeout = 30000
      $resp = $req.GetResponse(); $s = $resp.GetResponseStream()
      $buf = New-Object byte[] 131072
      while ($s.Read($buf, 0, $buf.Length) -gt 0) {}
      $s.Close(); $resp.Close()
    }
  } catch {}
}
$script:UP_BLOCK = {
  param($u)
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $chunk = New-Object byte[] 262144
    while ($true) {
      $req = [System.Net.HttpWebRequest]::Create($u); $req.Method = 'POST'; $req.Timeout = 30000
      $req.SendChunked = $true; $req.AllowWriteStreamBuffering = $false
      $rs = $req.GetRequestStream()
      for ($k = 0; $k -lt 400; $k++) { $rs.Write($chunk, 0, $chunk.Length) }
      $rs.Close(); $resp = $req.GetResponse(); $resp.Close()
    }
  } catch {}
}
function Run-Bufferbloat {
  $target = '1.1.1.1'
  $downUrl = 'https://speed.cloudflare.com/__down?bytes=1073741824'
  $upUrl = 'https://speed.cloudflare.com/__up'

  Say-Info '   Latenza a riposo (baseline, 50 campioni)...' '1/3'
  $idle = Measure-Ping $target 50 40 1000
  $idleP50 = Percentile $idle.rtts 0.5
  $idleMin = Percentile $idle.rtts 0.0
  Say ("        idle p50: {0} ms | min: {1} ms | jitter: {2} ms" -f $idleP50, $idleMin, (Jitter $idle.rtts)) 'DarkGray'

  Say-Info '   Sotto carico DOWNLOAD (8 stream, warm-up 2.5s)...' '2/3'
  $dljobs = @(); for ($i = 0; $i -lt 8; $i++) { $dljobs += Start-Job -ScriptBlock $script:DL_BLOCK -ArgumentList $downUrl }
  Start-Sleep -Milliseconds 2500
  $down = Measure-Ping $target 80 40 2000
  $dljobs | Stop-Job -ErrorAction SilentlyContinue; $dljobs | Remove-Job -Force -ErrorAction SilentlyContinue
  $downP50 = Percentile $down.rtts 0.5; $downP95 = Percentile $down.rtts 0.95; $downP99 = Percentile $down.rtts 0.99
  Say ("        download p50: {0} ms | p95: {1} ms | p99: {2} ms" -f $downP50, $downP95, $downP99) 'DarkGray'
  Start-Sleep -Milliseconds 1000

  Say-Info '   Sotto carico UPLOAD (4 stream, warm-up 2.5s)...' '3/3'
  $upP50 = $null; $upP95 = $null; $upP99 = $null; $upLost = 0; $upSent = 0
  try {
    $upjobs = @(); for ($i = 0; $i -lt 4; $i++) { $upjobs += Start-Job -ScriptBlock $script:UP_BLOCK -ArgumentList $upUrl }
    Start-Sleep -Milliseconds 2500
    $up = Measure-Ping $target 60 40 2000
    $upjobs | Stop-Job -ErrorAction SilentlyContinue; $upjobs | Remove-Job -Force -ErrorAction SilentlyContinue
    $upP50 = Percentile $up.rtts 0.5; $upP95 = Percentile $up.rtts 0.95; $upP99 = Percentile $up.rtts 0.99
    $upLost = $up.lost; $upSent = $up.sent
    Say ("        upload p50: {0} ms | p95: {1} ms | p99: {2} ms" -f $upP50, $upP95, $upP99) 'DarkGray'
  } catch {}

  $totalSent = $down.sent + $upSent
  $totalLost = $down.lost + $upLost
  $loss = if ($totalSent -gt 0) { [math]::Round(100.0 * $totalLost / $totalSent, 1) } else { 0 }
  $res = [ordered]@{
    idle_ms   = $idleP50
    idle_min  = $idleMin
    down_ms   = $downP50
    down_p95  = $downP95
    down_p99  = $downP99
    up_ms     = $upP50
    up_p95    = $upP95
    up_p99    = $upP99
    jitter_ms = (Jitter $idle.rtts)
    loss_pct  = $loss
    samples   = ($idle.rtts.Count + $down.rtts.Count)
  }
  Send-NetResult $res
  Say "`n[ OK ] Test rete completato. Apri FrameForge -> Rete per il voto (A-F) e i consigli." 'Green'
}

# ---------------- LAB: Laboratorio Automatico delle Prestazioni (Fase 1) ----------------
function LabApi($method, $path, $body) {
  try {
    $h = @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME }
    if ($body) { return Invoke-RestMethod -Uri "$BACKEND$path" -Method $method -ContentType 'application/json' -Headers $h -Body ($body | ConvertTo-Json -Depth 8 -Compress) -TimeoutSec 30 }
    return Invoke-RestMethod -Uri "$BACKEND$path" -Method $method -Headers $h -TimeoutSec 30
  } catch { return $null }
}
function LabEvent($type, $data) {
  $b = @{ type = $type }
  if ($data) { $b.data = $data }
  LabApi 'Post' '/api/agent/lab/event' $b | Out-Null
}
# ---------------- Strumenti di misura del Lab ----------------
function Get-LabRunContext {
  # Contesto in cui la misura e' stata presa. Senza, due run non confrontabili
  # (uno a batteria, uno dopo un cambio di risoluzione) finiscono nello stesso
  # confronto come se fossero la stessa cosa.
  $c = @{}
  try {
    $vc = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
          Where-Object { $_.CurrentHorizontalResolution -gt 0 } | Select-Object -First 1
    if ($vc) {
      $c.res_w = [int]$vc.CurrentHorizontalResolution
      $c.res_h = [int]$vc.CurrentVerticalResolution
      $c.refresh_hz = [int]$vc.CurrentRefreshRate
      if ($vc.DriverVersion) { $c.gpu_driver = "$($vc.DriverVersion)" }
    }
  } catch {}
  try {
    # BatteryStatus 1 = a batteria. Su un fisso la classe non esiste proprio.
    $b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    $c.on_battery = [bool]($b -and $b.BatteryStatus -eq 1)
  } catch { $c.on_battery = $false }
  try { $c.power_plan = "$(Get-PowerPlanNormalized)" } catch {}
  try { $c.obs_running = [bool](Get-Process -Name 'obs64', 'obs32', 'obs' -ErrorAction SilentlyContinue) } catch {}
  return $c
}

function Start-LabTelemetry {
  # nvidia-smi gira UNA volta per tutto il run scrivendo su file, invece di
  # essere rilanciato a ogni campione: avviare un processo ogni cinque secondi
  # durante un benchmark significa misurare anche il proprio disturbo.
  $script:LT_CPU = New-Object System.Collections.ArrayList
  $script:LT_TCPU = New-Object System.Collections.ArrayList
  $script:LT_RAM = New-Object System.Collections.ArrayList
  $script:LT_GPU = New-Object System.Collections.ArrayList
  $script:LT_TGPU = New-Object System.Collections.ArrayList
  $script:LT_CLK = New-Object System.Collections.ArrayList
  $script:LT_PWR = New-Object System.Collections.ArrayList
  $script:LT_NVFILE = Join-Path $env:TEMP ('ff_lab_nv_' + [guid]::NewGuid().ToString('N') + '.csv')
  $script:LT_NV = $null
  try {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
      $nvArgs = '--query-gpu=utilization.gpu,temperature.gpu,clocks.gr,power.draw ' +
                '--format=csv,noheader,nounits -l 1 -f "' + $script:LT_NVFILE + '"'
      $script:LT_NV = Start-Process -FilePath 'nvidia-smi' -ArgumentList $nvArgs `
        -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue
    }
  } catch {}
}

function Add-LabTelemetrySample {
  # Contatore di prestazione invece di Win32_Processor.LoadPercentage, che e'
  # aggiornato di rado e mediato su una finestra che nessuno controlla.
  try {
    $p = Get-CimInstance -ClassName Win32_PerfFormattedData_PerfOS_Processor `
         -Filter "Name='_Total'" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { [void]$script:LT_CPU.Add([double]$p.PercentProcessorTime) }
  } catch {}
  try {
    $o = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($o -and $o.TotalVisibleMemorySize -gt 0) {
      [void]$script:LT_RAM.Add([double](($o.TotalVisibleMemorySize - $o.FreePhysicalMemory) / $o.TotalVisibleMemorySize * 100))
    }
  } catch {}
  try {
    $lhm = Get-LhmTemps
    if ($lhm.ContainsKey('cpu_temp')) { [void]$script:LT_TCPU.Add([double]$lhm.cpu_temp) }
    if ((-not $script:LT_NV) -and $lhm.ContainsKey('gpu_temp')) { [void]$script:LT_TGPU.Add([double]$lhm.gpu_temp) }
  } catch {}
}

function _LtAgg($list, $name, $target) {
  if (-not $list -or $list.Count -eq 0) { return }
  $target[($name + '_avg')] = [math]::Round(($list | Measure-Object -Average).Average, 1)
  $target[($name + '_max')] = [math]::Round(($list | Measure-Object -Maximum).Maximum, 1)
}

function Stop-LabTelemetry {
  $out = @{}
  if ($script:LT_NV) {
    try { Stop-Process -Id $script:LT_NV.Id -Force -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Milliseconds 200
    try {
      foreach ($ln in (Get-Content $script:LT_NVFILE -ErrorAction SilentlyContinue)) {
        $p = "$ln".Split(',')
        if ($p.Count -lt 4) { continue }
        try {
          [void]$script:LT_GPU.Add([double]$p[0].Trim())
          [void]$script:LT_TGPU.Add([double]$p[1].Trim())
          [void]$script:LT_CLK.Add([double]$p[2].Trim())
          [void]$script:LT_PWR.Add([double]$p[3].Trim())
        } catch {}
      }
    } catch {}
    try { Remove-Item $script:LT_NVFILE -Force -ErrorAction SilentlyContinue } catch {}
    $script:LT_NV = $null
  }
  _LtAgg $script:LT_CPU 'cpu_pct' $out
  _LtAgg $script:LT_GPU 'gpu_pct' $out
  _LtAgg $script:LT_TCPU 'temp_cpu' $out
  _LtAgg $script:LT_TGPU 'temp_gpu' $out
  $n = 0
  foreach ($l in @($script:LT_CPU, $script:LT_GPU)) { if ($l -and $l.Count -gt $n) { $n = $l.Count } }
  $out.telemetry_samples = $n
  if ($script:LT_CLK -and $script:LT_CLK.Count -gt 0) {
    $out.gpu_clock_avg = [int][math]::Round(($script:LT_CLK | Measure-Object -Average).Average)
  }
  if ($script:LT_PWR -and $script:LT_PWR.Count -gt 0) {
    $out.gpu_power_avg = [int][math]::Round(($script:LT_PWR | Measure-Object -Average).Average)
  }
  return $out
}

function Get-LabTick {
  # Frametime (ms) NUOVI dal flusso PresentMon. Quando il gioco bersaglio e'
  # gia' stato scelto si leggono SOLO le sue righe: prendere a ogni tick l'app
  # con piu' present significa che un overlay o il browser possono vincere un
  # tick e infilare i propri frametime nel campione del gioco.
  if (-not $script:PM_ON) { return $null }
  $raw = Read-Shared $script:PM_OUT
  if (-not $raw) { return $null }
  $lines = $raw -split "`r?`n" | Where-Object { $_ -ne '' }
  if (-not $lines -or $lines.Count -le $script:PM_ROWS) { return $null }
  $hdr = $lines[0] -split ','
  $iApp = -1; $iMs = -1; $iLat = -1; $iPid = -1
  for ($k = 0; $k -lt $hdr.Count; $k++) {
    $h = $hdr[$k].Trim().ToLower()
    if ($h -eq 'application') { $iApp = $k }
    if ($h -eq 'processid') { $iPid = $k }
    if ($h -like '*betweenpresents*') { $iMs = $k }
    if ($h -like '*untildisplayed*') { $iLat = $k }
  }
  if ($iMs -lt 0) { $script:PM_ROWS = $lines.Count; return $null }
  $new = $lines[$script:PM_ROWS..($lines.Count - 1)]
  $script:PM_ROWS = $lines.Count
  $byApp = @{}
  $byLat = @{}
  $byPid = @{}
  $inv = [Globalization.CultureInfo]::InvariantCulture
  foreach ($ln in $new) {
    $c = $ln -split ','
    if ($c.Count -le $iMs) { continue }
    $app = if ($iApp -ge 0 -and $c.Count -gt $iApp) { $c[$iApp] } else { 'game' }
    $pid_ = if ($iPid -ge 0 -and $c.Count -gt $iPid) { "$($c[$iPid])".Trim() } else { '' }
    if ($script:LAB_APP) {
      if ($app -ne $script:LAB_APP) { continue }
      if ($script:LAB_PID -and $pid_ -and $pid_ -ne $script:LAB_PID) { continue }
    }
    try { $ms = [double]::Parse($c[$iMs], $inv) } catch { continue }
    if ($ms -le 0) { continue }
    if (-not $byApp.ContainsKey($app)) { $byApp[$app] = New-Object System.Collections.ArrayList }
    [void]$byApp[$app].Add($ms)
    if ($pid_) { $byPid[$app] = $pid_ }
    if ($iLat -ge 0 -and $c.Count -gt $iLat) {
      try {
        $lv = [double]::Parse($c[$iLat], $inv)
        if ($lv -gt 0 -and $lv -lt 1000) {
          if (-not $byLat.ContainsKey($app)) { $byLat[$app] = New-Object System.Collections.ArrayList }
          [void]$byLat[$app].Add($lv)
        }
      } catch {}
    }
  }
  if ($byApp.Count -eq 0) { return $null }
  $top = $byApp.GetEnumerator() | Sort-Object { $_.Value.Count } -Descending | Select-Object -First 1
  return @{ app = $top.Key; pid = $byPid[$top.Key]; ms = $top.Value; lat = $byLat[$top.Key] }
}
function Wait-LabGame {
  $shown = $false
  $lastPoll = Get-Date
  while ($true) {
    $t = Get-LabTick
    if ($t -and $t.ms.Count -ge 15) {
      if (-not $script:LAB_APP) {
        # Bersaglio bloccato una volta per tutta la sessione: da qui in poi si
        # misura questo processo e nient'altro.
        $script:LAB_APP = $t.app
        $script:LAB_PID = $t.pid
      }
      if ($shown) { Say-Ok ("   Gioco rilevato: {0}" -f $t.app) 'LAB'; LabEvent 'game_detected' @{ game = $t.app } }
      return $t.app
    }
    if (-not $shown) {
      $shown = $true
      if ($script:LAB_APP) {
        Say-Warn ("   In attesa di {0}... la sessione misura questo processo e nessun altro: riaprilo e resta in partita (scena il piu possibile ripetibile)." -f $script:LAB_APP) 'LAB'
      } else {
        Say-Warn '   In attesa del gioco... avvia il gioco e resta in partita (scena il piu possibile ripetibile).' 'LAB'
      }
      LabEvent 'waiting_game' $null
    }
    if (((Get-Date) - $lastPoll).TotalSeconds -ge 12) {
      $lastPoll = Get-Date
      $nx = LabApi 'Get' '/api/agent/lab/next' $null
      if ($nx -and ($nx.action -eq 'abort' -or $nx.action -eq 'complete')) { return '__STOP__' }
    }
    Start-Sleep -Milliseconds 1500
  }
}
function Invoke-LabRun($seconds, $label) {
  $fr = New-Object System.Collections.ArrayList
  $lt = New-Object System.Collections.ArrayList
  $hist = New-Object 'int[]' 306
  $app = ''
  $ctx = Get-LabRunContext
  Start-LabTelemetry
  $t0 = Get-Date
  $lastSay = -100
  $lastTel = -100
  while (((Get-Date) - $t0).TotalSeconds -lt $seconds) {
    $t = Get-LabTick
    if ($t) {
      $app = $t.app
      foreach ($v in $t.ms) { [void]$fr.Add($v); $hist[(Get-HistBucket ([double]$v))]++ }
      if ($t.lat) { foreach ($v in $t.lat) { [void]$lt.Add($v) } }
    }
    $el = [int]((Get-Date) - $t0).TotalSeconds
    # Un campione ogni 5s: la telemetria del run e' una media della finestra,
    # non l'istantanea presa alla fine come faceva la versione precedente.
    if (($el - $lastTel) -ge 5) { $lastTel = $el; Add-LabTelemetrySample }
    if (($el - $lastSay) -ge 15) { $lastSay = $el; Say ("      [{0}] {1}/{2}s - frame raccolti: {3}" -f $label, $el, $seconds, $fr.Count) 'DarkGray' }
    Start-Sleep -Milliseconds 900
  }
  $tel = Stop-LabTelemetry
  if ($fr.Count -lt 100) { return $null }
  $arr = [double[]]$fr.ToArray()
  $sorted = [double[]]$arr.Clone(); [Array]::Sort($sorted)
  $sum = 0.0; foreach ($v in $arr) { $sum += $v }
  $avg = $sum / $arr.Length
  $var = 0.0; foreach ($v in $arr) { $var += ($v - $avg) * ($v - $avg) }
  $var = $var / $arr.Length
  # 1% low = frametime MEDIO dell'1% peggiore dei frame, non il p99 puntuale:
  # il p99 guarda un solo frame e ignora tutto cio' che sta oltre, quindi non
  # distingue un'esitazione da 30 ms da un freeze da mezzo secondo.
  $k1 = [math]::Max(1, [int][math]::Ceiling($arr.Length * 0.01))
  $s1 = 0.0; for ($i = $sorted.Length - $k1; $i -lt $sorted.Length; $i++) { $s1 += $sorted[$i] }
  $low1 = $s1 / $k1
  $run = @{
    fps_avg = [math]::Round(1000.0 / $avg, 2)
    fps_p1 = [math]::Round(1000.0 / $low1, 2)
    ft_avg_ms = [math]::Round($avg, 3)
    ft_var = [math]::Round($var, 3)
    ft_cv = [math]::Round([math]::Sqrt($var) / [math]::Max($avg, 0.001), 3)
    frames = $arr.Length
    duration_s = [int]$seconds
    game = $app
    hist = $hist
    metrics_version = 2
  }
  # Lo 0.1% peggiore ha senso solo se sono almeno cinque frame: sotto, sarebbe
  # il singolo frame piu' sfortunato del run spacciato per una statistica.
  $k01 = [int][math]::Ceiling($arr.Length * 0.001)
  if ($k01 -ge 5) {
    $s01 = 0.0; for ($i = $sorted.Length - $k01; $i -lt $sorted.Length; $i++) { $s01 += $sorted[$i] }
    $run.fps_p01 = [math]::Round(1000.0 / ($s01 / $k01), 2)
  }
  foreach ($kv in $tel.GetEnumerator()) { $ctx[$kv.Key] = $kv.Value }
  if ($script:LAB_PID) { $ctx.process_id = "$script:LAB_PID" }
  $run.ctx = $ctx
  # Chiavi storiche mantenute: il resto del prodotto (grafici, report, AI) le legge.
  if ($ctx.ContainsKey('cpu_pct_avg')) { $run.cpu_pct = [int]$ctx.cpu_pct_avg }
  if ($ctx.ContainsKey('gpu_pct_avg')) { $run.gpu_pct = [int]$ctx.gpu_pct_avg }
  if ($ctx.ContainsKey('temp_gpu_avg')) { $run.temp_gpu = [int]$ctx.temp_gpu_avg }
  if ($ctx.ContainsKey('temp_cpu_avg')) { $run.temp_cpu = [int]$ctx.temp_cpu_avg }
  if ($lt.Count -ge 50) {
    $ls = 0.0; foreach ($v in $lt) { $ls += $v }
    $run.latency_ms = [math]::Round($ls / $lt.Count, 2)
  }
  return $run
}

function Test-RunRejected($resp) {
  # Il backend rifiuta i run presi in condizioni non confrontabili (PC a
  # batteria, gioco diverso, troppi pochi frame). Si ripete la misura invece di
  # infilare nel confronto un dato che appartiene a un altro esperimento.
  if ($resp -and $resp.rejected) {
    Say-Warn ("   {0}. Ripeto la misura." -f $resp.reason)
    return $true
  }
  if ($resp -and $resp.warnings) {
    foreach ($w in @($resp.warnings)) { Say-Info ("   {0}" -f $w) }
  }
  return $false
}

function Register-LabResume {
  # Riprende il Lab automaticamente dopo il riavvio (RunOnce al logon + bootstrap che riscarica lo script)
  try {
    $dir = Join-Path $env:LOCALAPPDATA 'FrameForge'
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $rs = Join-Path $dir 'lab_resume.ps1'
    $lines = @(
      "`$t = '$TOKEN'",
      "`$u = '$BACKEND/api/agent/script?t=' + `$t",
      "`$f = Join-Path `$env:TEMP 'ff_lab_resume.ps1'",
      "try { Invoke-WebRequest -UseBasicParsing -Uri `$u -OutFile `$f -TimeoutSec 60 } catch { Start-Sleep 15; Invoke-WebRequest -UseBasicParsing -Uri `$u -OutFile `$f -TimeoutSec 60 }",
      "powershell -NoProfile -ExecutionPolicy Bypass -File `$f -Token `$t -Mode lab"
    )
    Set-Content -Path $rs -Value ($lines -join "`r`n") -Encoding UTF8
    $cmd = 'powershell -NoProfile -WindowStyle Normal -ExecutionPolicy Bypass -File "' + $rs + '"'
    Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Name 'FrameForgeLabResume' -Value $cmd -Force
    return $true
  } catch { return $false }
}
function Remove-LabResume {
  try { Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Name 'FrameForgeLabResume' -ErrorAction SilentlyContinue } catch {}
  try { Remove-Item (Join-Path $env:LOCALAPPDATA 'FrameForge\lab_resume.ps1') -Force -ErrorAction SilentlyContinue } catch {}
}
function Invoke-LabRebootPrompt($tweakId) {
  $reg = Register-LabResume
  if ($reg) { Say-Ok '   Ripresa automatica registrata: dopo il riavvio e il login, il Lab continua da solo (conferma UAC richiesta).' }
  else { Say-Warn '   Non sono riuscito a registrare la ripresa automatica: dopo il riavvio rilancia tu il comando Lab.' }
  Say ("`n   Il tweak '{0}' richiede un RIAVVIO per avere effetto." -f $tweakId) 'Yellow'
  $ans = Read-Host '   Riavviare ADESSO? Digita S per riavviare subito, altro tasto per riavviare tu manualmente'
  if ($ans -match '^[sS]') {
    Say '   Riavvio in 8 secondi... salva tutto!' 'Yellow'
    shutdown /r /t 8 | Out-Null
  } else {
    Say '   OK: riavvia quando vuoi. Il Lab riprendera automaticamente al prossimo login.' 'Gray'
  }
}

if ($MODE -eq 'lab') {
  Say "`n== FrameForge LAB - Laboratorio Automatico delle Prestazioni ==" 'Cyan'
  Say '   Testo i tweak UNO ALLA VOLTA sul tuo gioco: baseline x3, misura, statistica, rollback se inutile.' 'Gray'
  if (-not (Test-Admin)) {
    if ($PSCommandPath) {
      Say-Warn '   Servono i permessi amministratore (tweak di sistema + punto di ripristino): riavvio elevato...' 'LAB'
      try {
        Start-Process powershell -Verb RunAs -ArgumentList ('-ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Token ' + $TOKEN + ' -Mode lab')
        return
      } catch {}
    }
    Say-Err 'Il Laboratorio richiede PowerShell come AMMINISTRATORE.'
    Say '       Apri PowerShell con tasto destro -> Esegui come amministratore e rilancia il comando.' 'Yellow'
    return
  }
  $script:TWMAP = @{}
  foreach ($t in $script:TWEAKS) { $script:TWMAP[$t.id] = $t }
  $script:LAB_APPLIED = New-Object System.Collections.ArrayList
  $script:LAB_BTEMPS = New-Object System.Collections.ArrayList
  $script:LAB_TREF = $null
  function Wait-ThermalStable {
    if (-not $script:LAB_TREF) { return }
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt 90) {
      $tel = Get-TelemetrySample
      $g = $null
      if ($tel.ContainsKey('gpu_temp')) { $g = [double]$tel.gpu_temp }
      if ((-not $g) -or ($g -le ($script:LAB_TREF + 3))) { return }
      Say-Info ("   GPU {0}C oltre il riferimento baseline ({1}C): attendo il raffreddamento per una misura pulita..." -f $g, $script:LAB_TREF) 'TERMICA'
      Start-Sleep -Seconds 8
    }
  }
  Start-Fps
  if (-not $script:PM_ON) { Say-Err 'Cattura FPS non disponibile: il Lab non puo misurare i benchmark.'; return }
  Say '   Collegato. Controllo la sessione Lab (avviala da FrameForge -> Laboratorio se non lo hai gia fatto)...' 'DarkGray'
  $idleWaits = 0
  $labDone = $false
  try {
    while (-not $labDone) {
      $nx = LabApi 'Get' '/api/agent/lab/next' $null
      if (-not $nx) { Start-Sleep -Seconds 5; continue }
      $act = "$($nx.action)"
      if ($act -eq 'wait') {
        $idleWaits++
        if ($idleWaits -eq 1) { Say-Warn '   Nessuna sessione attiva. Avviane una da FrameForge -> Laboratorio (resto in ascolto).' 'LAB' }
        if ($idleWaits -gt 75) { Say-Warn '   Nessuna sessione avviata in 5 minuti: esco.' 'LAB'; $labDone = $true; continue }
        Start-Sleep -Seconds 4
      }
      elseif ($act -eq 'snapshot') {
        $idleWaits = 0
        Say "`n[FASE 1/4] SNAPSHOT - punto di ripristino Windows + stato iniziale" 'Cyan'
        # Nuova sessione: si riparte senza bersaglio, altrimenti resterebbe
        # agganciato al gioco della sessione precedente.
        $script:LAB_APP = $null
        $script:LAB_PID = $null
        $rp = $false
        try {
          Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction SilentlyContinue
          Checkpoint-Computer -Description 'FrameForge Lab' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop
          $rp = $true
          Say-Ok '   Punto di ripristino Windows creato.'
        } catch {
          Say-Warn ('   Punto di ripristino non creato: ' + $_.Exception.Message)
          Say '          (Windows ne consente 1 ogni 24h; il backup mirato per-tweak resta comunque attivo.)' 'DarkGray'
        }
        $states = @{}
        foreach ($cid in @($nx.candidate_ids)) {
          $tw = $script:TWMAP[$cid]
          if ($tw) { $states[$cid] = "$((Get-TwState $tw).label)" }
        }
        LabEvent 'snapshot_done' @{ restore_point = $rp; states = $states }
        Say-Ok '   Snapshot inviato. Si passa alla BASELINE.'
      }
      elseif ($act -eq 'run_baseline') {
        Say ("`n[FASE 2/4] BASELINE - run {0}/{1} ({2}s)" -f ([int]$nx.runs_done + 1), $nx.runs_target, $nx.run_seconds) 'Cyan'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        $run = Invoke-LabRun $nx.run_seconds 'baseline'
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti (gioco chiuso o in pausa?). Riprovo.'; continue }
        Say ("   run: {0} FPS avg | 1% low {1} | frame {2}" -f $run.fps_avg, $run.fps_p1, $run.frames) 'Gray'
        $resp = LabApi 'Post' '/api/agent/lab/run' @{ phase = 'baseline'; run = $run }
        if (Test-RunRejected $resp) { continue }
        if ($run.temp_gpu) { [void]$script:LAB_BTEMPS.Add([double]$run.temp_gpu) }
        if ($resp -and $resp.baseline_ok) {
          Say-Ok ("   BASELINE stabile: {0} FPS avg (CV {1}%)" -f $resp.stats.fps_avg, $resp.stats.cv_pct)
          if ($resp.quality -and $resp.quality.capped) {
            Say-Warn ("   Frame cap rilevato a ~{0} FPS: con V-Sync o un limitatore attivo nessun tweak puo' mostrare un effetto misurabile. Togli il limite e rilancia il Lab." -f $resp.quality.cap_fps)
          }
          if ($script:LAB_BTEMPS.Count -gt 0) { $script:LAB_TREF = [int](($script:LAB_BTEMPS | Measure-Object -Average).Average) }
        }
        elseif ($resp -and $resp.extra_run) { Say-Info '   Variabilita alta tra i run (CV > 5%): 4o run e scarto l outlier.' }
      }
      elseif ($act -eq 'apply_tweak') {
        $tw = $script:TWMAP[$nx.tweak_id]
        if (-not $tw) {
          LabEvent 'tweak_skip' @{ tweak_id = $nx.tweak_id; reason = 'tweak non presente nel catalogo agent' }
          Say-Warn ("   Tweak {0} non trovato nel catalogo: salto." -f $nx.tweak_id)
        } else {
          Say ("`n[FASE 3/4] TEST {0}/{1}: {2}" -f $nx.step, $nx.total, $tw.name) 'Cyan'
          Invoke-ApplyTracked $tw
          Save-Backup
          [void]$script:LAB_APPLIED.Add("$($nx.tweak_id)")
          LabEvent 'tweak_applied' @{ tweak_id = $nx.tweak_id; requires_reboot = [bool]$nx.requires_reboot }
          if ($nx.requires_reboot) {
            Invoke-LabRebootPrompt $nx.tweak_id
            $labDone = $true
          } else {
            Say-Ok '   Tweak applicato (backup automatico). Attendo 3s che si assesti...'
            Start-Sleep -Seconds 3
          }
        }
      }
      elseif ($act -eq 'pair_toggle') {
        # Schema appaiato: si spegne e riaccende il tweak fra una misura e
        # l'altra, cosi' ogni coppia ON/OFF condivide temperatura e scena.
        $tid = "$($nx.tweak_id)"
        if ("$($nx.stage)" -eq 'off') {
          $msg = Invoke-RestoreTweak $tid
          Say-Info ("   {0} disattivato per la misura OFF: {1}" -f $tid, $msg) 'COPPIA'
        } else {
          $tw = $script:TWMAP[$tid]
          if ($tw) { Invoke-ApplyTracked $tw; Save-Backup }
          Say-Info ("   {0} riattivato per la misura ON" -f $tid) 'COPPIA'
        }
        Start-Sleep -Seconds 3
        LabEvent 'pair_toggled' @{ tweak_id = $tid; stage = "$($nx.stage)"; final = [bool]$nx.final }
      }
      elseif ($act -eq 'run_pair') {
        Say ("   [TEST {0} - {1}] coppia {2}/{3} ({4}s)" -f $nx.tweak_id, "$($nx.stage)".ToUpper(), $nx.pair_num, $nx.pairs_total, $nx.run_seconds) 'Cyan'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        Wait-ThermalStable
        $run = Invoke-LabRun $nx.run_seconds ("$($nx.tweak_id) " + $nx.stage)
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti (gioco chiuso o in pausa?). Riprovo.'; continue }
        Say ("   run: {0} FPS avg | 1% low {1}" -f $run.fps_avg, $run.fps_p1) 'Gray'
        $ph = if ("$($nx.stage)" -eq 'off') { 'pair_off' } else { 'pair_on' }
        $resp = LabApi 'Post' '/api/agent/lab/run' @{ phase = $ph; tweak_id = $nx.tweak_id; run = $run }
        if (Test-RunRejected $resp) { continue }
        if ($resp -and $resp.decision) {
          if ($resp.decision -eq 'kept') {
            Say-Ok ("   MANTENUTO: {0}" -f $resp.reason)
          } else {
            Say-Warn ("   {0}" -f $resp.reason) 'ROLLBACK'
            if (-not $resp.already_off) {
              $msg = Invoke-RestoreTweak "$($nx.tweak_id)"
              Say-Ok ("   {0}" -f $msg)
            } else {
              Say-Ok '   Gia disattivato dall ultima misura della sequenza.'
            }
            $script:LAB_APPLIED.Remove("$($nx.tweak_id)")
            LabEvent 'rolled_back' @{ tweak_id = $nx.tweak_id }
          }
          if ($resp.completed) { Say-Step '   Sequenza completata: genero il report...' 'LAB' }
        }
      }
      elseif ($act -eq 'rollback_tweaks') {
        $ids = @($nx.tweak_ids)
        Say ("`n[CONTROLLO STATISTICO] {0} tweak mantenuti non reggono la correzione per test multipli: li annullo." -f $ids.Count) 'Yellow'
        Say '   (Testare molti tweak di fila fa comparire per caso qualche falso positivo: questo passaggio li toglie di mezzo.)' 'DarkGray'
        foreach ($rid in $ids) {
          $msg = Invoke-RestoreTweak "$rid"
          $script:LAB_APPLIED.Remove("$rid")
          Say ("   {0}: {1}" -f $rid, $msg) 'DarkGray'
        }
        LabEvent 'tweaks_rolled_back' @{ tweak_ids = $ids }
      }
      elseif ($act -eq 'reboot_required') {
        $rebooted = $false
        try {
          $bootUtc = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime()
          $appliedUtc = ([DateTimeOffset]::Parse("$($nx.applied_at)")).UtcDateTime
          if ($bootUtc -gt $appliedUtc) { $rebooted = $true }
        } catch {}
        if ($rebooted) {
          Remove-LabResume
          Say ("`n[LAB] Riavvio rilevato: riprendo il test di {0}." -f $nx.tweak_id) 'Green'
          LabEvent 'reboot_done' @{ tweak_id = $nx.tweak_id }
        } else {
          Invoke-LabRebootPrompt $nx.tweak_id
          $labDone = $true
        }
      }
      elseif ($act -eq 'run_warmup') {
        Say ("   [WARM-UP] run di assestamento post-riavvio ({0}s, scartato dalle statistiche)" -f $nx.run_seconds) 'Cyan'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        $run = Invoke-LabRun $nx.run_seconds 'warmup'
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti. Riprovo.'; continue }
        LabApi 'Post' '/api/agent/lab/run' @{ phase = 'warmup'; tweak_id = $nx.tweak_id; run = $run } | Out-Null
        Say ("   warm-up: {0} FPS avg (ok, ora si misura sul serio)" -f $run.fps_avg) 'Gray'
      }
      elseif ($act -eq 'synergy_toggle') {
        $p = @($nx.pair)
        Say ("`n[SYNERGY {0}/{1}] {2} + {3} - preparo misura {4}" -f $nx.pair_num, $nx.pairs_total, $p[0], $p[1], "$($nx.stage)".ToUpper()) 'Cyan'
        foreach ($tid in $p) {
          if ($nx.stage -eq 'off') {
            $msg = Invoke-RestoreTweak "$tid"
            Say ("   OFF {0}: {1}" -f $tid, $msg) 'DarkGray'
          } else {
            $tw = $script:TWMAP[$tid]
            if ($tw) { Invoke-ApplyTracked $tw }
            Say ("   ON  {0}: riapplicato" -f $tid) 'DarkGray'
          }
        }
        Save-Backup
        Start-Sleep -Seconds 3
        LabEvent 'synergy_toggled' @{ stage = "$($nx.stage)" }
      }
      elseif ($act -eq 'run_synergy') {
        Say ("   [SYNERGY {0}] run {1}/{2} ({3}s)" -f "$($nx.stage)".ToUpper(), ([int]$nx.runs_done + 1), $nx.runs_target, $nx.run_seconds) 'Cyan'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        Wait-ThermalStable
        $run = Invoke-LabRun $nx.run_seconds ('synergy ' + $nx.stage)
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti. Riprovo.'; continue }
        Say ("   run: {0} FPS avg" -f $run.fps_avg) 'Gray'
        $ph = 'synergy_' + $nx.stage
        $resp = LabApi 'Post' '/api/agent/lab/run' @{ phase = $ph; run = $run }
        if (Test-RunRejected $resp) { continue }
        if ($resp -and $resp.pair_done -and $resp.synergy) {
          if ($resp.synergy.is_synergy) { Say-Ok ("   SINERGIA: insieme {0}% vs somma singoli {1}%" -f $resp.synergy.combined_delta_pct, $resp.synergy.individual_sum_pct) }
          else { Say-Info ("   Nessuna sinergia extra ({0}% vs {1}%)" -f $resp.synergy.combined_delta_pct, $resp.synergy.individual_sum_pct) }
        }
      }
      elseif ($act -eq 'run_validation') {
        Say ("`n[VALIDAZIONE] Sessione di gioco reale da {0} minuti con la configurazione finale. Gioca normalmente!" -f [int]($nx.run_seconds / 60)) 'Cyan'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        Wait-ThermalStable
        $run = Invoke-LabRun $nx.run_seconds 'validazione'
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti. Riprovo.'; continue }
        $resp = LabApi 'Post' '/api/agent/lab/run' @{ phase = 'validation'; run = $run }
        if (Test-RunRejected $resp) { continue }
        if ($resp -and $resp.validation) {
          Say ("   Reale: {0}% vs previsto {1}%" -f $resp.validation.real_gain_pct, $resp.validation.predicted_gain_pct) 'Yellow'
          if ($resp.validation.discrepancy) { Say-Warn '   Guadagno reale sotto il 50% del previsto: segnalato nel report.' }
        }
      }
      elseif ($act -eq 'run_recheck') {
        Say-Step ("   run di controllo baseline {0}/{1} ({2}s)" -f ([int]$nx.runs_done + 1), $nx.runs_target, $nx.run_seconds) 'DRIFT CHECK'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        Wait-ThermalStable
        $run = Invoke-LabRun $nx.run_seconds 'drift check'
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti. Riprovo.'; continue }
        $resp = LabApi 'Post' '/api/agent/lab/run' @{ phase = 'recheck'; run = $run }
        if (Test-RunRejected $resp) { continue }
        if ($resp) {
          if ($resp.stable) { Say-Ok ("   Baseline stabile (drift {0}%)" -f $resp.drift_pct) }
          elseif ($resp.rebaselined) { Say-Ok ("   Nuova baseline: {0} FPS avg (drift compensato)" -f $resp.stats.fps_avg) }
          elseif ($null -ne $resp.drift_pct) { Say-Warn ("   Drift {0}% rilevato: ri-misuro la baseline" -f $resp.drift_pct) }
        }
      }
      elseif ($act -eq 'run_test') {
        Say ("   [TEST {0}] run {1}/{2} ({3}s)" -f $nx.tweak_id, ([int]$nx.runs_done + 1), $nx.runs_target, $nx.run_seconds) 'Cyan'
        $g = Wait-LabGame
        if ($g -eq '__STOP__') { continue }
        Wait-ThermalStable
        $run = Invoke-LabRun $nx.run_seconds ("test " + $nx.tweak_id)
        if (-not $run) { Say-Warn '   Troppi pochi frame raccolti. Riprovo.'; continue }
        Say ("   run: {0} FPS avg | 1% low {1}" -f $run.fps_avg, $run.fps_p1) 'Gray'
        $resp = LabApi 'Post' '/api/agent/lab/run' @{ phase = 'test'; tweak_id = $nx.tweak_id; run = $run }
        if (Test-RunRejected $resp) { continue }
        if ($resp -and $resp.decision) {
          if ($resp.decision -eq 'kept') {
            Say-Ok ("   MANTENUTO: {0}" -f $resp.reason)
          } else {
            Say-Warn ("   {0}" -f $resp.reason) 'ROLLBACK'
            $msg = Invoke-RestoreTweak "$($nx.tweak_id)"
            $script:LAB_APPLIED.Remove("$($nx.tweak_id)")
            LabEvent 'rolled_back' @{ tweak_id = $nx.tweak_id }
            Say-Ok ("   {0}" -f $msg)
          }
          if ($resp.completed) { Say-Step '   Sequenza completata: genero il report...' 'LAB' }
        }
      }
      elseif ($act -eq 'abort') {
        Say "`n[LAB] Interruzione richiesta dal web: annullo tutti i tweak applicati dal Lab..." 'Yellow'
        $ids = @($nx.rollback_ids)
        if ($ids.Count -eq 0) { $ids = @($script:LAB_APPLIED) }
        foreach ($rid in $ids) { $msg = Invoke-RestoreTweak "$rid"; Say ("   {0}: {1}" -f $rid, $msg) 'DarkGray' }
        $script:LAB_APPLIED.Clear()
        LabEvent 'aborted' $null
        Say-Ok 'Tutto annullato. Sessione interrotta.'
        $labDone = $true
      }
      elseif ($act -eq 'complete') {
        Say "`n[FASE 4/4] REPORT" 'Cyan'
        if ($nx.report) {
          $rep = $nx.report
          Say ("   Gioco: {0}" -f $rep.game) 'Gray'
          Say ("   Baseline: {0} FPS -> Finale: {1} FPS ({2}%)" -f $rep.baseline.fps_avg, $rep.final.fps_avg, $rep.total_gain_pct) 'Yellow'
          Say ("   Tweak mantenuti: {0} su {1} testati" -f @($rep.kept).Count, $rep.tweaks_tested) 'Gray'
        }
        Say "`n[ OK ] Laboratorio completato! Apri FrameForge -> Laboratorio per il report dettagliato." 'Green'
        $labDone = $true
      }
      else { Start-Sleep -Seconds 4 }
    }
  } finally { Stop-Fps }
  return
}

if ($MODE -eq 'bufferbloat') {
  Say "`n== FrameForge Agent - Test rete / Bufferbloat ==" 'Cyan'
  Say '   Non usare internet durante il test (~15s). Misuro latenza a riposo e sotto carico.' 'DarkGray'
  Run-Bufferbloat
  return
}


if ($MODE -eq 'monitor') {
  Say "`n[STEP] Monitoraggio live avviato. Lascia aperta questa finestra. Premi Ctrl+C per fermare (o Stop dal browser)." 'Cyan'
  Say '   Apri FrameForge -> Live per i grafici in tempo reale.' 'DarkGray'
  Start-Fps
  $noFpsCount = 0
  try {
    while ($true) {
      $s = Get-TelemetrySample
      $f = Get-Fps
      if ($f) {
        $s.fps = $f.fps; $s.game = $f.game
        if ($null -ne $f.latency_ms) { $s.latency_ms = $f.latency_ms }
        if ($f.gd) {
          $s.ft_p99 = $f.gd.ft_p99; $s.ft_worst = $f.gd.ft_worst; $s.hitches = $f.gd.hitches; $s.pace_dev = $f.gd.pace_dev
          $s.ft_cv = $f.gd.ft_cv; $s.hitch_thr = $f.gd.hitch_thr
          if ($f.gd.hist) { $s.ft_hist = $f.gd.hist; $s.ft_n = $f.gd.hist_n }
        }
        $noFpsCount = 0
      }
      elseif ($script:PM_ON) { $noFpsCount++; if ($noFpsCount -eq 10) { Show-FpsDiag } }
      $stopFromWeb = Send-Telemetry $s
      $g = if ($s.ContainsKey('gpu_util')) { ("GPU {0}% {1}C {2}MHz" -f $s.gpu_util, $s.gpu_temp, $s.gpu_clock) } else { 'GPU n/d' }
      $ct = if ($s.ContainsKey('cpu_temp')) { ("{0}C" -f $s.cpu_temp) } else { '' }
      $lt = if ($s.ContainsKey('latency_ms')) { (" {0}ms" -f $s.latency_ms) } else { '' }
      $fp = if ($s.ContainsKey('fps')) { (" | {0} FPS ({1}){2}" -f $s.fps, $s.game, $lt) } else { '' }
      Say ("   CPU {0}% {1} | RAM {2}% | {3}{4}" -f $s.cpu_util, $ct, $s.ram_used_pct, $g, $fp)
      if ($stopFromWeb) {
        Say "`n[INFO] Stop richiesto dal browser. Chiudo il monitor..." 'Yellow'
        break
      }
      Start-Sleep -Milliseconds 1000
    }
  } finally { Stop-Fps }
  return
}

if ($MODE -eq 'prematch') {
  Say "`n== FrameForge Agent - Modalita Prima del match ==" 'Cyan'
  $setPower = __PREMATCH_POWER__
  $prevPlan = ''
  if ($setPower) {
    $out = powercfg /getactivescheme
    $prevPlan = ([regex]::Match($out, '([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})')).Value
    if ($prevPlan) { Say ("   Piano energetico attuale salvato: {0}" -f $prevPlan) 'DarkGray' }
    powercfg /setactive scheme_min 2>$null
    Say-Ok "   Piano Prestazioni elevate attivato."
  } else {
    Say-Info "   Piano energetico lasciato invariato (da impostazioni)."
  }
  $apps = @(__PREMATCH_APPS__)
  $closed = 0
  foreach ($a in $apps) {
    $p = Get-Process -Name $a -ErrorAction SilentlyContinue
    if ($p) { Stop-Process -InputObject $p -Force -ErrorAction SilentlyContinue; $closed++ }
  }
  Say-Ok ("   App in background chiuse: {0} (su {1} selezionate)" -f $closed, $apps.Count)
  Say "`n   Boost attivo. Avvia pure il tuo gioco. Buon match!" 'Yellow'
  Read-Host "`nPremi INVIO quando hai finito di giocare per ripristinare tutto"
  if ($setPower) {
    if ($prevPlan) { powercfg /setactive $prevPlan 2>$null; Say-Ok "   Piano energetico originale ripristinato." }
    else { powercfg /setactive scheme_balanced 2>$null; Say-Ok "   Piano energetico bilanciato ripristinato." }
  }
  Say "`n[ OK ] Le app chiuse puoi riaprirle normalmente. A presto!" 'Cyan'
  return
}

if ($MODE -eq 'booster') {
  Say "`n== FrameForge Agent - GAME BOOSTER ==" 'Cyan'
  Say '   Sorveglio i giochi in avvio: quando ne rilevo uno ti propongo il boost con 5 secondi per annullare.' 'Gray'
  Say '   NIENTE parte in automatico al 100%: hai sempre la scelta. A fine partita ripristino tutto. Ctrl+C per uscire.' 'Gray'
  try { Add-Type -AssemblyName System.Windows.Forms } catch {}
  $doPower = __BOOSTER_POWER__
  $doPriority = __BOOSTER_PRIORITY__
  $doPurge = __BOOSTER_PURGE__
  $apps = @(__BOOSTER_APPS__)
  Say ("   Azioni configurate (FrameForge -> Games): priorita={0} energia={1} purgeRAM={2} appDaChiudere={3}" -f $doPriority, $doPower, $doPurge, $apps.Count) 'DarkGray'
  if (-not (Test-Admin) -and (Test-FpsCapable) -ne 'ok') { Say-Info '   Cattura FPS non ancora autorizzata: apri una volta la GUI (Ottimizza) e riavvia il PC. Intanto rilevo il gioco dalla finestra a schermo intero.' }
  if (-not ('FFWin' -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class FFWin {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
}
"@ 2>$null
  }
  function Test-KeyCancel { try { if ([Console]::KeyAvailable) { [void][Console]::ReadKey($true); return $true } } catch {}; return $false }
  function Get-FullscreenGame {
    try {
      $h = [FFWin]::GetForegroundWindow()
      if ($h -eq [IntPtr]::Zero) { return $null }
      $rc = New-Object FFWin+RECT
      [void][FFWin]::GetWindowRect($h, [ref]$rc)
      $mw = [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize.Width
      $mh = [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize.Height
      if (($rc.R - $rc.L) -lt ($mw - 2) -or ($rc.B - $rc.T) -lt ($mh - 2)) { return $null }
      $gp = [uint32]0; [void][FFWin]::GetWindowThreadProcessId($h, [ref]$gp)
      $p = Get-Process -Id $gp -ErrorAction SilentlyContinue
      if (-not $p) { return $null }
      $skipRe = 'explorer|dwm|powershell|pwsh|WindowsTerminal|cmd|chrome|msedge|firefox|opera|brave|Code|devenv|obs64|obs32|Taskmgr|SearchHost|ShellExperienceHost|ApplicationFrameHost|LockApp|vlc|Photos|Netflix|Spotify'
      if ($p.Name -match $skipRe) { return $null }
      return $p
    } catch { return $null }
  }
  Start-Fps
  $boosted = $false; $skipUntilExit = $false; $bGame = ''; $bStart = $null; $prevPlan = ''
  $curName = ''; $detCount = 0; $lostCount = 0; $script:BACTS = @()
  # Recap post-partita: accumulatori sessione
  $script:RCP_FPS = New-Object System.Collections.ArrayList
  $script:RCP_LATS = 0.0; $script:RCP_LATN = 0; $script:RCP_HIT = 0; $script:RCP_TICK = 0
  $script:RCP_GTS = 0; $script:RCP_GTN = 0; $script:RCP_GTMAX = 0; $script:RCP_CTMAX = 0
  Say "`n[SORVEGLIANZA ATTIVA] Avvia pure il tuo gioco quando vuoi." 'Green'
  try {
    while ($true) {
      $name = ''; $gpid = 0
      $f = Get-Fps
      if ($f -and $f.fps -ge 15) { $name = $f.game }
      if ($boosted -and $f -and $f.fps -gt 0) {
        [void]$script:RCP_FPS.Add([int]$f.fps)
        if ($f.latency_ms) { $script:RCP_LATS += $f.latency_ms; $script:RCP_LATN++ }
        if ($f.gd -and $f.gd.hitches) { $script:RCP_HIT += [int]$f.gd.hitches }
        $script:RCP_TICK++
        if (($script:RCP_TICK % 15) -eq 1) {
          try {
            $tt = Get-LhmTemps
            if ($tt -and $tt.ContainsKey('gpu_temp')) { $gv = [int]$tt.gpu_temp; $script:RCP_GTS += $gv; $script:RCP_GTN++; if ($gv -gt $script:RCP_GTMAX) { $script:RCP_GTMAX = $gv } }
            if ($tt -and $tt.ContainsKey('cpu_temp')) { $cv = [int]$tt.cpu_temp; if ($cv -gt $script:RCP_CTMAX) { $script:RCP_CTMAX = $cv } }
          } catch {}
        }
      }
      if (-not $name) { $p = Get-FullscreenGame; if ($p) { $name = $p.Name; $gpid = $p.Id } }
      if ($name) {
        if ($name -eq $curName) { $detCount++ } else { $curName = $name; $detCount = 1 }
        $lostCount = 0
      } else {
        $lostCount++
        if ($lostCount -ge 8 -and -not $boosted -and -not $skipUntilExit) { $curName = ''; $detCount = 0 }
      }
      if (-not $boosted -and -not $skipUntilExit -and $curName -and $detCount -eq 3) {
        Say ("`n[GIOCO RILEVATO] {0}" -f $curName) 'Yellow'
        Say '   Boost tra 5 secondi... premi un tasto QUALSIASI per ANNULLARE il boost di questa sessione.' 'Yellow'
        while (Test-KeyCancel) {}
        $cancel = $false
        for ($i = 5; $i -ge 1; $i--) {
          Write-Host ("   {0}..." -f $i) -ForegroundColor DarkGray
          $t0 = Get-Date
          while (((Get-Date) - $t0).TotalMilliseconds -lt 1000) {
            if (Test-KeyCancel) { $cancel = $true; break }
            Start-Sleep -Milliseconds 100
          }
          if ($cancel) { break }
        }
        if ($cancel) {
          Say '   Boost ANNULLATO: nessuna modifica. Riprendo la sorveglianza a fine partita.' 'DarkYellow'
          $skipUntilExit = $true
        } else {
          $acts = New-Object System.Collections.Generic.List[string]
          if ($doPriority) {
            if (-not $gpid) { $pp = Get-Process -Name ($curName -replace '\.exe$', '') -ErrorAction SilentlyContinue | Select-Object -First 1; if ($pp) { $gpid = $pp.Id } }
            if ($gpid) { try { (Get-Process -Id $gpid).PriorityClass = 'High'; $acts.Add('priorita_high'); Say-Ok '   Priorita CPU del gioco: HIGH.' } catch {} }
          }
          if ($doPower) {
            $out = powercfg /getactivescheme
            $prevPlan = ([regex]::Match($out, '([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})')).Value
            powercfg /setactive scheme_min 2>$null
            $acts.Add('piano_energetico'); Say-Ok '   Piano Prestazioni elevate attivo (solo durante il gioco).'
          }
          if ($apps.Count -gt 0) {
            $closed = 0
            foreach ($a in $apps) { $pr = Get-Process -Name $a -ErrorAction SilentlyContinue; if ($pr) { Stop-Process -InputObject $pr -Force -ErrorAction SilentlyContinue; $closed++ } }
            if ($closed -gt 0) { $acts.Add("app_chiuse_$closed"); Say-Ok ("   App in background chiuse: {0}." -f $closed) }
          }
          if ($doPurge) { Clear-StandbyList; $acts.Add('purge_ram'); Say-Ok '   RAM standby svuotata.' }
          $boosted = $true; $bGame = $curName; $bStart = Get-Date; $script:BACTS = @($acts)
          Say ("`n   Boost attivo! Buona partita! Ripristino tutto quando esci da {0}." -f ($curName -replace '\.exe$', '')) 'Yellow'
        }
      }
      if (($boosted -or $skipUntilExit) -and $lostCount -ge 8) {
        if ($boosted) {
          Say ("`n[STEP] Fine partita {0}: ripristino..." -f ($bGame -replace '\.exe$', '')) 'Cyan'
          if ($doPower) { if ($prevPlan) { powercfg /setactive $prevPlan 2>$null } else { powercfg /setactive scheme_balanced 2>$null }; Say-Ok '   Piano energetico ripristinato.' }
          $dur = [int]((Get-Date) - $bStart).TotalSeconds
          $recap = $null
          if ($script:RCP_FPS.Count -ge 5) {
            $arr = [int[]]$script:RCP_FPS.ToArray(); [Array]::Sort($arr)
            $rn = $arr.Length
            $sum = 0; foreach ($v in $arr) { $sum += $v }
            $recap = @{ fps_avg = [int][math]::Round($sum / $rn); fps_low = $arr[[math]::Max(0, [int][math]::Floor(0.01 * $rn))]; fps_min = $arr[0]; fps_max = $arr[$rn - 1]; samples = $rn }
            if ($script:RCP_LATN -gt 0) { $recap.latency_ms = [int][math]::Round($script:RCP_LATS / $script:RCP_LATN) }
            if ($script:RCP_HIT -gt 0) { $recap.hitches = $script:RCP_HIT }
            if ($script:RCP_GTN -gt 0) { $recap.gpu_temp_max = $script:RCP_GTMAX; $recap.gpu_temp_avg = [int][math]::Round($script:RCP_GTS / $script:RCP_GTN) }
            if ($script:RCP_CTMAX -gt 0) { $recap.cpu_temp_max = $script:RCP_CTMAX }
          }
          $__bs = @{ game = ($bGame -replace '\.exe$', ''); duration_s = $dur; actions = @($script:BACTS); ended_at = (Get-Date).ToString('o') }
          if ($recap) { $__bs.recap = $recap }
          $body = [System.Text.Encoding]::UTF8.GetBytes((@{ boost_session = $__bs } | ConvertTo-Json -Depth 5 -Compress))
          try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{ 'X-Agent-Token' = $TOKEN; 'X-Device' = $env:COMPUTERNAME } -Body $body | Out-Null } catch {}
          if ($recap) {
            Say ("`n   == RECAP PARTITA: {0} ({1} min) ==" -f ($bGame -replace '\.exe$', ''), [math]::Round($dur / 60, 1)) 'Cyan'
            Say ("   FPS medi: {0}  |  1% low: {1}  |  min/max: {2}/{3}" -f $recap.fps_avg, $recap.fps_low, $recap.fps_min, $recap.fps_max) 'White'
            if ($recap.ContainsKey('gpu_temp_max')) { Say ("   GPU: max {0} C (media {1} C)" -f $recap.gpu_temp_max, $recap.gpu_temp_avg) 'White' }
            if ($recap.ContainsKey('latency_ms')) { Say ("   Latenza media: {0} ms" -f $recap.latency_ms) 'White' }
            Say '   Recap completo su forgefps.dev -> Gaming -> Sessioni.' 'DarkGray'
          }
          Say ("   Sessione registrata ({0} min). Torno in sorveglianza." -f [math]::Round($dur / 60, 1)) 'DarkGray'
        } else {
          Say "`n[INFO] Partita finita (boost annullato). Torno in sorveglianza." 'DarkGray'
        }
        $boosted = $false; $skipUntilExit = $false; $bGame = ''; $prevPlan = ''; $curName = ''; $detCount = 0
        $script:RCP_FPS = New-Object System.Collections.ArrayList
        $script:RCP_LATS = 0.0; $script:RCP_LATN = 0; $script:RCP_HIT = 0; $script:RCP_TICK = 0
        $script:RCP_GTS = 0; $script:RCP_GTN = 0; $script:RCP_GTMAX = 0; $script:RCP_CTMAX = 0
      }
      Start-Sleep -Milliseconds 2000
    }
  } finally {
    Stop-Fps
    if ($boosted -and $doPower) { if ($prevPlan) { powercfg /setactive $prevPlan 2>$null } else { powercfg /setactive scheme_balanced 2>$null } }
    Say "`n[ OK ] Game Booster fermato. Tutto ripristinato." 'Cyan'
  }
  return
}

# default: sync (safe)
Say "`n[STEP] Rilevamento hardware, salute e avvio..." 'Cyan'
if (-not (Test-Admin)) { Say-Info '   Suggerimento: esegui in PowerShell (Amministratore) per temperature CPU/GPU reali e analisi piu precisa.' }
$specs = Get-Specs
Say ("   CPU: {0}" -f $specs.cpu); Say ("   GPU: {0}" -f $specs.gpu)
Say ("   MB : {0}  ({1} {2})" -f $specs.motherboard, $specs.cpu_socket, $specs.chipset)
$health = Get-Health
if ($health.ContainsKey('cpu_temp')) { Say ("   Temp CPU: {0}C  |  Temp GPU: {1}C" -f $health.cpu_temp, $(if($health.ContainsKey('gpu_temp')){$health.gpu_temp}else{'n/d'})) 'DarkGray' }
elseif (Test-Admin) {
  Say-Info '   [diag] Temp CPU non leggibile. Sensori temperatura rilevati:'
  if ($script:LHM_LAST) { Say ("         " + $script:LHM_LAST) 'DarkGray' }
  else { Say '         (nessuno)' 'DarkGray' }
  $mi = Test-MemoryIntegrity
  $bl = Test-VulnerableDriverBlocklist
  Say-Info ("   Integrita memoria: {0}  |  Blocklist driver vulnerabili: {1}" -f $(if($mi){'ATTIVA'}else{'disattivata'}), $(if($bl){'ATTIVA'}else{'disattivata'})) 'diag'
  if ($mi -or $bl) {
    Say-Warn '   CAUSA: Windows sta bloccando il driver dei sensori CPU (protezione di sicurezza).'
    Say '       La temperatura CPU sulle AMD Ryzen richiede questo driver di basso livello.' 'Gray'
    if ($mi) {
      Say '       -> Disattiva "Integrita della memoria": Impostazioni > Privacy e sicurezza >' 'Gray'
      Say '          Sicurezza di Windows > Sicurezza dispositivo > Isolamento core > OFF, poi riavvia.' 'Gray'
    }
    if ($bl) {
      Say '       -> La "Blocklist driver vulnerabili" e attiva (default su Windows 11) e blocca questo driver.' 'Gray'
      Say '          E una protezione di sicurezza: si consiglia di lasciarla attiva.' 'Gray'
    }
    Say '       (La temperatura GPU funziona gia e non richiede alcuna modifica.)' 'DarkGray'
  } else {
    Say-Info '   Il driver sensori CPU non ha risposto (possibile blocco antivirus). La temp GPU funziona comunque.'
  }
}
Send-Data $specs $health (Get-StartupList)
$games = Get-Games
if ($games.Count -gt 0) { Send-Games $games; Say ("   Giochi rilevati: {0}" -f $games.Count) 'DarkGray' }
$running = Get-RunningApps
Send-Running $running
Say ("   App in background attive: {0}" -f $running.Count) 'DarkGray'
Say "`n[ OK ] Dati inviati! Apri FrameForge -> Il mio PC per analisi e consigli." 'Green'
'''


# ---------------------------------------------------------------------------
# La GUI locale vive in agent_gui.html, non qui dentro.
#
# Erano 2.121 righe di HTML/CSS/JS in una here-string PowerShell dentro una
# stringa raw Python: tre livelli di annidamento, quindi niente evidenziazione,
# niente linting, niente formattatore, e insidie di quoting su due livelli.
# Il file viene reinserito qui all'import, cosi' `PS_SCRIPT` resta completo per
# tutti quelli che lo consumano (routers/pc.py, desktop_agent, l'harness di
# test) e nulla a valle deve sapere che la sorgente e' cambiata.
#
# Vincolo da rispettare in agent_gui.html: il contenuto finisce in una
# here-string a singolo apice (@'...'@), quindi nessuna riga puo' iniziare con
# `'@` — verificato dal test in tests_unit/test_agent_gui_asset.py. In compenso
# PowerShell non espande nulla, quindi il JS puo' usare $ e ${} liberamente.
_GUI_HTML_PATH = _Path(__file__).with_name("agent_gui.html")


def _load_gui_html() -> str:
    try:
        return _GUI_HTML_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:  # pragma: no cover - deploy incompleto
        raise RuntimeError(
            f"agent_gui.html non trovato accanto a ps_agent.py ({_GUI_HTML_PATH}). "
            "Va distribuito insieme al backend: senza, l'agent non ha interfaccia."
        )


GUI_HTML = _load_gui_html()
PS_SCRIPT = PS_SCRIPT.replace("__GUI_HTML__", GUI_HTML)
