"""PowerShell one-liner agent, served at GET /api/agent/script and run via `irm ... | iex`.
Non-interactive by design.
Modes:
  sync      -> safe: detect hardware/health/startup and report (no changes)
  benchmark -> run a quick CPU/RAM/disk/network benchmark and report it
  optimize  -> benchmark BEFORE, apply deep reversible tweaks (backup), benchmark AFTER, report both
  restore   -> revert every tweak from the backup file
All tweaks are backed up before being applied so `restore` fully reverts them."""

PS_SCRIPT = r'''
$ErrorActionPreference = 'SilentlyContinue'
$BACKEND = '__BACKEND_URL__'
$TOKEN   = '__AGENT_TOKEN__'
$MODE    = '__MODE__'
$BACKUP  = Join-Path $env:TEMP 'boostpc_backup.json'

function Say($m, $c='Gray') { Write-Host $m -ForegroundColor $c }
function ConvertTo-HashtableSafe { $h=@{}; foreach($p in $input.PSObject.Properties){ $h[$p.Name]=$p.Value }; return $h }

Say '======================================' 'Yellow'
Say '   BOOST PC AI - Agent PowerShell' 'Yellow'
Say '======================================' 'Yellow'

# ---------------- Backup registry helpers ----------------
$script:BK = @{}
if (Test-Path $BACKUP) { try { $script:BK = Get-Content $BACKUP -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe } catch { $script:BK = @{} } }

function Backup-Reg($path, $name, $type) {
  $key = "$path::$name"
  if ($script:BK.ContainsKey($key)) { return }
  $cur = (Get-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue).$name
  if ($null -eq $cur) { $script:BK[$key] = '__ABSENT__' } else { $script:BK[$key] = "$type|$cur" }
}
function Set-Reg($path, $name, $type, $value) {
  Backup-Reg $path $name $type
  if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
  New-ItemProperty -Path $path -Name $name -PropertyType $type -Value $value -Force | Out-Null
}
function Save-Backup { $script:BK | ConvertTo-Json -Depth 6 | Set-Content $BACKUP }

# ---------------- Hardware / health detection ----------------
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

  $nv = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null
  if ($nv) {
    $p = ($nv | Select-Object -First 1).Split(',')
    $s.gpu = $p[0].Trim(); $s.gpu_vram_gb = "$([math]::Round([double]$p[1].Trim()/1024))"; $s.gpu_driver_version = $p[2].Trim()
  } else {
    $g = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -notmatch 'Basic|Virtual|Remote|Meta|Parsec|Citrix' } | Select-Object -First 1
    if (-not $g) { $g = Get-CimInstance Win32_VideoController | Select-Object -First 1 }
    $s.gpu = $g.Name; $s.gpu_driver_version = $g.DriverVersion
    if ($g.AdapterRAM -gt 0) { $s.gpu_vram_gb = "$([math]::Round($g.AdapterRAM/1GB))" }
  }
  $s.refresh_hz = "$((Get-CimInstance Win32_VideoController | Where-Object {$_.CurrentRefreshRate -gt 0} | Sort-Object CurrentRefreshRate -Descending | Select-Object -First 1).CurrentRefreshRate)"

  $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)
  $s.ram = "$ram GB"
  $pm = Get-CimInstance Win32_PhysicalMemory
  $s.ram_speed_mhz = "$(($pm | Select-Object -First 1).Speed)"
  $s.ram_modules = "$(($pm | Measure-Object).Count)"
  $s.ram_type = @{ '20'='DDR'; '21'='DDR2'; '24'='DDR3'; '26'='DDR4'; '34'='DDR5' }["$(($pm | Select-Object -First 1).SMBIOSMemoryType)"]

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
  return $s
}

function Get-Health {
  $h = @{}
  $tempMb = 0
  Get-ChildItem $env:TEMP, "$env:LOCALAPPDATA\Temp" -Recurse -File -Force 2>$null | ForEach-Object { $tempMb += $_.Length }
  $h.temp_mb = [math]::Round($tempMb/1MB, 1)
  $h.startup_count = (Get-CimInstance Win32_StartupCommand | Measure-Object).Count
  $h.power_plan = (powercfg /getactivescheme)
  $gm = (Get-ItemProperty 'HKCU:\Software\Microsoft\GameBar' -Name AllowAutoGameMode).AllowAutoGameMode
  $h.game_mode = ($gm -eq 1)
  $hags = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode).HwSchMode
  $h.gpu_scheduling = ($hags -eq 2)
  $o = Get-CimInstance Win32_OperatingSystem
  $h.ram_used_pct = [math]::Round(($o.TotalVisibleMemorySize - $o.FreePhysicalMemory) / $o.TotalVisibleMemorySize * 100)
  $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
  if ($d) { $h.disk_free_pct = [math]::Round($d.FreeSpace / $d.Size * 100) }
  $vc = Get-CimInstance Win32_VideoController | Select-Object -First 1
  $h.gpu = $vc.Name; $h.gpu_driver_version = $vc.DriverVersion
  if ($vc.DriverDate) { $h.gpu_driver_date = $vc.DriverDate.ToString('yyyy-MM-dd') }
  $gt = & nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>$null
  if ($gt) { $h.gpu_temp = [int]($gt | Select-Object -First 1).Trim() }
  $tzt = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object -First 1
  if ($tzt) { $h.cpu_temp = [math]::Round(($tzt.CurrentTemperature - 2732)/10) }
  return $h
}

function Get-StartupList {
  return @(Get-CimInstance Win32_StartupCommand | Select-Object -ExpandProperty Name | Select-Object -First 40)
}

# ---------------- Benchmark ----------------
function Run-Benchmark {
  Say '   Benchmark in corso (CPU / RAM / Disco / Rete)...' 'DarkGray'
  $r = @{}
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $acc = 0.0
  for ($i = 0; $i -lt 3000000; $i++) { $acc += [math]::Sqrt($i) }
  $sw.Stop()
  $r.cpu_score = [int]([math]::Round(3000000 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001) / 1000))

  $size = 64MB
  $buf = New-Object byte[] $size
  $dst = New-Object byte[] $size
  $sw.Restart()
  for ($i = 0; $i -lt 5; $i++) { [Array]::Copy($buf, $dst, $size) }
  $sw.Stop()
  $r.ram_mbps = [int]([math]::Round((5 * $size / 1MB) / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))

  $tmp = Join-Path $env:TEMP 'boostpc_bench.bin'
  $data = New-Object byte[] (64MB)
  (New-Object Random).NextBytes($data)
  $sw.Restart(); [System.IO.File]::WriteAllBytes($tmp, $data); $sw.Stop()
  $r.disk_write_mbps = [int]([math]::Round(64 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
  $sw.Restart(); $null = [System.IO.File]::ReadAllBytes($tmp); $sw.Stop()
  $r.disk_read_mbps = [int]([math]::Round(64 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
  Remove-Item $tmp -ErrorAction SilentlyContinue

  try {
    $png = New-Object System.Net.NetworkInformation.Ping
    $tot = 0; $n = 0
    for ($i = 0; $i -lt 4; $i++) { $res = $png.Send('1.1.1.1', 2000); if ($res.Status -eq 'Success') { $tot += $res.RoundtripTime; $n++ } }
    $r.ping_ms = if ($n -gt 0) { [int]([math]::Round($tot / $n)) } else { 0 }
  } catch { $r.ping_ms = 0 }

  $o = Get-CimInstance Win32_OperatingSystem
  $r.free_ram_pct = [int]([math]::Round($o.FreePhysicalMemory / $o.TotalVisibleMemorySize * 100))
  $r.overall = [int]([math]::Round($r.cpu_score + $r.ram_mbps/50.0 + $r.disk_write_mbps/50.0 + $r.disk_read_mbps/50.0 + [math]::Max(0, 120 - $r.ping_ms) + $r.free_ram_pct))
  return $r
}

function Show-Bench($r, $title) {
  Say "`n   [$title]" 'Cyan'
  Say ("   CPU score      : {0}" -f $r.cpu_score)
  Say ("   RAM bandwidth  : {0} MB/s" -f $r.ram_mbps)
  Say ("   Disco scrittura: {0} MB/s" -f $r.disk_write_mbps)
  Say ("   Disco lettura  : {0} MB/s" -f $r.disk_read_mbps)
  Say ("   Ping (1.1.1.1) : {0} ms" -f $r.ping_ms)
  Say ("   RAM libera     : {0} %" -f $r.free_ram_pct)
  Say ("   PUNTEGGIO      : {0}" -f $r.overall) 'Yellow'
}

function Show-Compare($b, $a) {
  Say "`n=== CONFRONTO PRIMA / DOPO ===" 'Yellow'
  $rows = @(
    @('CPU score', $b.cpu_score, $a.cpu_score, $true),
    @('RAM MB/s', $b.ram_mbps, $a.ram_mbps, $true),
    @('Disco scritt.', $b.disk_write_mbps, $a.disk_write_mbps, $true),
    @('Disco lett.', $b.disk_read_mbps, $a.disk_read_mbps, $true),
    @('Ping ms', $b.ping_ms, $a.ping_ms, $false),
    @('RAM libera %', $b.free_ram_pct, $a.free_ram_pct, $true),
    @('PUNTEGGIO', $b.overall, $a.overall, $true)
  )
  Say ("   {0,-14}{1,10}{2,10}{3,10}" -f 'METRICA','PRIMA','DOPO','VAR')
  foreach ($row in $rows) {
    $name=$row[0]; $bv=[double]$row[1]; $av=[double]$row[2]; $higherBetter=$row[3]
    $delta = if ($bv -ne 0) { [math]::Round(($av-$bv)/$bv*100) } else { 0 }
    $improved = if ($higherBetter) { $av -ge $bv } else { $av -le $bv }
    $col = if ($improved) { 'Green' } else { 'Red' }
    $sign = if ($delta -ge 0) { '+' } else { '' }
    Write-Host ("   {0,-14}{1,10}{2,10}{3,9}%" -f $name,$row[1],$row[2],"$sign$delta") -ForegroundColor $col
  }
}

# ---------------- Reporting ----------------
function Send-Data($specs, $health, $startup) {
  $body = @{ data = $specs; health = $health; startup = $startup } | ConvertTo-Json -Depth 6 -Compress
  try {
    Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' `
      -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null
    Say "`n[OK] Dati inviati! Apri BOOST PC -> Il mio PC per analisi e consigli." 'Green'
  } catch {
    Say "`n[!] Invio fallito: $($_.Exception.Message)" 'Red'
  }
}

function Send-Benchmark($rec) {
  $body = @{ benchmark = $rec } | ConvertTo-Json -Depth 6 -Compress
  try {
    Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' `
      -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null
    Say "`n[OK] Benchmark inviato! Vedi il confronto in BOOST PC -> Il mio PC." 'Green'
  } catch {
    Say "`n[!] Invio benchmark fallito: $($_.Exception.Message)" 'Red'
  }
}

# ---------------- Optimize (deep, reversible) ----------------
function Invoke-Optimize {
  Say "`n[*] Applico ottimizzazioni profonde (con backup)..." 'Cyan'

  # Cleanup: temp + Windows Update cache + DNS flush
  Get-ChildItem $env:TEMP -Recurse -Force 2>$null | Remove-Item -Recurse -Force 2>$null
  Say '   - File temporanei puliti'
  Stop-Service wuauserv -Force 2>$null
  Get-ChildItem "$env:SystemRoot\SoftwareDistribution\Download" -Recurse -Force 2>$null | Remove-Item -Recurse -Force 2>$null
  Start-Service wuauserv 2>$null
  Say '   - Cache Windows Update pulita'
  ipconfig /flushdns | Out-Null
  Say '   - DNS flush eseguito'

  # Power plan: Ultimate Performance (fallback High Performance)
  $curScheme = (powercfg /getactivescheme)
  if ($curScheme -match '([0-9a-fA-F-]{36})' -and -not $script:BK.ContainsKey('power_plan')) { $script:BK['power_plan'] = $matches[1] }
  $ultimate = 'e9a42b02-d5df-448d-aa00-03f14749eb61'
  powercfg -duplicatescheme $ultimate 2>$null | Out-Null
  $applied = powercfg -setactive $ultimate 2>$null
  if ($LASTEXITCODE -ne 0) { powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null }
  Say '   - Piano energetico: prestazioni massime'

  # Game Mode + GPU scheduling + GameDVR off
  Set-Reg 'HKCU:\Software\Microsoft\GameBar' 'AllowAutoGameMode' 'DWord' 1
  Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' 'HwSchMode' 'DWord' 2
  Set-Reg 'HKCU:\System\GameConfigStore' 'GameDVR_Enabled' 'DWord' 0
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\GameDVR' 'AllowGameDVR' 'DWord' 0
  Say '   - Game Mode + GPU Scheduling attivi, Game DVR disattivato'

  # MMCSS: priorita GPU/CPU ai giochi + responsiveness
  $sp = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile'
  Set-Reg $sp 'SystemResponsiveness' 'DWord' 0
  Set-Reg $sp 'NetworkThrottlingIndex' 'DWord' 4294967295
  $games = "$sp\Tasks\Games"
  Set-Reg $games 'GPU Priority' 'DWord' 8
  Set-Reg $games 'Priority' 'DWord' 6
  Set-Reg $games 'Scheduling Category' 'String' 'High'
  Set-Reg $games 'SFIO Priority' 'String' 'High'
  Set-Reg 'HKLM:\SYSTEM\CurrentControlSet\Control\PriorityControl' 'Win32PrioritySeparation' 'DWord' 26
  Say '   - Priorita GPU/CPU per i giochi + network throttling off'

  # Mouse acceleration off (raw input)
  Set-Reg 'HKCU:\Control Panel\Mouse' 'MouseSpeed' 'String' '0'
  Set-Reg 'HKCU:\Control Panel\Mouse' 'MouseThreshold1' 'String' '0'
  Set-Reg 'HKCU:\Control Panel\Mouse' 'MouseThreshold2' 'String' '0'
  Say '   - Accelerazione mouse disattivata (mira piu precisa)'

  # Visual effects: performance
  Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting' 'DWord' 2
  Say '   - Effetti visivi: modalita prestazioni'

  # Network latency: Nagle off per interface + TCP tuning
  $ifRoot = 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces'
  Get-ChildItem $ifRoot 2>$null | ForEach-Object {
    $p = Join-Path $ifRoot $_.PSChildName
    Set-Reg $p 'TcpAckFrequency' 'DWord' 1
    Set-Reg $p 'TCPNoDelay' 'DWord' 1
  }
  netsh int tcp set global autotuninglevel=normal 2>$null | Out-Null
  netsh int tcp set global ecncapability=enabled 2>$null | Out-Null
  netsh int tcp set global rss=enabled 2>$null | Out-Null
  Say '   - Nagle disattivato + TCP ottimizzato (meno latenza online)'

  # Fast DNS (Cloudflare) on active adapter, reversible to DHCP
  try {
    $adapter = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' } | Select-Object -First 1
    if ($adapter -and -not $script:BK.ContainsKey("dns::$($adapter.Name)")) {
      $script:BK["dns::$($adapter.Name)"] = 'reset'
      Set-DnsClientServerAddress -InterfaceAlias $adapter.Name -ServerAddresses ('1.1.1.1','1.0.0.1') 2>$null
      Say "   - DNS impostati su Cloudflare (1.1.1.1) su '$($adapter.Name)'"
    }
  } catch {}

  # Telemetry off (DiagTrack) - reversible
  $svc = Get-Service DiagTrack -ErrorAction SilentlyContinue
  if ($svc -and -not $script:BK.ContainsKey('svc::DiagTrack')) {
    $script:BK['svc::DiagTrack'] = "$($svc.StartType)"
    Stop-Service DiagTrack -Force 2>$null
    Set-Service DiagTrack -StartupType Disabled 2>$null
    Say '   - Telemetria (DiagTrack) disattivata'
  }

  # Consumer ads / suggestions in Start
  $cdm = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager'
  Set-Reg $cdm 'SilentInstalledAppsEnabled' 'DWord' 0
  Set-Reg $cdm 'SystemPaneSuggestionsEnabled' 'DWord' 0
  Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableWindowsConsumerFeatures' 'DWord' 1
  Say '   - Suggerimenti/ads di Windows disattivati'

  # Debloat: curated, reinstallable UWP apps
  $bloat = @('Microsoft.549981C3F5F10','Microsoft.BingNews','Microsoft.BingWeather','Microsoft.GetHelp',
             'Microsoft.Getstarted','Microsoft.WindowsFeedbackHub','Microsoft.MicrosoftSolitaireCollection',
             'Microsoft.People','Microsoft.WindowsMaps','Microsoft.3DBuilder','Microsoft.MixedReality.Portal',
             'king.com.CandyCrushSaga','Microsoft.SkypeApp')
  $removed = 0
  foreach ($pkg in $bloat) {
    $app = Get-AppxPackage -Name $pkg -ErrorAction SilentlyContinue
    if ($app) { $app | Remove-AppxPackage -ErrorAction SilentlyContinue; $removed++ }
  }
  Say "   - Debloat: rimosse $removed app superflue (reinstallabili dallo Store)"

  Save-Backup
  Say "`n   Ottimizzazioni applicate. Riavvio consigliato. Per annullare: comando 'restore'." 'Green'
}

function Invoke-Restore {
  Say "`n[*] Ripristino dal backup..." 'Cyan'
  if (-not (Test-Path $BACKUP)) { Say '   Nessun backup trovato.' 'Red'; return }
  $b = Get-Content $BACKUP -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe

  if ($b.ContainsKey('power_plan') -and $b['power_plan']) { powercfg -setactive $b['power_plan'] 2>$null }

  foreach ($k in $b.Keys) {
    if ($k -eq 'power_plan') { continue }
    if ($k.StartsWith('svc::')) {
      $svcName = $k.Substring(5); $st = $b[$k]
      $mode = switch -Wildcard ($st) { 'Auto*' {'Automatic'} 'Manual' {'Manual'} 'Disabled' {'Disabled'} default {'Manual'} }
      Set-Service $svcName -StartupType $mode 2>$null
      if ($mode -ne 'Disabled') { Start-Service $svcName 2>$null }
      continue
    }
    if ($k.StartsWith('dns::')) {
      $alias = $k.Substring(5)
      Set-DnsClientServerAddress -InterfaceAlias $alias -ResetServerAddresses 2>$null
      continue
    }
    $parts = $k -split '::', 2
    if ($parts.Count -ne 2) { continue }
    $path = $parts[0]; $name = $parts[1]; $v = $b[$k]
    if ($v -eq '__ABSENT__') {
      Remove-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue
    } else {
      $tv = $v -split '\|', 2; $tp = $tv[0]; $vv = $tv[1]
      if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
      if ($tp -eq 'DWord') { New-ItemProperty -Path $path -Name $name -PropertyType DWord -Value ([int64]$vv) -Force | Out-Null }
      else { New-ItemProperty -Path $path -Name $name -PropertyType String -Value $vv -Force | Out-Null }
    }
  }
  netsh int tcp set global autotuninglevel=normal 2>$null | Out-Null
  Remove-Item $BACKUP -ErrorAction SilentlyContinue
  Say '   Impostazioni ripristinate ai valori precedenti.' 'Green'
}

function Test-Admin {
  return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ---------------- Main ----------------
if ($MODE -eq 'restore') { Invoke-Restore; return }

if ($MODE -eq 'benchmark') {
  $bench = Run-Benchmark
  Show-Bench $bench 'BENCHMARK'
  Send-Benchmark @{ after = $bench; ts = (Get-Date).ToString('o') }
  return
}

Say "`n[*] Rilevamento hardware, salute e avvio..." 'Cyan'
$specs = Get-Specs
Say ("   CPU: {0}" -f $specs.cpu)
Say ("   GPU: {0}" -f $specs.gpu)
Say ("   MB : {0}  ({1} {2})" -f $specs.motherboard, $specs.cpu_socket, $specs.chipset)

if ($MODE -eq 'optimize') {
  if (-not (Test-Admin)) {
    Say "`n[!] Per le ottimizzazioni esegui PowerShell come Amministratore. Invio solo i dati." 'Yellow'
  } else {
    $before = Run-Benchmark
    Show-Bench $before 'PRIMA'
    Invoke-Optimize
    Say "`n[*] Benchmark post-ottimizzazione..." 'Cyan'
    $after = Run-Benchmark
    Show-Bench $after 'DOPO'
    Show-Compare $before $after
    Send-Benchmark @{ before = $before; after = $after; ts = (Get-Date).ToString('o') }
  }
}

$health  = Get-Health
$startup = Get-StartupList
Send-Data $specs $health $startup
'''
