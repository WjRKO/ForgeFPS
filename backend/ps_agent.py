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

PS_SCRIPT = r'''Param([string]$Token = '', [string]$Mode = 'sync')
$ErrorActionPreference = 'SilentlyContinue'
$BACKEND = '__BACKEND_URL__'
$TOKEN   = $Token
$MODE    = $Mode
$BACKUP  = Join-Path $env:TEMP 'boostpc_backup.json'
$script:PROFILE = @(__PROFILE_IDS__)

if ([string]::IsNullOrWhiteSpace($TOKEN)) {
  Write-Host ''
  Write-Host '[FrameForge] Token mancante / Missing token.' -ForegroundColor Red
  Write-Host 'Esegui / Run:  powershell -ExecutionPolicy Bypass -File .\forgefps.ps1 -Token IL_TUO_TOKEN -Mode optimize' -ForegroundColor Yellow
  Write-Host 'Il token si trova nella pagina "Collega il PC" del tuo account. / Find the token on the Connect PC page.' -ForegroundColor Yellow
  return
}

function Say($m, $c='Gray') { Write-Host $m -ForegroundColor $c }
function ConvertTo-HashtableSafe { $h=@{}; foreach($p in $input.PSObject.Properties){ $h[$p.Name]=$p.Value }; return $h }

Say '======================================' 'Yellow'
Say '   FrameForge - Agent PowerShell' 'Yellow'
Say '======================================' 'Yellow'

function Test-Admin {
  return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ---------------- Backup helpers ----------------
$script:BK = @{}
if (Test-Path $BACKUP) { try { $script:BK = Get-Content $BACKUP -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe } catch { $script:BK = @{} } }

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
  if (Test-ForbiddenReg $path) { Write-Host "[SICUREZZA] Modifica bloccata (area protetta): $path" -ForegroundColor Yellow; return }
  Backup-Reg $path $name $type
  if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
  New-ItemProperty -Path $path -Name $name -PropertyType $type -Value $value -Force | Out-Null
}
function Disable-ServiceSafe($name) {
  if (Test-ForbiddenSvc $name) { Write-Host "[SICUREZZA] Servizio protetto, non modificato: $name" -ForegroundColor Yellow; return $false }
  $svc = Get-Service $name -ErrorAction SilentlyContinue
  if ($svc -and $svc.Status -eq 'Running' -and -not $script:BK.ContainsKey("svc::$name")) {
    $script:BK["svc::$name"] = "$($svc.StartType)"
    Stop-Service $name -Force 2>$null
    Set-Service $name -StartupType Disabled 2>$null
  }
  return $true
}
function Save-Backup { $script:BK | ConvertTo-Json -Depth 6 | Set-Content $BACKUP }

function Get-RegVal($path, $name) { return (Get-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue).$name }
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
      Say '   [Sensori] Scarico LibreHardwareMonitor (una volta sola)...' 'DarkGray'
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
  } catch { Say ('   [Sensori] Errore LibreHardwareMonitor: ' + $_.Exception.Message) 'DarkYellow'; return $null }
}

function Get-LhmTemps {
  # Real CPU/GPU temperatures from hardware sensors (incl. motherboard SuperIO). Requires admin.
  $r = @{}
  $c = Get-LhmComputer
  if (-not $c) { return $r }
  try {
    $cpuTemps = @{}; $gpuTemps = @{}; $mbTemps = @{}
    $found = New-Object 'System.Collections.Generic.List[string]'
    $all = New-Object 'System.Collections.Generic.List[object]'
    foreach ($hw in $c.Hardware) { [void]$all.Add($hw); foreach ($sh in $hw.SubHardware) { [void]$all.Add($sh) } }
    foreach ($hw in $all) {
      $hw.Update()
      $ht = "$($hw.HardwareType)"
      foreach ($sensor in $hw.Sensors) {
        if ("$($sensor.SensorType)" -ne 'Temperature' -or $null -eq $sensor.Value) { continue }
        $tv = [double]$sensor.Value
        $found.Add(("{0}/{1}={2}" -f $ht, $sensor.Name, [int][math]::Round($tv)))
        if ($tv -le 0 -or $tv -gt 150) { continue }
        if ($ht -eq 'Cpu') { $cpuTemps["$($sensor.Name)"] = $tv }
        elseif ($ht -like 'Gpu*') { $gpuTemps["$($sensor.Name)"] = $tv }
        else { $mbTemps["$($sensor.Name)"] = $tv }
      }
    }
    $script:LHM_LAST = ($found -join ', ')
    $cpuVal = $null
    foreach ($k in @('CPU Package', 'Core (Tctl/Tdie)', 'Core (Tctl)', 'Core (Tdie)', 'Core Average', 'Core Max')) {
      if ($cpuTemps.ContainsKey($k)) { $cpuVal = $cpuTemps[$k]; break }
    }
    if ($null -eq $cpuVal -and $cpuTemps.Count -gt 0) { $cpuVal = ($cpuTemps.Values | Measure-Object -Maximum).Maximum }
    if ($null -eq $cpuVal) {
      # Motherboard SuperIO fallback: a sensor explicitly named like CPU.
      foreach ($k in $mbTemps.Keys) { if ($k -match 'CPU') { $cpuVal = $mbTemps[$k]; break } }
    }
    if ($null -ne $cpuVal -and $cpuVal -gt 0) { $r.cpu_temp = [int][math]::Round($cpuVal) }
    $gpuVal = $null
    foreach ($k in @('GPU Core', 'GPU Hot Spot', 'GPU')) { if ($gpuTemps.ContainsKey($k)) { $gpuVal = $gpuTemps[$k]; break } }
    if ($null -eq $gpuVal -and $gpuTemps.Count -gt 0) { $gpuVal = ($gpuTemps.Values | Measure-Object -Maximum).Maximum }
    if ($null -ne $gpuVal -and $gpuVal -gt 0) { $r.gpu_temp = [int][math]::Round($gpuVal) }
  } catch {}
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
    $sh = New-Object -ComObject Shell.Application
    $rb = $sh.NameSpace(0xA)
    if ($rb) { foreach ($it in $rb.Items()) { try { $total += [double]$it.Size } catch {} } }
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
    $vram = Get-GpuVramGb
    if ($vram) { $s.gpu_vram_gb = "$vram" }
    elseif ($g.AdapterRAM -gt 0) { $s.gpu_vram_gb = "$([math]::Round($g.AdapterRAM/1GB))" }
  }
  $s.refresh_hz = "$((Get-CimInstance Win32_VideoController | Where-Object {$_.CurrentRefreshRate -gt 0} | Sort-Object CurrentRefreshRate -Descending | Select-Object -First 1).CurrentRefreshRate)"
  $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)
  $s.ram = "$ram GB"
  $pm = Get-CimInstance Win32_PhysicalMemory
  $pm1 = $pm | Select-Object -First 1
  $s.ram_speed_mhz = "$(if ($pm1.ConfiguredClockSpeed -and $pm1.ConfiguredClockSpeed -gt 0) { $pm1.ConfiguredClockSpeed } else { $pm1.Speed })"
  $s.ram_modules = "$(($pm | Measure-Object).Count)"
  $s.ram_type = @{ '20'='DDR'; '21'='DDR2'; '24'='DDR3'; '26'='DDR4'; '34'='DDR5' }["$($pm1.SMBIOSMemoryType)"]
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
  if ($lhm.ContainsKey('cpu_temp')) {
    $h.cpu_temp = $lhm.cpu_temp
  } else {
    $tzt = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object -First 1
    if ($tzt -and $tzt.CurrentTemperature -gt 2732) {
      $ct = [math]::Round(($tzt.CurrentTemperature - 2732)/10)
      if ($ct -gt 0) { $h.cpu_temp = $ct }
    }
  }
  return $h
}

function Get-StartupList { return @(Get-CimInstance Win32_StartupCommand | Select-Object -ExpandProperty Name | Select-Object -First 40) }

# ---------------- Benchmark ----------------
function Run-Benchmark {
  $r = @{}
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $acc = 0.0
  for ($i = 0; $i -lt 3000000; $i++) { $acc += [math]::Sqrt($i) }
  $sw.Stop()
  $r.cpu_score = [int]([math]::Round(3000000 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001) / 1000))
  $size = 64MB
  $buf = New-Object byte[] $size; $dst = New-Object byte[] $size
  $sw.Restart(); for ($i = 0; $i -lt 5; $i++) { [Array]::Copy($buf, $dst, $size) }; $sw.Stop()
  $r.ram_mbps = [int]([math]::Round((5 * $size / 1MB) / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
  # Disco: scrittura sequenziale REALE (WriteThrough bypassa la cache, 256MB)
  $tmp = Join-Path $env:TEMP 'boostpc_bench.bin'
  try {
    $chunk = New-Object byte[] (8MB); (New-Object Random).NextBytes($chunk)
    $fs = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 1MB, [System.IO.FileOptions]::WriteThrough)
    $sw.Restart(); for ($i = 0; $i -lt 32; $i++) { $fs.Write($chunk, 0, $chunk.Length) }; $fs.Flush($true); $sw.Stop(); $fs.Close()
    $r.disk_write_mbps = [int]([math]::Round(256 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
    $sw.Restart(); $null = [System.IO.File]::ReadAllBytes($tmp); $sw.Stop()
    $r.disk_read_mbps = [int]([math]::Round(256 / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
    $b4 = New-Object byte[] 4096; $rnd = New-Object Random
    $fs2 = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4096, [System.IO.FileOptions]::WriteThrough)
    $ops = 200
    $sw.Restart()
    for ($i = 0; $i -lt $ops; $i++) { $fs2.Position = 4096 * $rnd.Next(0, 65536); $fs2.Write($b4, 0, 4096) }
    $fs2.Flush($true); $sw.Stop(); $fs2.Close()
    $r.iops_4k = [int]([math]::Round($ops / [math]::Max($sw.Elapsed.TotalSeconds, 0.001)))
  } catch { if (-not $r.ContainsKey('disk_write_mbps')) { $r.disk_write_mbps = 0 }; if (-not $r.ContainsKey('disk_read_mbps')) { $r.disk_read_mbps = 0 }; $r.iops_4k = 0 }
  Remove-Item $tmp -ErrorAction SilentlyContinue
  # Latenza scheduler/DPC (proxy): oversleep p95 su 150 sleep da 1ms
  $lat = New-Object System.Collections.Generic.List[double]
  $sw2 = [System.Diagnostics.Stopwatch]::StartNew()
  $prev = $sw2.Elapsed.TotalMilliseconds
  for ($i = 0; $i -lt 150; $i++) {
    Start-Sleep -Milliseconds 1
    $nowMs = $sw2.Elapsed.TotalMilliseconds
    $lat.Add([math]::Max(0, $nowMs - $prev - 1)); $prev = $nowMs
  }
  $sorted = @($lat | Sort-Object)
  $r.dpc_ms = [math]::Round($sorted[[int][math]::Floor($sorted.Count * 0.95)], 1)
  # Rete: ping medio + jitter su 10 campioni
  try {
    $png = New-Object System.Net.NetworkInformation.Ping
    $rtts = New-Object System.Collections.Generic.List[double]
    for ($i = 0; $i -lt 10; $i++) { $res = $png.Send('1.1.1.1', 2000); if ($res.Status -eq 'Success') { $rtts.Add([double]$res.RoundtripTime) } }
    if ($rtts.Count -gt 0) {
      $avg = ($rtts | Measure-Object -Average).Average
      $r.ping_ms = [int]([math]::Round($avg))
      $var = 0.0; foreach ($v in $rtts) { $var += [math]::Pow($v - $avg, 2) }
      $r.jitter_ms = [math]::Round([math]::Sqrt($var / $rtts.Count), 1)
    } else { $r.ping_ms = 0; $r.jitter_ms = 0 }
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
  $dpcN = [math]::Max(0, 100 - $r.dpc_ms * 20)
  $pingN = [math]::Max(0, 100 - $r.ping_ms)
  $jitN = [math]::Max(0, 100 - $r.jitter_ms * 10)
  $r.score = [int]([math]::Round($cpuN * 0.20 + $ramN * 0.10 + $dwN * 0.15 + $drN * 0.10 + $ioN * 0.10 + $dpcN * 0.15 + $pingN * 0.15 + $jitN * 0.05))
  $r.overall = [int]([math]::Round($r.cpu_score + $r.ram_mbps/50.0 + $r.disk_write_mbps/50.0 + $r.disk_read_mbps/50.0 + [math]::Max(0, 120 - $r.ping_ms) + $r.free_ram_pct))
  return $r
}
function Show-Bench($r, $title) {
  Say "`n   [$title]" 'Cyan'
  Say ("   CPU {0} | RAM {1} MB/s | Disco W/R {2}/{3} MB/s | 4K {4} IOPS" -f $r.cpu_score, $r.ram_mbps, $r.disk_write_mbps, $r.disk_read_mbps, $r.iops_4k) 'Yellow'
  Say ("   DPC {0} ms | Ping {1} ms (jitter {2} ms){3} | SCORE {4}/100" -f $r.dpc_ms, $r.ping_ms, $r.jitter_ms, $(if($r.ContainsKey('boot_s')){" | Avvio $($r.boot_s)s"}else{''}), $r.score) 'Yellow'
}

# ---------------- Reporting ----------------
function Send-Data($specs, $health, $startup) {
  $body = @{ data = $specs; health = $health; startup = $startup } | ConvertTo-Json -Depth 6 -Compress
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
}
function Send-Benchmark($rec) {
  $body = @{ benchmark = $rec } | ConvertTo-Json -Depth 6 -Compress
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
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
  $body = '{"games":[' + $items + ']}'
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
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
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
}

# ---------------- Live telemetry ----------------
function Get-TelemetrySample {
  $s = @{ ts = (Get-Date).ToString('o') }
  $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
  $s.cpu_util = [int]$cpu.LoadPercentage
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
  elseif ($lhm.ContainsKey('gpu_temp')) { $s.gpu_temp = $lhm.gpu_temp }
  return $s
}
function Send-Telemetry($sample) {
  $body = @{ sample = $sample } | ConvertTo-Json -Depth 5 -Compress
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/telemetry" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
}
function Push-LiveSample {
  # Lightweight sample sent to cloud when Live Sync toggle is ON.
  # Reuses Get-TelemetrySample which already handles CPU/GPU/RAM/temps via WMI+LHM.
  try {
    $sample = Get-TelemetrySample
    if ($sample) { Send-Telemetry $sample }
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
function Start-Fps {
  if (-not (Test-Admin)) { Say '   [FPS] Richiede Amministratore: avvia PowerShell come Admin per gli FPS.' 'DarkYellow'; return }
  if (-not (Test-Path $script:PM_EXE)) {
    Say '   [FPS] Scarico PresentMon (una volta sola)...' 'DarkGray'
    try {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest $script:PM_URL -OutFile $script:PM_EXE -UseBasicParsing
    } catch { Say ('   [FPS] Download PresentMon fallito: ' + $_.Exception.Message) 'DarkYellow'; return }
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
      Say ('   [FPS] PresentMon si e chiuso subito (exit ' + $script:PM_PROC.ExitCode + '). Dettaglio: ' + ($err.Trim() -replace "`r?`n", ' | ')) 'DarkYellow'
    } else {
      Say '   [FPS] Cattura FPS attiva. Avvia un gioco (o uno screensaver 3D) a schermo intero.' 'DarkGray'
    }
  } catch { Say ('   [FPS] Avvio PresentMon fallito: ' + $_.Exception.Message) 'DarkYellow' }
}
function Stop-Fps { if ($script:PM_ON) { Stop-Process -Name PresentMon -Force -ErrorAction SilentlyContinue; $script:PM_ON = $false } }
function Show-FpsDiag {
  if ($script:PM_DIAG_DONE) { return }
  $script:PM_DIAG_DONE = $true
  Say '   [diag FPS] Nessun FPS ancora rilevato. Controllo stato:' 'DarkYellow'
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
  Say '   [diag FPS] Se serve, incolla queste righe in chat. Ricorda: gli FPS compaiono SOLO mentre un app renderizza a schermo (uno screensaver si chiude al primo movimento del mouse).' 'DarkYellow'
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
    if (-not $byApp.ContainsKey($app)) { $byApp[$app] = @{ sum = 0.0; n = 0; lsum = 0.0; ln = 0 } }
    $byApp[$app].sum += $ms; $byApp[$app].n++
    if ($iLat -ge 0 -and $c.Count -gt $iLat) {
      try { $lat = [double]::Parse($c[$iLat], $inv); if ($lat -gt 0 -and $lat -lt 1000) { $byApp[$app].lsum += $lat; $byApp[$app].ln++ } } catch {}
    }
  }
  if ($byApp.Count -eq 0) { return $null }
  $top = $byApp.GetEnumerator() | Sort-Object { $_.Value.n } -Descending | Select-Object -First 1
  $avg = $top.Value.sum / $top.Value.n
  if ($avg -le 0) { return $null }
  $lat = if ($top.Value.ln -gt 0) { [int]([math]::Round($top.Value.lsum / $top.Value.ln)) } else { $null }
  return @{ fps = [int]([math]::Round(1000 / $avg)); game = ($top.Key -replace '\.exe$', ''); latency_ms = $lat }
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
     state={ $p=(powercfg /getactivescheme); if($p -match 'high|ultimate|prestazioni elevate'){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Power } }
  @{ cat='gaming'; id='gaming'; name='Boost gaming (Game Mode, HAGS, Game DVR off)';
     problem='Game DVR registra in background e la GPU scheduling hardware potrebbe essere disattivata.';
     reason='Il Game DVR ruba CPU/GPU durante il gioco; HAGS riduce la latenza di pianificazione dei frame.';
     desc='Attiva Game Mode + Hardware GPU Scheduling, disattiva Game DVR/registrazione in background.';
     impact='+2-5% FPS e frametime piu costante, meno overhead durante il gioco.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\GameBar' 'AllowAutoGameMode') -eq 1){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Gaming } }
  @{ cat='gaming'; id='priority'; name='Priorita GPU/CPU ai giochi (MMCSS)';
     problem='Windows assegna le stesse risorse ai processi in background e al gioco in primo piano.';
     reason='MMCSS/SystemResponsiveness a 0 da priorita reale ai task multimediali e ai giochi attivi.';
     desc='Imposta SystemResponsiveness=0 e priorita GPU/CPU ai giochi in primo piano.';
     impact='Frametime piu regolare, meno spike quando ci sono app in background.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile' 'SystemResponsiveness') -eq 0){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Priority } }
  @{ cat='gaming'; id='mpo'; name='Disabilita MPO (Multi-Plane Overlay)';
     problem='Il Multi-Plane Overlay causa flickering, stutter e SCHERMO NERO in OBS Game Capture.';
     reason='MPO ha bug noti con molti driver: interferisce con la cattura schermo e il DWM.';
     desc='Imposta OverlayTestMode=5 per disattivare MPO nel Desktop Window Manager.';
     impact='Elimina flickering/schermo nero in OBS, meno stutter sul desktop. Richiede riavvio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows\Dwm' 'OverlayTestMode') -eq 5){'Disabilitato'}else{'Attivo (da disabilitare)'} }; apply={ Do-Mpo } }
  @{ cat='gaming'; id='gpu_msi'; name='GPU: MSI mode ON (latenza DPC)';
     problem='La GPU usa interrupt line-based, che aumentano la latenza DPC e causano micro-stutter.';
     reason='I Message Signaled Interrupts (MSI) riducono la latenza di interrupt della GPU.';
     desc='Attiva MSISupported=1 nel ramo Interrupt Management della GPU (NVIDIA/AMD).';
     impact='Latenza DPC piu bassa, input piu reattivo. Richiede riavvio.';
     risk='safe';
     state={ $pnp=Get-GpuPnp; if($pnp){ $v=Get-RegVal "HKLM:\SYSTEM\CurrentControlSet\Enum\$pnp\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties" 'MSISupported'; if($v -eq 1){'Attivo'}else{'Da attivare'} }else{'n/d'} }; apply={ Do-GpuMsi } }
  @{ cat='gaming'; id='amd_ulps'; name='AMD: disabilita ULPS';
     problem='Le Radeon abbassano troppo il clock in idle (Ultra Low Power State), causando stutter.';
     reason='ULPS mette la GPU in stato a bassissimo consumo, con risvegli lenti che generano scatti.';
     desc='Disattiva ULPS nelle chiavi di registro AMD (solo GPU AMD).';
     impact='Meno stutter e latenza su schede AMD, clock piu stabile.';
     risk='safe';
     fit={ if($script:HW.gpu -eq 'AMD'){'ok'}else{"skip:Solo GPU AMD (rilevata $($script:HW.gpu))"} };
     state={ if((Get-GpuVendor) -eq 'AMD'){'GPU AMD: applicabile'}else{'Solo GPU AMD'} }; apply={ Do-AmdUlps } }
  @{ cat='gaming'; id='nvidia_tel'; name='NVIDIA: disabilita telemetria';
     problem='I driver NVIDIA installano task/servizi di telemetria che girano in background.';
     reason='La telemetria consuma CPU e rete senza alcun beneficio per il gaming.';
     desc='Disattiva i task pianificati e il servizio di telemetria NVIDIA (solo GPU NVIDIA).';
     impact='Meno processi in background, CPU leggermente piu libera.';
     risk='safe';
     fit={ if($script:HW.gpu -eq 'NVIDIA'){'ok'}else{"skip:Solo GPU NVIDIA (rilevata $($script:HW.gpu))"} };
     state={ if((Get-GpuVendor) -eq 'NVIDIA'){'GPU NVIDIA: applicabile'}else{'Solo GPU NVIDIA'} }; apply={ Do-NvidiaTel } }
  @{ cat='gaming'; id='hibernate'; name='Disabilita ibernazione';
     problem='Il file hiberfil.sys occupa diversi GB di disco anche se non usi mai la sospensione.';
     reason='Su desktop l ibernazione e raramente usata; il file pesa quanto la RAM installata.';
     desc='Esegue powercfg -h off per rimuovere hiberfil.sys (reversibile con -h on).';
     impact='Libera 4-32 GB su disco. Perdi la sospensione ibrida/avvio rapido.';
     risk='caution';
     fit={ if($script:HW.laptop){'warn:Su laptop l ibernazione e utile a batteria scarica: disattivala solo se non la usi mai'}else{'ok'} };
     state={ 'Applica per liberare spazio' }; apply={ Do-Hibernate } }
  # LATENZA & INPUT
  @{ cat='input'; id='mouse'; name='Accelerazione mouse OFF (raw input)';
     problem='L Enhance Pointer Precision di Windows accelera il mouse in modo imprevedibile.';
     reason='L accelerazione rende la mira incoerente: lo stesso movimento fisico da spostamenti diversi.';
     desc='Disattiva MouseSpeed/Threshold per un input 1:1 (raw).';
     impact='Mira piu precisa e costante negli sparatutto. Nessun rischio.';
     risk='safe';
     state={ if("$(Get-RegVal 'HKCU:\Control Panel\Mouse' 'MouseSpeed')" -eq '0'){'Gia disattivata'}else{'Attiva (da disattivare)'} }; apply={ Do-Mouse } }
  @{ cat='input'; id='timer'; name='Timer resolution globale';
     problem='Su Windows 11 la timer resolution puo essere variabile, con scheduling meno preciso.';
     reason='Una timer resolution alta e costante rende piu regolari i frametime e la latenza.';
     desc='Attiva GlobalTimerResolutionRequests=1 (richiesta timer globale).';
     impact='Frametime piu costante, meno stutter. Richiede riavvio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\kernel' 'GlobalTimerResolutionRequests') -eq 1){'Attivo'}else{'Da attivare'} }; apply={ Do-Timer } }
  @{ cat='input'; id='usb'; name='USB power management OFF';
     problem='Windows sospende le porte USB per risparmiare energia, causando cali di polling.';
     reason='Se il mouse/tastiera vanno in standby, si hanno input drop e micro-freeze.';
     desc='Disattiva il risparmio energetico sui controller USB.';
     impact='Input di mouse/tastiera piu stabile, niente drop. Nessun rischio.';
     risk='safe';
     fit={ if($script:HW.laptop){'warn:Su laptop aumenta il consumo della batteria: attiva solo se giochi collegato alla corrente'}else{'ok'} };
     state={ 'Applica per input stabile' }; apply={ Do-Usb } }
  @{ cat='input'; id='stickykeys'; name='Sticky/Filter/Toggle Keys OFF';
     problem='Premendo Shift ripetutamente compare il popup delle Sticky Keys che ti butta fuori dal gioco.';
     reason='Le funzioni di accessibilita tastiera si attivano per errore durante il gioco.';
     desc='Disattiva Sticky/Filter/Toggle Keys.';
     impact='Niente piu popup che rubano il focus in game. Nessun rischio.';
     risk='safe';
     state={ if("$(Get-RegVal 'HKCU:\Control Panel\Accessibility\StickyKeys' 'Flags')" -eq '506'){'Disattivati'}else{'Attivi (da disattivare)'} }; apply={ Do-StickyKeys } }
  @{ cat='input'; id='startupdelay'; name='Startup delay app ridotto';
     problem='Windows ritarda artificialmente l avvio delle app in autostart.';
     reason='Il delay serve a non sovraccaricare l avvio, ma rallenta l accesso al desktop utile.';
     desc='Imposta StartupDelayInMSec=0 per avviare subito le app.';
     impact='Desktop e app pronti prima dopo l accensione. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize' 'StartupDelayInMSec') -eq 0){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-StartupDelay } }
  # RETE & STREAMING
  @{ cat='network'; id='network'; name='Rete: Nagle OFF + TCP tuning';
     problem='L algoritmo di Nagle accumula piccoli pacchetti, aggiungendo latenza nei giochi online.';
     reason='I giochi inviano tanti pacchetti piccoli: Nagle li ritarda, aumentando il ping percepito.';
     desc='Disattiva Nagle sulla scheda attiva e regola autotuning/ECN/RSS.';
     impact='Ping piu basso e stabile online. Reversibile con Ripristina.';
     risk='safe';
     state={ 'Applica per meno lag online' }; apply={ Do-Network } }
  @{ cat='network'; id='dns'; name='DNS veloci (Cloudflare 1.1.1.1)';
     problem='I DNS del provider sono spesso lenti e possono rallentare la risoluzione dei domini.';
     reason='DNS piu veloci riducono i tempi di connessione a server di gioco e matchmaking.';
     desc='Imposta 1.1.1.1 / 1.0.0.1 sulla scheda attiva (reversibile a DHCP).';
     impact='Connessioni piu rapide. Reversibile in un click.';
     risk='safe';
     state={ $a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; if($a){ $d=(Get-DnsClientServerAddress -InterfaceAlias $a.Name -AddressFamily IPv4).ServerAddresses -join ','; if($d -match '1.1.1.1'){'Gia Cloudflare'}else{"Attuale: $d"} }else{'n/d'} }; apply={ Do-Dns } }
  @{ cat='network'; id='qos'; name='Rimuovi 20% banda riservata QoS';
     problem='Windows riserva fino al 20% della banda per il QoS di sistema.';
     reason='Recuperando quella banda hai piu throughput reale per download e streaming.';
     desc='Imposta NonBestEffortLimit=0.';
     impact='Piu banda disponibile per gioco/stream. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched' 'NonBestEffortLimit') -eq 0){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Qos } }
  @{ cat='network'; id='deliveryopt'; name='Delivery Optimization P2P OFF';
     problem='Windows usa la tua banda in upload per distribuire aggiornamenti ad altri PC (P2P).';
     reason='Durante lo streaming quell upload occupa banda e destabilizza il bitrate.';
     desc='Imposta DODownloadMode=0 (nessun P2P).';
     impact='Upload piu libero, stream piu stabile. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config' 'DODownloadMode') -eq 0){'Disattivato'}else{'Attivo (da disattivare)'} }; apply={ Do-DeliveryOpt } }
  @{ cat='network'; id='obs_priority'; name='OBS ad alta priorita';
     problem='OBS gira a priorita normale e puo perdere frame in encoding sotto carico.';
     reason='Alzando la priorita CPU di OBS l encoding resta fluido anche con la CPU occupata dal gioco.';
     desc='Imposta CpuPriorityClass alta per obs64/obs32.exe (via Image File Execution Options).';
     impact='Meno frame persi in registrazione/stream. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\obs64.exe\PerfOptions' 'CpuPriorityClass') -eq 3){'Attivo'}else{'Da attivare'} }; apply={ Do-ObsPriority } }
  # SISTEMA & DEBLOAT
  @{ cat='system'; id='clean'; name='Pulizia temp + cache Windows Update';
     problem='File temporanei e cache degli aggiornamenti si accumulano e occupano spazio.';
     reason='Ripulire libera disco e puo velocizzare alcune operazioni di sistema.';
     desc='Rimuove temp utente/sistema, cache Windows Update e svuota il DNS.';
     impact='Libera spazio su disco. Nessun file personale toccato.';
     risk='safe';
     state={ $mb=0; Get-ChildItem $env:TEMP -Recurse -File -Force 2>$null | ForEach-Object { $mb+=$_.Length }; "$([math]::Round($mb/1MB)) MB da pulire" }; apply={ Do-Cleanup } }
  @{ cat='system'; id='visual'; name='Effetti visivi: modalita prestazioni';
     problem='Animazioni e trasparenze consumano GPU/CPU e rendono la UI meno reattiva.';
     reason='In modalita prestazioni Windows disattiva gli effetti superflui.';
     desc='Imposta VisualFXSetting=2 (prestazioni).';
     impact='UI piu snella e reattiva. Estetica leggermente piu spartana.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting') -eq 2){'Prestazioni'}else{'Da ottimizzare'} }; apply={ Do-Visual } }
  @{ cat='system'; id='telemetry'; name='Telemetria (DiagTrack) OFF';
     problem='Il servizio DiagTrack invia dati di diagnostica e gira sempre in background.';
     reason='Disattivarlo riduce l uso di CPU e rete senza impatti sulle funzioni essenziali.';
     desc='Ferma e disabilita il servizio DiagTrack (Connected User Experiences).';
     impact='Meno CPU/rete in background. NON tocca Defender ne la sicurezza.';
     risk='caution';
     state={ $s=Get-Service DiagTrack -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){'Attiva (da disattivare)'}else{'Disattivata'} }; apply={ Do-Telemetry } }
  @{ cat='system'; id='ads'; name='Suggerimenti/ads di Windows OFF';
     problem='Windows mostra app suggerite e contenuti promozionali nel menu Start e altrove.';
     reason='Sono distrazioni e consumano risorse per scaricare i contenuti suggeriti.';
     desc='Disattiva SilentInstalledApps, suggerimenti e Consumer Features.';
     impact='Start piu pulito, niente app installate a sorpresa. Nessun rischio.';
     risk='safe';
     state={ 'Applica per rimuovere ads' }; apply={ Do-Ads } }
  @{ cat='system'; id='bgapps'; name='App in background OFF (globale)';
     problem='Le app UWP restano attive in background consumando CPU/RAM e rete.';
     reason='Bloccarle libera risorse per il gioco senza disinstallare nulla.';
     desc='Imposta GlobalUserDisabled=1 e LetAppsRunInBackground.';
     impact='Meno consumo di CPU/RAM in background. Alcune notifiche UWP potrebbero ritardare.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled') -eq 1){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-BgApps } }
  @{ cat='system'; id='gamebar_rec'; name='Xbox Game Bar recording OFF';
     problem='La Game Bar registra in background per la funzione clip, usando risorse.';
     reason='Se non usi le clip Xbox, la registrazione continua e uno spreco di CPU/GPU.';
     desc='Disattiva GameDVR_Enabled e AppCaptureEnabled.';
     impact='Meno overhead in game. Perdi la registrazione automatica Xbox.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' 'AppCaptureEnabled') -eq 0){'Disattivato'}else{'Attivo (da disattivare)'} }; apply={ Do-GamebarRec } }
  @{ cat='system'; id='debloat'; name='Debloat app superflue (UWP)';
     problem='Windows preinstalla app come Candy Crush, Solitaire, Bing, 3D Builder che non usi.';
     reason='Occupano spazio e alcune girano in background inutilmente.';
     desc='Rimuove una lista curata di app UWP (reinstallabili dallo Store).';
     impact='Sistema piu pulito. Puoi reinstallarle in qualsiasi momento dallo Store.';
     risk='caution';
     state={ $n=0; foreach($p in $script:BLOAT){ if(Get-AppxPackage -Name $p -ErrorAction SilentlyContinue){$n++} }; "$n app rimovibili" }; apply={ Do-Debloat } }
  @{ cat='system'; id='search_index'; name='Windows Search indexing OFF (invasivo)';
     problem='Il servizio di indicizzazione della ricerca puo generare carico su disco/CPU.';
     reason='Su alcuni PC l indicizzazione rallenta il sistema, ma serve alla ricerca file veloce.';
     desc='Ferma e disabilita il servizio WSearch.';
     impact='Meno carico su disco/CPU, MA la ricerca file diventa piu lenta. Reversibile.';
     risk='caution';
     state={ $s=Get-Service WSearch -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){'Attivo'}else{'Disattivato'} }; apply={ Do-SearchIndex } }
  # NUOVI TWEAK (motore adattivo)
  @{ cat='gaming'; id='fse'; name='Fullscreen Optimizations OFF';
     problem='Windows forza il fullscreen ottimizzato (borderless) invece del fullscreen esclusivo reale.';
     reason='Il fullscreen esclusivo bypassa il compositor DWM: input piu diretto e frametime piu pulito.';
     desc='Imposta FSEBehaviorMode=2 e HonorUserFSEBehavior nel GameConfigStore.';
     impact='Input lag ridotto nei giochi a schermo intero. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKCU:\System\GameConfigStore' 'GameDVR_FSEBehaviorMode') -eq 2){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Fse } }
  @{ cat='gaming'; id='power_throttling'; name='Power throttling CPU OFF';
     problem='Windows rallenta (throttla) i processi che considera poco importanti per risparmiare energia.';
     reason='A volte il throttling colpisce anche giochi, OBS o launcher, causando cali improvvisi.';
     desc='Imposta PowerThrottlingOff=1: nessun processo viene mai rallentato dal risparmio energetico.';
     impact='CPU sempre reattiva per giochi e streaming. Consuma un po piu di energia.';
     risk='safe';
     fit={ if($script:HW.laptop){'warn:Su laptop il power throttling risparmia batteria: attiva solo se giochi sempre collegato alla corrente'}else{'ok'} };
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling' 'PowerThrottlingOff') -eq 1){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-PowerThrottling } }
  @{ cat='gaming'; id='standby_clear'; name='Svuota RAM standby (azione istantanea)';
     problem='Windows tiene in RAM una cache standby che a volte non viene liberata abbastanza in fretta.';
     reason='Svuotare la standby list prima di giocare rende la memoria subito disponibile per il gioco.';
     desc='Purge della standby memory list via API di sistema (richiede Amministratore). Nessuna modifica permanente.';
     impact='RAM libera immediata prima della sessione di gioco. Azione una tantum, sempre sicura.';
     risk='safe';
     state={ $o=Get-CimInstance Win32_OperatingSystem; "$([math]::Round($o.FreePhysicalMemory/1MB,1)) GB RAM libera ora" }; apply={ Clear-StandbyList } }
  @{ cat='network'; id='nic_power'; name='Scheda di rete a piena potenza';
     problem='Windows puo spegnere la scheda di rete per risparmiare energia e usa interrupt moderation che aggiunge latenza.';
     reason='Il risparmio energetico della NIC causa micro-disconnessioni; la moderazione degli interrupt ritarda i pacchetti.';
     desc='Disattiva il power saving della scheda attiva (PnPCapabilities=24) e la interrupt moderation.';
     impact='Ping piu stabile, niente drop di connessione in game. Richiede riavvio o riconnessione.';
     risk='safe';
     fit={ if($script:HW.laptop){'warn:Su laptop la scheda di rete sempre attiva consuma piu batteria'}else{'ok'} };
     state={ $a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; if(-not $a){'n/d'}else{ $ok=$false; Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue | ForEach-Object { $p=Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue; if($p.NetCfgInstanceId -eq $a.InterfaceGuid -and $p.PnPCapabilities -eq 24){$ok=$true} }; if($ok){'Attivo'}else{'Da ottimizzare'} } }; apply={ Do-NicPower } }
  @{ cat='system'; id='paging_exec'; name='Kernel sempre in RAM (16GB+)';
     problem='Windows puo spostare parti del kernel e dei driver nel file di paging su disco.';
     reason='Con abbastanza RAM, tenere il kernel in memoria elimina micro-attese di paging.';
     desc='Imposta DisablePagingExecutive=1 in Memory Management.';
     impact='Sistema piu scattante sotto carico. Consigliato solo con 16 GB o piu.';
     risk='safe';
     fit={ if($script:HW.ram -ge 16){'ok'}else{"skip:Richiede almeno 16 GB di RAM (rilevati $($script:HW.ram) GB)"} };
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management' 'DisablePagingExecutive') -eq 1){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-PagingExec } }
  @{ cat='system'; id='sysmain'; name='SysMain/Superfetch OFF (solo SSD)';
     problem='SysMain precarica app in RAM analizzando l uso del disco: su SSD e superfluo e consuma CPU/disco.';
     reason='Gli SSD sono gia velocissimi in lettura casuale: il preload di SysMain non serve e genera carico.';
     desc='Ferma e disabilita il servizio SysMain (ex Superfetch).';
     impact='Meno attivita disco/CPU in background su SSD. Su HDD invece va lasciato attivo.';
     risk='caution';
     fit={ if($script:HW.ssd){'ok'}else{'skip:Solo con SSD: su HDD SysMain velocizza i caricamenti, meglio lasciarlo attivo'} };
     state={ $s=Get-Service SysMain -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){'Attivo (da disattivare)'}else{'Disattivato'} }; apply={ Do-SysMain } }
  @{ cat='system'; id='trim'; name='Verifica TRIM SSD attivo';
     problem='Se il TRIM e disattivato, l SSD rallenta progressivamente con l uso.';
     reason='Il TRIM permette all SSD di riorganizzare le celle libere mantenendo le prestazioni di scrittura.';
     desc='Esegue fsutil behavior set DisableDeleteNotify 0 (TRIM attivo).';
     impact='SSD sempre alla massima velocita nel tempo. Nessun rischio.';
     risk='safe';
     fit={ if($script:HW.ssd){'ok'}else{'skip:Solo per SSD: il TRIM non si applica agli HDD'} };
     state={ $q=(fsutil behavior query DisableDeleteNotify) -join ' '; if($q -match 'DisableDeleteNotify\s*=\s*0'){'TRIM attivo'}else{'Da attivare'} }; apply={ Do-Trim } }
  @{ cat='system'; id='ntfs'; name='NTFS: last-access timestamp OFF';
     problem='NTFS aggiorna la data di ultimo accesso di ogni file letto, generando scritture inutili.';
     reason='Disattivarlo riduce le scritture su disco a ogni lettura di file (utile anche per la vita dell SSD).';
     desc='Esegue fsutil behavior set disablelastaccess 1 (con backup del valore precedente).';
     impact='Meno I/O su disco nelle operazioni quotidiane. Nessun rischio.';
     risk='safe';
     state={ $q=(fsutil behavior query disablelastaccess) -join ' '; if($q -match '=\s*[13]'){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Ntfs } }
  @{ cat='system'; id='edge_preload'; name='Edge preload/background OFF';
     problem='Microsoft Edge si precarica all avvio e resta in background anche se non lo usi.';
     reason='Lo startup boost di Edge occupa RAM e CPU all accensione per un browser che magari non apri mai.';
     desc='Imposta StartupBoostEnabled=0 e BackgroundModeEnabled=0 via policy.';
     impact='Avvio piu pulito e RAM libera se non usi Edge. Nessun rischio.';
     risk='safe';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Policies\Microsoft\Edge' 'StartupBoostEnabled') -eq 0){'Disattivato'}else{'Attivo (da disattivare)'} }; apply={ Do-EdgePreload } }
)

$script:PRESETS = @{
  'competitivo' = @('power','gaming','priority','mpo','gpu_msi','amd_ulps','nvidia_tel','fse','power_throttling','standby_clear','mouse','timer','usb','stickykeys','network','nic_power','qos','visual','bgapps','paging_exec','ntfs')
  'streaming'   = @('power','gaming','priority','mpo','gpu_msi','amd_ulps','nvidia_tel','fse','network','dns','nic_power','qos','deliveryopt','obs_priority','telemetry','ads','bgapps','gamebar_rec','edge_preload','paging_exec')
}

# ---------------- Restore ----------------
function Invoke-Restore {
  if (-not (Test-Path $BACKUP)) { return 'Nessun backup trovato.' }
  $b = Get-Content $BACKUP -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe
  if ($b.ContainsKey('power_plan') -and $b['power_plan']) { powercfg -setactive $b['power_plan'] 2>$null }
  if ($b.ContainsKey('hib')) { powercfg -h on 2>$null }
  foreach ($k in $b.Keys) {
    if ($k -eq 'power_plan' -or $k -eq 'hib') { continue }
    if ($k.StartsWith('svc::')) {
      $svcName = $k.Substring(5); $st = $b[$k]
      $mode = switch -Wildcard ($st) { 'Auto*' {'Automatic'} 'Manual' {'Manual'} 'Disabled' {'Disabled'} default {'Manual'} }
      Set-Service $svcName -StartupType $mode 2>$null
      if ($mode -ne 'Disabled') { Start-Service $svcName 2>$null }
      continue
    }
    if ($k -eq 'ntfs::lastaccess') { fsutil behavior set disablelastaccess ([int]$b[$k]) 2>$null | Out-Null; continue }
    if ($k.StartsWith('dns::')) { Set-DnsClientServerAddress -InterfaceAlias $k.Substring(5) -ResetServerAddresses 2>$null; continue }
    $parts = $k -split '::', 2
    if ($parts.Count -ne 2) { continue }
    $path = $parts[0]; $name = $parts[1]; $v = $b[$k]
    if ($v -eq '__ABSENT__') { Remove-ItemProperty -Path $path -Name $name -ErrorAction SilentlyContinue }
    else {
      $tv = $v -split '\|', 2; $tp = $tv[0]; $vv = $tv[1]
      if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
      if ($tp -eq 'DWord') { New-ItemProperty -Path $path -Name $name -PropertyType DWord -Value ([int64]$vv) -Force | Out-Null }
      else { New-ItemProperty -Path $path -Name $name -PropertyType String -Value $vv -Force | Out-Null }
    }
  }
  netsh int tcp set global autotuninglevel=normal 2>$null | Out-Null
  Remove-Item $BACKUP -ErrorAction SilentlyContinue
  $script:BK = @{}
  return 'Impostazioni ripristinate ai valori precedenti.'
}

# ---------------- Modern Web GUI (Edge --app + local HTTP server) ----------------
function Show-WebGui {
  # Trova msedge
  $edgePaths = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
  )
  $edgeExe = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $edgeExe) { return $false }

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
  try { $listener.Start() } catch { return $false }

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
  function Get-TweakDto {
    $arr = @()
    foreach ($t in $script:TWEAKS) {
      $fit = $script:FITMAP[$t.id]
      $skip = $fit -like "skip:*"; $warn = $fit -like "warn:*"; $note = $fit -like "note:*"
      $hint = ""; if ($skip -or $warn -or $note) { $hint = ($fit -split ":", 2)[1] }
      $st = & $t.state
      $arr += @{
        id = $t.id; cat = $t.cat; name = $t.name; problem = $t.problem
        reason = $t.reason; desc = $t.desc; impact = $t.impact; risk = $t.risk
        state = $st; fit = @{ ok = (-not $skip); warn = [bool]$warn; note = [bool]$note; skip = [bool]$skip; hint = $hint }
      }
    }
    return $arr
  }

  # HTML della GUI (in singola-quote here-string: nessuna $-expansion PS; JS usa " e backtick)
  $html = @'
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>FrameForge - Ottimizzazioni sicure</title>
<style>
  :root {
    --bg: #0a0a0f;
    --bg2: #12121a;
    --card: #14141c;
    --card-hi: #1a1a24;
    --border: #23232e;
    --accent: #E5FF00;
    --ok: #00FF66;
    --warn: #FFAA00;
    --danger: #FF3355;
    --info: #00E0FF;
    --text: #e6e6ec;
    --muted: #7d7d8a;
    --dim: #4a4a55;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Segoe UI Variable", "Segoe UI", -apple-system, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 0; }
  ::-webkit-scrollbar-thumb:hover { background: #33333e; }

  header {
    padding: 20px 28px 16px;
    background: linear-gradient(180deg, var(--bg2) 0%, var(--bg) 100%);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .brand-row { display: flex; align-items: baseline; gap: 14px; margin-bottom: 6px; }
  .brand {
    font-size: 22px; font-weight: 800; letter-spacing: 2px;
    color: var(--accent);
    text-shadow: 0 0 24px rgba(229,255,0,0.25);
  }
  .brand-sub { font-size: 12px; color: var(--muted); }
  .ver-pill {
    font-size: 10px; padding: 2px 8px; border: 1px solid var(--info);
    color: var(--info); font-family: "Consolas", monospace;
  }
  .safety {
    color: var(--ok); font-size: 12px; margin-top: 4px; letter-spacing: 0.2px;
  }
  .safety strong { color: var(--ok); }
  .meta-row {
    display: grid; grid-template-columns: 1fr auto; align-items: end;
    gap: 12px; margin-top: 12px;
  }
  .hw-line { font-size: 12px; color: var(--info); font-family: "Consolas", monospace; }
  .hw-line b { color: var(--accent); font-weight: 600; }
  .admin-line { font-size: 12px; margin-top: 4px; }
  .admin-line.ok { color: var(--ok); }
  .admin-line.no { color: var(--danger); }
  .backup-badge {
    font-size: 11px; padding: 6px 12px; border: 1px solid var(--info);
    color: var(--info); font-family: "Consolas", monospace;
    cursor: pointer; user-select: none; transition: background 0.15s;
  }
  .backup-badge:hover, .backup-badge:focus-visible { background: rgba(0, 224, 255, 0.08); outline: none; }
  .backup-badge.disabled { opacity: 0.5; cursor: not-allowed; }
  .backup-panel {
    position: absolute; top: calc(100% + 6px); right: 28px;
    min-width: 320px; max-width: 420px; max-height: 400px; overflow-y: auto;
    background: var(--bg); border: 1px solid var(--info);
    padding: 12px 14px; z-index: 100; box-shadow: 0 10px 40px rgba(0,0,0,0.6);
  }
  .backup-panel[hidden] { display: none; }
  .backup-panel-title {
    font-family: "Consolas", monospace; font-size: 10px;
    color: var(--info); text-transform: uppercase; letter-spacing: 0.15em;
    margin-bottom: 10px;
  }
  .backup-list { list-style: none; margin: 0; padding: 0; }
  .backup-list li {
    padding: 6px 0; border-bottom: 1px solid var(--border);
    font-size: 12px; color: var(--fg); display: flex; align-items: center; gap: 8px;
  }
  .backup-list li:last-child { border-bottom: none; }
  .backup-list li::before {
    content: "\2713"; color: var(--ok); font-weight: 700; font-size: 11px;
  }
  .backup-list li.empty {
    color: var(--muted); font-style: italic; justify-content: center; padding: 12px 0;
  }
  .backup-list li.empty::before { content: ""; }
  .backup-panel-hint {
    margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
    font-size: 10px; color: var(--muted); line-height: 1.4;
  }
  header > div:has(> .backup-badge) { position: relative; }

  /* Header actions: live sync toggle + backup badge grouped */
  .header-actions {
    display: flex; align-items: center; gap: 12px; position: relative;
  }
  .live-sync-toggle {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 10px; border: 1px solid var(--border);
    font-size: 11px; font-family: "Consolas", monospace;
    color: var(--muted); cursor: pointer; user-select: none;
    transition: all 0.15s;
  }
  .live-sync-toggle:hover { border-color: var(--ok); color: var(--fg); }
  .live-sync-toggle input { position: absolute; opacity: 0; pointer-events: none; }
  .live-sync-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--muted); transition: all 0.2s;
    box-shadow: 0 0 0 0 rgba(0, 255, 102, 0);
  }
  .live-sync-toggle input:checked ~ .live-sync-dot {
    background: var(--ok);
    box-shadow: 0 0 12px 2px rgba(0, 255, 102, 0.55);
    animation: pulse 1.8s ease-in-out infinite;
  }
  .live-sync-toggle input:checked ~ .live-sync-text { color: var(--ok); }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 8px 1px rgba(0, 255, 102, 0.45); }
    50%      { box-shadow: 0 0 16px 3px rgba(0, 255, 102, 0.75); }
  }

  /* Profili tab: cards per applicare preset dal cloud */
  .profile-card {
    background: var(--card); border: 1px solid var(--border);
    padding: 16px; transition: border-color 0.15s;
  }
  .profile-card:hover { border-color: var(--accent); }
  .profile-card h3 {
    font-size: 15px; margin: 0 0 6px; color: var(--fg);
  }
  .profile-card .profile-meta {
    font-size: 11px; color: var(--muted); font-family: "Consolas", monospace;
    letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 8px;
  }
  .profile-card .profile-tweaks {
    display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px;
  }
  .profile-card .profile-tweaks span {
    background: rgba(255,255,255,0.04); border: 1px solid var(--border);
    padding: 2px 8px; font-size: 10px; color: var(--muted);
  }
  .profile-card .profile-apply {
    background: var(--accent); color: #000; border: none;
    padding: 8px 14px; font-size: 11px; font-weight: 700;
    letter-spacing: 0.15em; cursor: pointer; text-transform: uppercase;
    font-family: "Consolas", monospace;
  }
  .profile-card .profile-apply:hover { background: #fff; }
  .profile-section-title {
    grid-column: 1 / -1; font-family: "Consolas", monospace;
    font-size: 10px; color: var(--accent); letter-spacing: 0.2em;
    text-transform: uppercase; padding: 12px 0 4px;
    border-bottom: 1px solid var(--border);
  }

  .preset-bar {
    padding: 14px 28px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 10px;
    flex-shrink: 0;
  }
  .preset-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-right: 6px; }
  .preset-btn {
    background: var(--card); color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 20px; font-size: 13px; font-weight: 600;
    cursor: pointer; letter-spacing: 0.4px;
    transition: border-color 120ms ease, background 120ms ease, color 120ms ease, transform 120ms ease;
    font-family: inherit;
  }
  .preset-btn:hover { border-color: var(--accent); color: var(--accent); }
  .preset-btn.active { background: var(--accent); color: #000; border-color: var(--accent); }
  .preset-btn:active { transform: scale(0.97); }
  .preset-spacer { flex: 1; }
  .search {
    background: var(--card); color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 14px; width: 220px; font-size: 12px;
    font-family: inherit; outline: none;
    transition: border-color 120ms ease;
  }
  .search:focus { border-color: var(--accent); }

  .tabs {
    display: flex; gap: 4px; padding: 0 28px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }
  .tab {
    background: transparent; border: none; color: var(--muted);
    padding: 12px 20px; font-size: 13px; font-weight: 600;
    cursor: pointer; font-family: inherit; letter-spacing: 0.3px;
    border-bottom: 2px solid transparent;
    transition: color 120ms ease, border-color 120ms ease;
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab .count { color: var(--dim); font-size: 11px; margin-left: 6px; }
  .tab.active .count { color: var(--accent); }

  main {
    flex: 1; overflow-y: auto;
    padding: 20px 28px 12px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 14px;
    align-content: start;
  }
  .card {
    background: var(--card); border: 1px solid var(--border);
    padding: 16px 18px; position: relative;
    transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
    animation: fadeUp 260ms cubic-bezier(.22,1,.36,1) both;
  }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(6px);} to { opacity: 1; transform: none;} }
  .card:hover { border-color: #3a3a48; background: var(--card-hi); }
  .card.selected { border-color: var(--accent); }
  .card.skip { opacity: 0.45; }
  .card::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--accent);
  }
  .card.risk-caution::before { background: var(--warn); }
  .card.skip::before { background: var(--dim); }

  .card-head { display: flex; align-items: flex-start; gap: 10px; }
  .cb {
    appearance: none; width: 18px; height: 18px; margin: 2px 0 0;
    border: 1px solid var(--border); background: var(--bg2);
    cursor: pointer; flex-shrink: 0; position: relative;
    transition: border-color 120ms ease, background 120ms ease;
  }
  .cb:hover { border-color: var(--accent); }
  .cb:checked { background: var(--accent); border-color: var(--accent); }
  .cb:checked::after {
    content: ""; position: absolute;
    left: 5px; top: 1px; width: 4px; height: 10px;
    border: solid #000; border-width: 0 2px 2px 0;
    transform: rotate(45deg);
  }
  .cb:disabled { opacity: 0.4; cursor: not-allowed; }
  .name { flex: 1; font-weight: 700; font-size: 14px; color: var(--text); }
  .risk-pill {
    font-size: 9px; padding: 2px 6px; letter-spacing: 1px;
    font-weight: 700; text-transform: uppercase;
    background: var(--warn); color: #000;
  }
  .ok-pill {
    font-size: 9px; padding: 2px 8px; letter-spacing: 1px;
    font-weight: 700; text-transform: uppercase;
    background: transparent; color: var(--ok);
    border: 1px solid var(--ok);
  }
  .applied-note {
    font-size: 10px; color: var(--dim);
    font-style: italic; letter-spacing: 0.4px;
  }
  .card.applied { opacity: 0.72; }
  .card.applied::before { background: var(--ok); }
  .card.applied:hover { opacity: 1; }
  .state {
    font-size: 11px; margin-top: 6px; padding-left: 28px;
    color: var(--accent); font-family: "Consolas", monospace;
  }
  .state.ok { color: var(--ok); }
  .desc-block {
    margin-top: 12px; padding-left: 28px;
    font-size: 12px; line-height: 1.65;
  }
  .desc-block .row { display: flex; gap: 8px; margin-bottom: 4px; }
  .desc-block .row .k {
    color: var(--warn); font-weight: 700; flex-shrink: 0; min-width: 68px;
  }
  .desc-block .row .k.motivo { color: var(--muted); }
  .desc-block .row .k.mod { color: var(--muted); }
  .desc-block .row .k.impatto { color: var(--ok); }
  .desc-block .row .v { color: var(--text); }
  .desc-block .row .v.impatto { color: var(--ok); }
  .actions { margin-top: 12px; padding-left: 28px; display: flex; gap: 8px; }
  .btn-apply-one {
    background: transparent; color: var(--accent);
    border: 1px solid var(--accent);
    padding: 6px 14px; font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.2px; cursor: pointer; font-family: inherit;
    transition: background 120ms ease, color 120ms ease;
  }
  .btn-apply-one:hover { background: var(--accent); color: #000; }
  .btn-apply-one:disabled { opacity: 0.4; cursor: not-allowed; }
  .hint {
    margin-top: 8px; padding: 8px 12px 8px 28px;
    font-size: 11px; color: var(--muted);
    border-left: 2px solid var(--warn); background: rgba(255,170,0,0.06);
  }
  .hint.skip { border-left-color: var(--dim); color: var(--dim); }

  footer {
    background: var(--bg2); border-top: 1px solid var(--border);
    padding: 12px 28px 14px; flex-shrink: 0;
    display: grid; grid-template-columns: 1fr auto; gap: 16px;
    align-items: end;
  }
  .log {
    background: #000; border: 1px solid var(--border);
    height: 140px; overflow-y: auto;
    font-family: "Consolas", monospace; font-size: 12px;
    padding: 8px 12px; color: var(--ok);
  }
  .log .ts { color: var(--dim); margin-right: 8px; }
  .btn-bar { display: flex; flex-direction: column; gap: 8px; }
  .bench-toggle {
    display: flex; align-items: center; gap: 8px;
    font-size: 12px; color: var(--info); cursor: pointer;
    user-select: none;
  }
  .btn-primary {
    background: var(--accent); color: #000; border: none;
    padding: 14px 32px; font-size: 13px; font-weight: 800; letter-spacing: 1.4px;
    text-transform: uppercase; cursor: pointer; font-family: inherit;
    transition: filter 120ms ease, transform 120ms ease;
  }
  .btn-primary:hover { filter: brightness(1.1); }
  .btn-primary:active { transform: scale(0.98); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-danger {
    background: transparent; color: var(--danger); border: 1px solid var(--danger);
    padding: 10px 20px; font-size: 12px; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; cursor: pointer; font-family: inherit;
    transition: background 120ms ease, color 120ms ease;
  }
  .btn-danger:hover { background: var(--danger); color: #000; }

  .selection-count {
    font-size: 11px; color: var(--muted); text-align: right;
    letter-spacing: 0.5px;
  }
  .selection-count b { color: var(--accent); }

  .toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: var(--card); border: 1px solid var(--ok); color: var(--ok);
    padding: 10px 22px; font-size: 13px; font-weight: 600;
    opacity: 0; transition: opacity 220ms ease;
    z-index: 100;
  }
  .toast.show { opacity: 1; }

  .empty {
    grid-column: 1 / -1;
    text-align: center; color: var(--muted); padding: 60px 20px;
    font-size: 14px;
  }
</style>
</head>
<body>
  <header>
    <div class="brand-row">
      <div class="brand">FRAMEFORGE</div>
      <div class="brand-sub">Ottimizzazioni trasparenti per streamer &amp; gamer</div>
      <div class="ver-pill">GUI v2</div>
    </div>
    <div class="safety">
      <strong>SICUREZZA GARANTITA</strong> - Non tocchiamo MAI Windows Defender, Firewall o servizi di sicurezza. Ogni modifica ha backup automatico ed e reversibile.
    </div>
    <div class="meta-row">
      <div>
        <div class="hw-line" id="hwLine">PC: rilevamento in corso...</div>
        <div class="admin-line" id="adminLine"></div>
      </div>
      <div class="header-actions">
        <label class="live-sync-toggle" data-testid="live-sync-label" title="Invia CPU/GPU/RAM/temp in tempo reale al Command Center cloud">
          <input type="checkbox" id="liveSyncToggle" data-testid="live-sync-toggle" />
          <span class="live-sync-dot" aria-hidden="true"></span>
          <span class="live-sync-text">Sync Cloud</span>
        </label>
        <div class="backup-badge" id="backupBadge" data-testid="backup-badge" role="button" tabindex="0" title="Clicca per vedere la lista">Backup: 0</div>
        <div class="backup-panel" id="backupPanel" data-testid="backup-panel" hidden>
          <div class="backup-panel-title">Modifiche reversibili</div>
          <ul id="backupList" class="backup-list"></ul>
          <div class="backup-panel-hint">Usa "RIPRISTINA TUTTO" in fondo per riportare il PC allo stato iniziale.</div>
        </div>
      </div>
    </div>
  </header>

  <div class="preset-bar">
    <div class="preset-label">Preset:</div>
    <button class="preset-btn" data-preset="competitive" data-testid="preset-competitive">Competitivo</button>
    <button class="preset-btn" data-preset="streaming" data-testid="preset-streaming">Streaming</button>
    <button class="preset-btn" data-preset="complete" data-testid="preset-complete">Completo</button>
    <button class="preset-btn" data-preset="none" data-testid="preset-none">Nessuno</button>
    <div class="preset-spacer"></div>
    <input type="text" class="search" id="searchBox" placeholder="Cerca tweak..." data-testid="search-input" />
  </div>

  <div class="tabs" id="tabs"></div>

  <main id="cards"></main>

  <footer>
    <div class="log" id="log"></div>
    <div class="btn-bar">
      <div class="selection-count" id="selCount">0 tweak selezionati</div>
      <label class="bench-toggle">
        <input type="checkbox" id="benchToggle" checked /> Benchmark PRIMA/DOPO
      </label>
      <button class="btn-primary" id="applyBtn" data-testid="apply-selected-btn">Applica selezionati</button>
      <button class="btn-danger" id="restoreBtn" data-testid="restore-all-btn">Ripristina tutto</button>
    </div>
  </footer>

  <div class="toast" id="toast"></div>

<script>
(function(){
  const TOKEN = "__TOKEN__";
  const CATS = [
    { key: "gaming",  label: "Gaming & FPS" },
    { key: "input",   label: "Latenza & Input" },
    { key: "network", label: "Rete & Streaming" },
    { key: "system",  label: "Sistema & Debloat" },
    { key: "profiles", label: "Profili Cloud" }
  ];
  let state = { tweaks: [], hw: {}, admin: false, backup: 0, backup_ids: [], presets: {}, profiles: null };
  let selected = new Set();
  let activeCat = "gaming";
  let searchQ = "";
  let logSince = 0;
  let applying = false;

  function api(path, opts) {
    opts = opts || {};
    const url = path + (path.indexOf("?") >= 0 ? "&" : "?") + "tk=" + encodeURIComponent(TOKEN);
    return fetch(url, opts).then(r => r.json());
  }
  function toast(msg, cls) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast show" + (cls ? " " + cls : "");
    clearTimeout(t._h); t._h = setTimeout(() => t.className = "toast", 2400);
  }
  function esc(s) {
    return String(s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  }
  function stateClass(s) {
    const x = String(s || "");
    if (/attivo|disabilit|disattivat|gia|prestazioni|nessun/i.test(x)) return "ok";
    return "";
  }
  function isApplied(t) {
    if (t.fit.skip) return false;
    return stateClass(t.state) === "ok";
  }

  function renderTabs() {
    const el = document.getElementById("tabs");
    el.innerHTML = CATS.map(c => {
      if (c.key === "profiles") {
        const count = state.profiles?.profiles?.length ?? "…";
        return `<button class="tab ${c.key === activeCat ? "active" : ""}" data-cat="${c.key}" data-testid="tab-${c.key}">${c.label}<span class="count">${count}</span></button>`;
      }
      const inCat = state.tweaks.filter(t => t.cat === c.key && !t.fit.skip);
      const todo = inCat.filter(t => !isApplied(t)).length;
      const total = inCat.length;
      return `<button class="tab ${c.key === activeCat ? "active" : ""}" data-cat="${c.key}" data-testid="tab-${c.key}">${c.label}<span class="count">${todo}/${total}</span></button>`;
    }).join("");
    [...el.querySelectorAll(".tab")].forEach(b => b.onclick = () => {
      activeCat = b.dataset.cat;
      if (activeCat === "profiles" && !state.profiles) loadProfiles();
      renderTabs();
      renderCards();
    });
  }

  function renderCards() {
    const el = document.getElementById("cards");
    if (activeCat === "profiles") { renderProfilesTab(el); return; }
    const items = state.tweaks.filter(t => t.cat === activeCat).filter(t => {
      if (!searchQ) return true;
      const q = searchQ.toLowerCase();
      return (t.name + " " + (t.problem||"") + " " + (t.impact||"")).toLowerCase().includes(q);
    });
    if (!items.length) { el.innerHTML = `<div class="empty">Nessun tweak in questa categoria.</div>`; return; }
    el.innerHTML = items.map(t => {
      const applied = isApplied(t);
      t.applied = applied;
      const sel = selected.has(t.id);
      const skipCls = t.fit.skip ? " skip" : "";
      const appliedCls = applied ? " applied" : "";
      const riskCls = t.risk === "caution" ? " risk-caution" : "";
      const selCls = sel ? " selected" : "";
      const stCls = stateClass(t.state);
      const riskPill = t.risk === "caution" ? `<span class="risk-pill">Cautela</span>` : "";
      let hint = "";
      if (t.fit.skip) hint = `<div class="hint skip">Non applicabile: ${esc(t.fit.hint)}</div>`;
      else if (t.fit.warn) hint = `<div class="hint">Attenzione: ${esc(t.fit.hint)}</div>`;
      else if (t.fit.note) hint = `<div class="hint">Nota: ${esc(t.fit.hint)}</div>`;
      return `
        <div class="card${skipCls}${riskCls}${selCls}${appliedCls}" data-id="${t.id}" data-testid="card-${t.id}">
          <div class="card-head">
            <input type="checkbox" class="cb" data-id="${t.id}" ${sel?"checked":""} ${t.fit.skip?"disabled":""} data-testid="cb-${t.id}" />
            <div class="name">${esc(t.name)}</div>
            ${applied ? `<span class="ok-pill" data-testid="applied-${t.id}">GIA ATTIVO</span>` : ""}
            ${riskPill}
          </div>
          <div class="state ${stCls}">Stato: ${esc(t.state)}</div>
          <div class="desc-block">
            <div class="row"><div class="k">Problema</div><div class="v">${esc(t.problem)}</div></div>
            <div class="row"><div class="k motivo">Motivo</div><div class="v">${esc(t.reason)}</div></div>
            <div class="row"><div class="k mod">Modifica</div><div class="v">${esc(t.desc)}</div></div>
            <div class="row"><div class="k impatto">Impatto</div><div class="v impatto">${esc(t.impact)}</div></div>
          </div>
          ${hint}
          <div class="actions">
            ${applied
              ? `<span class="applied-note">Nessuna azione necessaria</span>`
              : `<button class="btn-apply-one" data-apply="${t.id}" ${t.fit.skip?"disabled":""} data-testid="apply-one-${t.id}">Applica</button>`}
          </div>
        </div>`;
    }).join("");
    el.querySelectorAll(".cb").forEach(cb => cb.onchange = e => {
      const id = e.target.dataset.id;
      if (e.target.checked) selected.add(id); else selected.delete(id);
      updateSelCount();
      const card = e.target.closest(".card");
      if (card) card.classList.toggle("selected", e.target.checked);
    });
    el.querySelectorAll(".btn-apply-one").forEach(b => b.onclick = () => applyOne(b.dataset.apply));
  }

  function updateSelCount() {
    document.getElementById("selCount").innerHTML = `<b>${selected.size}</b> tweak selezionati`;
  }

  // -------- Cloud profiles tab --------
  async function loadProfiles() {
    const el = document.getElementById("cards");
    if (activeCat === "profiles") el.innerHTML = `<div class="empty">Caricamento profili dal cloud…</div>`;
    try {
      const d = await api("/api/profiles-cloud");
      state.profiles = d && !d.err ? d : { profiles: [], templates: [], catalog: [], err: d?.err };
    } catch (e) {
      state.profiles = { profiles: [], templates: [], catalog: [], err: "network" };
    }
    if (activeCat === "profiles") { renderTabs(); renderCards(); }
  }

  function renderProfilesTab(el) {
    const p = state.profiles;
    if (!p) { el.innerHTML = `<div class="empty">Caricamento profili…</div>`; loadProfiles(); return; }
    if (p.err) { el.innerHTML = `<div class="empty">Cloud non raggiungibile. Verifica la connessione internet e riprova.</div>`; return; }
    const catalogMap = {};
    (p.catalog || []).forEach(c => { catalogMap[c.id] = c.name; });
    const cardHtml = (item, opts) => {
      const isTemplate = !!opts.template;
      const tweakIds = item.tweak_ids || [];
      const names = tweakIds.map(id => catalogMap[id]).filter(Boolean).slice(0, 6);
      const extra = tweakIds.length > 6 ? ` <span>+${tweakIds.length - 6}</span>` : "";
      const meta = isTemplate ? `📚 Template community · ${tweakIds.length} tweak` : `👤 Il tuo profilo · ${tweakIds.length} tweak`;
      const testid = isTemplate ? `profile-template-${item.id}` : `profile-${item.id}`;
      return `<div class="profile-card" data-testid="${testid}">
        <h3>${esc(item.name || item.game_name || 'Senza nome')}</h3>
        <div class="profile-meta">${meta}</div>
        <div class="profile-tweaks">${names.map(n => `<span>${esc(n)}</span>`).join("")}${extra}</div>
        <button class="profile-apply" data-testid="apply-${testid}" onclick='applyProfile(${JSON.stringify(tweakIds)})'>Applica profilo</button>
      </div>`;
    };
    let html = "";
    if ((p.profiles || []).length) {
      html += `<div class="profile-section-title" data-testid="section-my-profiles">// I MIEI PROFILI</div>`;
      html += p.profiles.map(pr => cardHtml(pr, { template: false })).join("");
    } else {
      html += `<div class="profile-section-title">// I MIEI PROFILI</div><div class="empty" style="grid-column: 1 / -1;">Nessun profilo personale ancora. Creane uno su forgefps.dev/app/profiles.</div>`;
    }
    if ((p.templates || []).length) {
      html += `<div class="profile-section-title" data-testid="section-templates">// TEMPLATE COMMUNITY</div>`;
      html += p.templates.map(t => cardHtml(t, { template: true })).join("");
    }
    el.innerHTML = html;
  }

  window.applyProfile = function(tweakIds) {
    if (!Array.isArray(tweakIds) || !tweakIds.length) return;
    // Select the tweaks in the local catalog matching this profile.
    selected.clear();
    let matched = 0;
    for (const id of tweakIds) {
      if (state.tweaks.find(t => t.id === id && !t.fit.skip)) { selected.add(id); matched++; }
    }
    if (!matched) { toast("Nessun tweak compatibile con il tuo hardware", "err"); return; }
    toast(`Profilo caricato: ${matched} tweak selezionati`, "ok");
    // Jump to Gaming tab so the user sees what got selected.
    activeCat = "gaming";
    renderTabs(); renderCards(); updateSelCount();
  };

  function renderHeader() {
    const hw = state.hw || {};
    const gpuTxt = hw.gpu || "?";
    const chassis = hw.laptop ? "Laptop" : "Desktop";
    const disk = hw.ssd ? "SSD" : "HDD";
    const win11 = hw.win11 ? " | Win 11" : "";
    document.getElementById("hwLine").innerHTML =
      `PC: <b>${chassis}</b> | GPU <b>${esc(gpuTxt)}</b> | RAM <b>${hw.ram||"?"} GB</b> | <b>${disk}</b>${win11} -> tweak adattati automaticamente`;
    const adm = document.getElementById("adminLine");
    if (state.admin) { adm.className = "admin-line ok"; adm.textContent = "Amministratore: SI - tutte le ottimizzazioni disponibili."; }
    else { adm.className = "admin-line no"; adm.textContent = "Amministratore: NO - alcune opzioni non verranno applicate."; }
    document.getElementById("backupBadge").textContent = `Backup: ${state.backup} modifiche reversibili`;
    renderBackupPanel();
  }

  // Populate the backup dropdown with the names of the tweaks currently reversible.
  function renderBackupPanel() {
    const badge = document.getElementById("backupBadge");
    const list = document.getElementById("backupList");
    if (!list) return;
    const ids = Array.isArray(state.backup_ids) ? state.backup_ids : [];
    // ID -> friendly name via existing tweaks catalog.
    const items = ids.map(id => {
      const tw = state.tweaks.find(t => t.id === id);
      return { id, name: tw ? tw.name : id };
    });
    list.innerHTML = "";
    if (items.length === 0) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Nessuna modifica applicata ancora.";
      list.appendChild(li);
      badge.classList.add("disabled");
    } else {
      badge.classList.remove("disabled");
      for (const it of items) {
        const li = document.createElement("li");
        li.setAttribute("data-testid", `backup-item-${it.id}`);
        li.textContent = it.name;
        list.appendChild(li);
      }
    }
  }

  function toggleBackupPanel(force) {
    const panel = document.getElementById("backupPanel");
    if (!panel) return;
    const willOpen = typeof force === "boolean" ? force : panel.hasAttribute("hidden");
    if (willOpen) panel.removeAttribute("hidden");
    else panel.setAttribute("hidden", "");
  }

  function applyPreset(key) {
    document.querySelectorAll(".preset-btn").forEach(b => b.classList.toggle("active", b.dataset.preset === key));
    selected.clear();
    if (key === "none") { renderCards(); updateSelCount(); return; }
    const list = key === "complete"
      ? state.tweaks.filter(t => !t.fit.skip && !isApplied(t)).map(t => t.id)
      : (state.presets[key] || []).filter(id => {
          const t = state.tweaks.find(x => x.id === id);
          return t && !t.fit.skip && !isApplied(t);
        });
    list.forEach(id => selected.add(id));
    renderCards(); updateSelCount();
  }

  function pollLog() {
    fetch(`/api/log?tk=${encodeURIComponent(TOKEN)}&since=${logSince}`)
      .then(r => r.json())
      .then(d => {
        if (d.logs && d.logs.length) {
          const el = document.getElementById("log");
          d.logs.forEach(l => {
            const div = document.createElement("div");
            div.innerHTML = `<span class="ts">${l.ts}</span>${esc(l.msg)}`;
            el.appendChild(div);
          });
          el.scrollTop = el.scrollHeight;
          logSince = d.total;
        }
        if (typeof d.applying === "boolean") setApplying(d.applying);
      }).catch(()=>{});
  }
  function setApplying(v) {
    applying = v;
    document.getElementById("applyBtn").disabled = v;
    document.getElementById("restoreBtn").disabled = v;
  }

  async function refreshState(showToast) {
    const d = await api("/api/state");
    state.tweaks = d.tweaks || [];
    state.hw = d.hw || {}; state.admin = !!d.admin;
    state.backup = d.backup || 0; state.backup_ids = d.backup_ids || []; state.presets = d.presets || {};
    renderHeader(); renderTabs(); renderCards();
    if (showToast) toast("Aggiornato", "ok");
  }

  async function applySelected() {
    if (!selected.size) { toast("Seleziona almeno un tweak"); return; }
    setApplying(true);
    const bench = document.getElementById("benchToggle").checked;
    const d = await api("/api/apply", { method: "POST", headers:{"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ ids: Array.from(selected), benchmark: bench }) });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = d.backup || state.backup; if (d.backup_ids) state.backup_ids = d.backup_ids; renderHeader(); renderCards(); }
    setApplying(false);
    toast("Ottimizzazioni applicate", "ok");
  }
  async function applyOne(id) {
    setApplying(true);
    const d = await api("/api/apply-one", { method: "POST", headers:{"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ id }) });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = d.backup || state.backup; if (d.backup_ids) state.backup_ids = d.backup_ids; renderHeader(); renderCards(); }
    setApplying(false);
    toast("Applicato");
  }
  async function doRestore() {
    if (!confirm("Ripristinare TUTTE le modifiche dal backup?")) return;
    setApplying(true);
    const d = await api("/api/restore", { method: "POST", headers:{"X-FF-Token":TOKEN} });
    if (d.tweaks) { state.tweaks = d.tweaks; state.backup = 0; state.backup_ids = []; renderHeader(); renderCards(); }
    setApplying(false);
    toast("Ripristino completato", "ok");
  }

  // events
  document.querySelectorAll(".preset-btn").forEach(b => b.onclick = () => applyPreset(b.dataset.preset));
  document.getElementById("applyBtn").onclick = applySelected;
  document.getElementById("restoreBtn").onclick = doRestore;
  document.getElementById("searchBox").oninput = e => { searchQ = e.target.value; renderCards(); };

  // Live Sync toggle: streams telemetry to cloud when ON.
  const _liveToggle = document.getElementById("liveSyncToggle");
  if (_liveToggle) {
    _liveToggle.addEventListener("change", async () => {
      try {
        const d = await api("/api/live-sync", { method: "POST", headers: {"Content-Type":"application/json","X-FF-Token":TOKEN}, body: JSON.stringify({ enabled: _liveToggle.checked }) });
        if (d && d.ok) toast(d.enabled ? "Sync Cloud attivo · dati in streaming" : "Sync Cloud disattivato", d.enabled ? "ok" : null);
      } catch { _liveToggle.checked = !_liveToggle.checked; toast("Errore attivazione sync", "err"); }
    });
  }

  // Backup badge toggle: open panel with reversible tweaks list.
  const _backupBadge = document.getElementById("backupBadge");
  if (_backupBadge) {
    _backupBadge.addEventListener("click", () => toggleBackupPanel());
    _backupBadge.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleBackupPanel(); }
    });
    document.addEventListener("click", (e) => {
      const panel = document.getElementById("backupPanel");
      if (!panel || panel.hasAttribute("hidden")) return;
      if (!panel.contains(e.target) && e.target !== _backupBadge) toggleBackupPanel(false);
    });
  }
  window.addEventListener("beforeunload", () => {
    try { navigator.sendBeacon(`/api/close?tk=${encodeURIComponent(TOKEN)}`, ""); } catch(e){}
  });

  refreshState();
  setInterval(pollLog, 400);
})();
</script>
</body>
</html>
'@
  $html = $html.Replace('__TOKEN__', $sessionToken)

  # Directory temp per il profilo Edge (isolato)
  $tmpDir = Join-Path $env:TEMP "forgefps-gui"
  if (-not (Test-Path $tmpDir)) { New-Item -ItemType Directory -Path $tmpDir | Out-Null }
  $profileDir = Join-Path $tmpDir 'edge-profile'

  $localUrl = "http://127.0.0.1:$port/?tk=$sessionToken"
  Say "[*] GUI locale su $localUrl" 'Cyan'
  Say "    (se la finestra non si apre, incolla l'URL sopra in un browser)" 'DarkGray'

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
    $edge = Start-Process -FilePath $edgeExe -ArgumentList $edgeArgs -PassThru
  } catch { try { $listener.Stop() } catch {}; return $false }

  # Il launcher msedge.exe fa "hop and exit" se c'e' gia' un'istanza Edge attiva.
  # Cerco il process reale (quello con il nostro user-data-dir) dopo un breve wait.
  Start-Sleep -Milliseconds 1800
  $realEdge = $null
  try {
    $procs = Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
      if ($p.CommandLine -and $p.CommandLine -like "*$profileDir*") {
        $realEdge = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
        break
      }
    }
  } catch {}
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
            backup_ids = @($script:BK.Keys)
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
          if ($bench) { WebLog 'Benchmark PRIMA in corso...'; $before = Run-Benchmark; WebLog ("  Punteggio PRIMA: {0}" -f $before.overall) }
          foreach ($id in $ids) {
            $t = $script:TWMAP[$id]; if (-not $t) { continue }
            WebLog ("-> {0}" -f $t.name); & $t.apply
          }
          Save-Backup
          if ($bench) {
            WebLog 'Benchmark DOPO in corso...'; $after = Run-Benchmark
            $pct = 0; if ($before.overall) { $pct = [math]::Round(($after.overall - $before.overall) / $before.overall * 100) }
            WebLog ("  Punteggio DOPO: {0}  (variazione {1}%)" -f $after.overall, $pct)
            Send-Benchmark @{ before = $before; after = $after; ts = (Get-Date).ToString('o') }
          }
          Send-Data (Get-Specs) (Get-Health) (Get-StartupList)
          WebLog 'FATTO. Dati inviati a FrameForge. Riavvio consigliato.'
          $script:APPLYING = $false
          Send-Json $ctx @{ ok = $true; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = @($script:BK.Keys); before = $before; after = $after }
        }
        elseif ($path -eq '/api/apply-one' -and $method -eq 'POST') {
          $body = Read-Body $ctx | ConvertFrom-Json
          $t = $script:TWMAP[$body.id]
          if ($t) { WebLog ("-> {0}" -f $t.name); & $t.apply; Save-Backup }
          Send-Json $ctx @{ ok = $true; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = @($script:BK.Keys) }
        }
        elseif ($path -eq '/api/profiles-cloud' -and $method -eq 'GET') {
          # Proxy to FrameForge cloud: /api/agent/profiles (X-Agent-Token auth).
          try {
            $resp = Invoke-RestMethod -Uri "$BACKEND/api/agent/profiles" -Headers @{ 'X-Agent-Token' = $TOKEN } -TimeoutSec 8
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
        elseif ($path -eq '/api/restore' -and $method -eq 'POST') {
          WebLog 'Ripristino dal backup...'; $msg = Invoke-Restore; WebLog ('  ' + $msg)
          Send-Json $ctx @{ ok = $true; message = $msg; tweaks = Get-TweakDto; backup = $script:BK.Count; backup_ids = @($script:BK.Keys) }
        }
        elseif ($path -eq '/api/close') {
          Send-Json $ctx @{ ok = $true }
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
  $form.Text = 'FrameForge - Ottimizzazioni sicure'
  $form.Size = New-Object System.Drawing.Size(800, 962)
  $form.StartPosition = 'CenterScreen'
  $form.BackColor = $bg; $form.ForeColor = $white
  $form.Font = New-Object System.Drawing.Font('Segoe UI', 9)

  # ---- Header ----
  $head = New-Object System.Windows.Forms.Panel
  $head.Location = New-Object System.Drawing.Point(0, 0); $head.Size = New-Object System.Drawing.Size(800, 150); $head.BackColor = $bg2
  $form.Controls.Add($head)

  $bolt = New-Object System.Windows.Forms.Label
  $bolt.Text = 'FRAMEFORGE'; $bolt.ForeColor = $acc
  $bolt.Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
  $bolt.Location = New-Object System.Drawing.Point(18, 12); $bolt.AutoSize = $true
  $head.Controls.Add($bolt)

  $sub = New-Object System.Windows.Forms.Label
  $sub.Text = 'Ottimizzazioni trasparenti per streamer & gamer'; $sub.ForeColor = $gray
  $sub.Location = New-Object System.Drawing.Point(20, 46); $sub.AutoSize = $true
  $head.Controls.Add($sub)

  $sec = New-Object System.Windows.Forms.Label
  $sec.Text = "SICUREZZA GARANTITA  -  Non tocchiamo MAI Windows Defender, Firewall o servizi di sicurezza. Ogni modifica ha un backup automatico ed e reversibile."
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
    $s = & $t.state
    $lbl = $script:STATUS[$id]; if (-not $lbl) { return }
    $lbl.Text = "Stato attuale: $s"
    if ($s -like '*(da *') { $lbl.ForeColor = $script:C_ACC }
    elseif ($s -match 'Attivo|Disabilit|Disattivat|Gia|Prestazioni') { $lbl.ForeColor = $script:C_GREEN }
    else { $lbl.ForeColor = $script:C_ACC }
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
    if ($script:BENCHCB.Checked) { GuiLog 'Benchmark PRIMA in corso...'; $before = Run-Benchmark; GuiLog ("  Punteggio PRIMA: {0}" -f $before.overall) }
    foreach ($t in $script:TWEAKS) { if ($script:CHECKS[$t.id].Checked) { GuiLog ("-> {0}" -f $t.name); & $t.apply } }
    Save-Backup
    if ($script:BENCHCB.Checked) {
      GuiLog 'Benchmark DOPO in corso...'; $after = Run-Benchmark
      $pct = $(if ($before.overall) { [math]::Round(($after.overall - $before.overall) / $before.overall * 100) } else { 0 })
      GuiLog ("  Punteggio DOPO: {0}  (variazione {1}%)" -f $after.overall, $pct)
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
if ($MODE -eq 'restore') { Say "`n[*] Ripristino dal backup..." 'Cyan'; Say ('   ' + (Invoke-Restore)) 'Green'; return }

if ($MODE -eq 'benchmark') {
  Say "`n[*] Benchmark (CPU / RAM / Disco / Rete)..." 'Cyan'
  $bench = Run-Benchmark; Show-Bench $bench 'BENCHMARK'
  Send-Benchmark @{ after = $bench; ts = (Get-Date).ToString('o') }
  Say "`n[OK] Benchmark inviato! Vedi il confronto in FrameForge -> Il mio PC." 'Green'
  return
}

if ($MODE -eq 'optimize') {
  Say "`n[*] Apro il pannello ottimizzazioni..." 'Cyan'
  $ok = $false
  try { $ok = Show-WebGui } catch { $ok = $false }
  if (-not $ok) {
    Say '[!] Interfaccia web non disponibile, uso la GUI classica...' 'Yellow'
    $ok = Show-Gui
  }
  if (-not $ok) {
    Say '[!] Interfaccia grafica non disponibile. Applico i preset Completo...' 'Yellow'
    $before = Run-Benchmark; Show-Bench $before 'PRIMA'
    Say ("[HW] {0} | GPU {1} | RAM {2} GB | {3} -> tweak adattati" -f $(if($script:HW.laptop){'Laptop'}else{'Desktop'}), $script:HW.gpu, $script:HW.ram, $(if($script:HW.ssd){'SSD'}else{'HDD'})) 'Cyan'
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
  try { Invoke-RestMethod -Uri "$BACKEND/api/agent/netresult" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
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

  Say '   [1/3] Latenza a riposo (baseline, 50 campioni)...' 'DarkGray'
  $idle = Measure-Ping $target 50 40 1000
  $idleP50 = Percentile $idle.rtts 0.5
  $idleMin = Percentile $idle.rtts 0.0
  Say ("        idle p50: {0} ms | min: {1} ms | jitter: {2} ms" -f $idleP50, $idleMin, (Jitter $idle.rtts)) 'DarkGray'

  Say '   [2/3] Sotto carico DOWNLOAD (8 stream, warm-up 2.5s)...' 'DarkGray'
  $dljobs = @(); for ($i = 0; $i -lt 8; $i++) { $dljobs += Start-Job -ScriptBlock $script:DL_BLOCK -ArgumentList $downUrl }
  Start-Sleep -Milliseconds 2500
  $down = Measure-Ping $target 80 40 2000
  $dljobs | Stop-Job -ErrorAction SilentlyContinue; $dljobs | Remove-Job -Force -ErrorAction SilentlyContinue
  $downP50 = Percentile $down.rtts 0.5; $downP95 = Percentile $down.rtts 0.95
  Say ("        download p50: {0} ms | p95: {1} ms" -f $downP50, $downP95) 'DarkGray'
  Start-Sleep -Milliseconds 1000

  Say '   [3/3] Sotto carico UPLOAD (4 stream, warm-up 2.5s)...' 'DarkGray'
  $upP50 = $null; $upP95 = $null; $upLost = 0; $upSent = 0
  try {
    $upjobs = @(); for ($i = 0; $i -lt 4; $i++) { $upjobs += Start-Job -ScriptBlock $script:UP_BLOCK -ArgumentList $upUrl }
    Start-Sleep -Milliseconds 2500
    $up = Measure-Ping $target 60 40 2000
    $upjobs | Stop-Job -ErrorAction SilentlyContinue; $upjobs | Remove-Job -Force -ErrorAction SilentlyContinue
    $upP50 = Percentile $up.rtts 0.5; $upP95 = Percentile $up.rtts 0.95
    $upLost = $up.lost; $upSent = $up.sent
    Say ("        upload p50: {0} ms | p95: {1} ms" -f $upP50, $upP95) 'DarkGray'
  } catch {}

  $totalSent = $down.sent + $upSent
  $totalLost = $down.lost + $upLost
  $loss = if ($totalSent -gt 0) { [math]::Round(100.0 * $totalLost / $totalSent, 1) } else { 0 }
  $res = [ordered]@{
    idle_ms   = $idleP50
    idle_min  = $idleMin
    down_ms   = $downP50
    down_p95  = $downP95
    up_ms     = $upP50
    up_p95    = $upP95
    jitter_ms = (Jitter $idle.rtts)
    loss_pct  = $loss
    samples   = ($idle.rtts.Count + $down.rtts.Count)
  }
  Send-NetResult $res
  Say "`n[OK] Test rete completato. Apri FrameForge -> Rete per il voto (A-F) e i consigli." 'Green'
}

if ($MODE -eq 'bufferbloat') {
  Say "`n== FrameForge - Test rete / Bufferbloat ==" 'Cyan'
  Say '   Non usare internet durante il test (~15s). Misuro latenza a riposo e sotto carico.' 'DarkGray'
  Run-Bufferbloat
  return
}


if ($MODE -eq 'monitor') {
  Say "`n[*] Monitoraggio live avviato. Lascia aperta questa finestra. Premi Ctrl+C per fermare." 'Cyan'
  Say '   Apri FrameForge -> Live per i grafici in tempo reale.' 'DarkGray'
  Start-Fps
  $noFpsCount = 0
  try {
    while ($true) {
      $s = Get-TelemetrySample
      $f = Get-Fps
      if ($f) { $s.fps = $f.fps; $s.game = $f.game; if ($null -ne $f.latency_ms) { $s.latency_ms = $f.latency_ms }; $noFpsCount = 0 }
      elseif ($script:PM_ON) { $noFpsCount++; if ($noFpsCount -eq 10) { Show-FpsDiag } }
      Send-Telemetry $s
      $g = if ($s.ContainsKey('gpu_util')) { ("GPU {0}% {1}C {2}MHz" -f $s.gpu_util, $s.gpu_temp, $s.gpu_clock) } else { 'GPU n/d' }
      $ct = if ($s.ContainsKey('cpu_temp')) { ("{0}C" -f $s.cpu_temp) } else { '' }
      $lt = if ($s.ContainsKey('latency_ms')) { (" {0}ms" -f $s.latency_ms) } else { '' }
      $fp = if ($s.ContainsKey('fps')) { (" | {0} FPS ({1}){2}" -f $s.fps, $s.game, $lt) } else { '' }
      Say ("   CPU {0}% {1} | RAM {2}% | {3}{4}" -f $s.cpu_util, $ct, $s.ram_used_pct, $g, $fp)
      Start-Sleep -Milliseconds 1000
    }
  } finally { Stop-Fps }
  return
}

if ($MODE -eq 'prematch') {
  Say "`n== FrameForge - Modalita Prima del match ==" 'Cyan'
  $setPower = __PREMATCH_POWER__
  $prevPlan = ''
  if ($setPower) {
    $out = powercfg /getactivescheme
    $prevPlan = ([regex]::Match($out, '([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})')).Value
    if ($prevPlan) { Say ("   Piano energetico attuale salvato: {0}" -f $prevPlan) 'DarkGray' }
    powercfg /setactive scheme_min 2>$null
    Say "   [OK] Piano Prestazioni elevate attivato." 'Green'
  } else {
    Say "   [i] Piano energetico lasciato invariato (da impostazioni)." 'DarkGray'
  }
  $apps = @(__PREMATCH_APPS__)
  $closed = 0
  foreach ($a in $apps) {
    $p = Get-Process -Name $a -ErrorAction SilentlyContinue
    if ($p) { Stop-Process -InputObject $p -Force -ErrorAction SilentlyContinue; $closed++ }
  }
  Say ("   [OK] App in background chiuse: {0} (su {1} selezionate)" -f $closed, $apps.Count) 'Green'
  Say "`n[BOOST ATTIVO] Avvia pure il tuo gioco. Buon match!" 'Yellow'
  Read-Host "`nPremi INVIO quando hai finito di giocare per ripristinare tutto"
  if ($setPower) {
    if ($prevPlan) { powercfg /setactive $prevPlan 2>$null; Say "   [OK] Piano energetico originale ripristinato." 'Green' }
    else { powercfg /setactive scheme_balanced 2>$null; Say "   [OK] Piano energetico bilanciato ripristinato." 'Green' }
  }
  Say "`n[FATTO] Le app chiuse puoi riaprirle normalmente. A presto!" 'Cyan'
  return
}

if ($MODE -eq 'booster') {
  Say "`n== FrameForge - GAME BOOSTER ==" 'Cyan'
  Say '   Sorveglio i giochi in avvio: quando ne rilevo uno ti propongo il boost con 5 secondi per annullare.' 'Gray'
  Say '   NIENTE parte in automatico al 100%: hai sempre la scelta. A fine partita ripristino tutto. Ctrl+C per uscire.' 'Gray'
  try { Add-Type -AssemblyName System.Windows.Forms } catch {}
  $doPower = __BOOSTER_POWER__
  $doPriority = __BOOSTER_PRIORITY__
  $doPurge = __BOOSTER_PURGE__
  $apps = @(__BOOSTER_APPS__)
  Say ("   Azioni configurate (FrameForge -> Games): priorita={0} energia={1} purgeRAM={2} appDaChiudere={3}" -f $doPriority, $doPower, $doPurge, $apps.Count) 'DarkGray'
  if (-not (Test-Admin)) { Say '   [i] Senza Amministratore rilevo il gioco dalla finestra a schermo intero (niente conteggio FPS).' 'DarkYellow' }
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
  if (Test-Admin) { Start-Fps }
  $boosted = $false; $skipUntilExit = $false; $bGame = ''; $bStart = $null; $prevPlan = ''
  $curName = ''; $detCount = 0; $lostCount = 0; $script:BACTS = @()
  Say "`n[SORVEGLIANZA ATTIVA] Avvia pure il tuo gioco quando vuoi." 'Green'
  try {
    while ($true) {
      $name = ''; $gpid = 0
      $f = Get-Fps
      if ($f -and $f.fps -ge 15) { $name = $f.game }
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
            if ($gpid) { try { (Get-Process -Id $gpid).PriorityClass = 'High'; $acts.Add('priorita_high'); Say '   [OK] Priorita CPU del gioco: HIGH.' 'Green' } catch {} }
          }
          if ($doPower) {
            $out = powercfg /getactivescheme
            $prevPlan = ([regex]::Match($out, '([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})')).Value
            powercfg /setactive scheme_min 2>$null
            $acts.Add('piano_energetico'); Say '   [OK] Piano Prestazioni elevate attivo (solo durante il gioco).' 'Green'
          }
          if ($apps.Count -gt 0) {
            $closed = 0
            foreach ($a in $apps) { $pr = Get-Process -Name $a -ErrorAction SilentlyContinue; if ($pr) { Stop-Process -InputObject $pr -Force -ErrorAction SilentlyContinue; $closed++ } }
            if ($closed -gt 0) { $acts.Add("app_chiuse_$closed"); Say ("   [OK] App in background chiuse: {0}." -f $closed) 'Green' }
          }
          if ($doPurge) { Clear-StandbyList; $acts.Add('purge_ram'); Say '   [OK] RAM standby svuotata.' 'Green' }
          $boosted = $true; $bGame = $curName; $bStart = Get-Date; $script:BACTS = @($acts)
          Say ("`n[BOOST ATTIVO] Buona partita! Ripristino tutto quando esci da {0}." -f ($curName -replace '\.exe$', '')) 'Yellow'
        }
      }
      if (($boosted -or $skipUntilExit) -and $lostCount -ge 8) {
        if ($boosted) {
          Say ("`n[FINE PARTITA] {0}: ripristino..." -f ($bGame -replace '\.exe$', '')) 'Cyan'
          if ($doPower) { if ($prevPlan) { powercfg /setactive $prevPlan 2>$null } else { powercfg /setactive scheme_balanced 2>$null }; Say '   [OK] Piano energetico ripristinato.' 'Green' }
          $dur = [int]((Get-Date) - $bStart).TotalSeconds
          $body = @{ boost_session = @{ game = ($bGame -replace '\.exe$', ''); duration_s = $dur; actions = @($script:BACTS); ended_at = (Get-Date).ToString('o') } } | ConvertTo-Json -Depth 4 -Compress
          try { Invoke-RestMethod -Uri "$BACKEND/api/agent/report-specs" -Method Post -ContentType 'application/json' -Headers @{ 'X-Agent-Token' = $TOKEN } -Body $body | Out-Null } catch {}
          Say ("   Sessione registrata ({0} min). Torno in sorveglianza." -f [math]::Round($dur / 60, 1)) 'DarkGray'
        } else {
          Say "`n[i] Partita finita (boost annullato). Torno in sorveglianza." 'DarkGray'
        }
        $boosted = $false; $skipUntilExit = $false; $bGame = ''; $prevPlan = ''; $curName = ''; $detCount = 0
      }
      Start-Sleep -Milliseconds 2000
    }
  } finally {
    Stop-Fps
    if ($boosted -and $doPower) { if ($prevPlan) { powercfg /setactive $prevPlan 2>$null } else { powercfg /setactive scheme_balanced 2>$null } }
    Say "`n[STOP] Game Booster fermato. Tutto ripristinato." 'Cyan'
  }
  return
}

# default: sync (safe)
Say "`n[*] Rilevamento hardware, salute e avvio..." 'Cyan'
if (-not (Test-Admin)) { Say '   [i] Suggerimento: esegui in PowerShell (Amministratore) per temperature CPU/GPU reali e analisi piu precisa.' 'DarkYellow' }
$specs = Get-Specs
Say ("   CPU: {0}" -f $specs.cpu); Say ("   GPU: {0}" -f $specs.gpu)
Say ("   MB : {0}  ({1} {2})" -f $specs.motherboard, $specs.cpu_socket, $specs.chipset)
$health = Get-Health
if ($health.ContainsKey('cpu_temp')) { Say ("   Temp CPU: {0}C  |  Temp GPU: {1}C" -f $health.cpu_temp, $(if($health.ContainsKey('gpu_temp')){$health.gpu_temp}else{'n/d'})) 'DarkGray' }
elseif (Test-Admin) {
  Say '   [diag] Temp CPU non leggibile. Sensori temperatura rilevati:' 'DarkYellow'
  if ($script:LHM_LAST) { Say ("         " + $script:LHM_LAST) 'DarkGray' }
  else { Say '         (nessuno)' 'DarkGray' }
  $mi = Test-MemoryIntegrity
  $bl = Test-VulnerableDriverBlocklist
  Say ("   [diag] Integrita memoria: {0}  |  Blocklist driver vulnerabili: {1}" -f $(if($mi){'ATTIVA'}else{'disattivata'}), $(if($bl){'ATTIVA'}else{'disattivata'})) 'DarkGray'
  if ($mi -or $bl) {
    Say '   [!] CAUSA: Windows sta bloccando il driver dei sensori CPU (protezione di sicurezza).' 'Yellow'
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
    Say '   [i] Il driver sensori CPU non ha risposto (possibile blocco antivirus). La temp GPU funziona comunque.' 'DarkGray'
  }
}
Send-Data $specs $health (Get-StartupList)
$games = Get-Games
if ($games.Count -gt 0) { Send-Games $games; Say ("   Giochi rilevati: {0}" -f $games.Count) 'DarkGray' }
$running = Get-RunningApps
Send-Running $running
Say ("   App in background attive: {0}" -f $running.Count) 'DarkGray'
Say "`n[OK] Dati inviati! Apri FrameForge -> Il mio PC per analisi e consigli." 'Green'
'''
