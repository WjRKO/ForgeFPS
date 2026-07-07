"""PowerShell agent, served at GET /api/agent/script and run via `irm ... | iex`.
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

PS_SCRIPT = r'''
$ErrorActionPreference = 'SilentlyContinue'
$BACKEND = '__BACKEND_URL__'
$TOKEN   = '__AGENT_TOKEN__'
$MODE    = '__MODE__'
$BACKUP  = Join-Path $env:TEMP 'boostpc_backup.json'
$script:PROFILE = @(__PROFILE_IDS__)

function Say($m, $c='Gray') { Write-Host $m -ForegroundColor $c }
function ConvertTo-HashtableSafe { $h=@{}; foreach($p in $input.PSObject.Properties){ $h[$p.Name]=$p.Value }; return $h }

Say '======================================' 'Yellow'
Say '   BOOST PC AI - Agent PowerShell' 'Yellow'
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
function Set-Reg($path, $name, $type, $value) {
  Backup-Reg $path $name $type
  if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
  New-ItemProperty -Path $path -Name $name -PropertyType $type -Value $value -Force | Out-Null
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
  $tmp = Join-Path $env:TEMP 'boostpc_bench.bin'
  $data = New-Object byte[] (64MB); (New-Object Random).NextBytes($data)
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
  Say ("   CPU {0} | RAM {1} MB/s | Disco W/R {2}/{3} MB/s | Ping {4} ms | PUNTEGGIO {5}" -f `
    $r.cpu_score, $r.ram_mbps, $r.disk_write_mbps, $r.disk_read_mbps, $r.ping_ms, $r.overall) 'Yellow'
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
  $skip = @('Steamworks Common Redistributables', 'Steam Linux Runtime', 'Proton EasyAntiCheat Runtime')
  return @($games | Where-Object { $skip -notcontains $_ -and $_ -notmatch 'Proton|Runtime|Redistributable' } | Select-Object -Unique | Select-Object -First 60)
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
      -ArgumentList '--output_file', "`"$($script:PM_CSV)`"", '--stop_existing_session', '--v1_metrics', '--no_console_stats' `
      -WindowStyle Hidden -PassThru -RedirectStandardOutput $script:PM_OUT -RedirectStandardError $script:PM_ERR
    $script:PM_ON = $true
    Start-Sleep -Milliseconds 1500
    if ($script:PM_PROC -and $script:PM_PROC.HasExited) {
      $script:PM_ON = $false
      $err = ''
      foreach ($lf in @($script:PM_ERR, $script:PM_OUT)) { if (Test-Path $lf) { $err += (Get-Content $lf -Raw -ErrorAction SilentlyContinue) } }
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
  if (Test-Path $script:PM_CSV) {
    $sz = (Get-Item $script:PM_CSV).Length
    Say ("             CSV presente: si ({0} byte)" -f $sz) 'DarkGray'
    $raw = Read-Shared $script:PM_CSV
    $ln = $raw -split "`r?`n" | Where-Object { $_ -ne '' }
    Say ("             Righe CSV: {0}" -f $ln.Count) 'DarkGray'
    if ($ln.Count -ge 1) { Say ("             Intestazione: " + ($ln[0].Substring(0,[math]::Min(120,$ln[0].Length)))) 'DarkGray' }
  } else {
    Say '             CSV presente: NO (PresentMon non sta scrivendo dati)' 'DarkGray'
  }
  if (-not $alive) {
    $err = ''
    foreach ($lf in @($script:PM_ERR, $script:PM_OUT)) { if (Test-Path $lf) { $err += (Get-Content $lf -Raw -ErrorAction SilentlyContinue) } }
    if ($err.Trim()) { Say ('             Errore PresentMon: ' + ($err.Trim() -replace "`r?`n", ' | ')) 'DarkGray' }
  }
  Say '   [diag FPS] Se serve, incolla queste righe in chat. Ricorda: gli FPS compaiono SOLO mentre un app renderizza a schermo (uno screensaver si chiude al primo movimento del mouse).' 'DarkYellow'
}
function Get-Fps {
  if (-not $script:PM_ON) { return $null }
  $raw = Read-Shared $script:PM_CSV
  if (-not $raw) { return $null }
  $lines = $raw -split "`r?`n" | Where-Object { $_ -ne '' }
  if (-not $lines -or $lines.Count -le $script:PM_ROWS) { return $null }
  $hdr = $lines[0] -split ','
  $iApp = -1; $iMs = -1
  for ($k = 0; $k -lt $hdr.Count; $k++) {
    $h = $hdr[$k].Trim().ToLower()
    if ($h -eq 'application') { $iApp = $k }
    if ($h -like '*betweenpresents*') { $iMs = $k }
  }
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
    if (-not $byApp.ContainsKey($app)) { $byApp[$app] = @{ sum = 0.0; n = 0 } }
    $byApp[$app].sum += $ms; $byApp[$app].n++
  }
  if ($byApp.Count -eq 0) { return $null }
  $top = $byApp.GetEnumerator() | Sort-Object { $_.Value.n } -Descending | Select-Object -First 1
  $avg = $top.Value.sum / $top.Value.n
  if ($avg -le 0) { return $null }
  return @{ fps = [int]([math]::Round(1000 / $avg)); game = ($top.Key -replace '\.exe$', '') }
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
  $svc = Get-Service DiagTrack -ErrorAction SilentlyContinue
  if ($svc -and -not $script:BK.ContainsKey('svc::DiagTrack')) { $script:BK['svc::DiagTrack'] = "$($svc.StartType)"; Stop-Service DiagTrack -Force 2>$null; Set-Service DiagTrack -StartupType Disabled 2>$null }
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
  $svc = Get-Service WSearch -ErrorAction SilentlyContinue
  if ($svc -and -not $script:BK.ContainsKey('svc::WSearch')) { $script:BK['svc::WSearch'] = "$($svc.StartType)"; Stop-Service WSearch -Force 2>$null; Set-Service WSearch -StartupType Disabled 2>$null }
}
$script:BLOAT = @('Microsoft.549981C3F5F10','Microsoft.BingNews','Microsoft.BingWeather','Microsoft.GetHelp',
  'Microsoft.Getstarted','Microsoft.WindowsFeedbackHub','Microsoft.MicrosoftSolitaireCollection',
  'Microsoft.People','Microsoft.WindowsMaps','Microsoft.3DBuilder','Microsoft.MixedReality.Portal',
  'king.com.CandyCrushSaga','Microsoft.SkypeApp')
function Do-Debloat { foreach ($pkg in $script:BLOAT) { $app = Get-AppxPackage -Name $pkg -ErrorAction SilentlyContinue; if ($app) { $app | Remove-AppxPackage -ErrorAction SilentlyContinue } } }

# ---------------- Tweak catalogue (cat / id / name / desc / state / apply) ----------------
$script:TWEAKS = @(
  # GAMING & FPS
  @{ cat='gaming'; id='power'; name='Piano energetico prestazioni massime'; desc='Ultimate Performance + core parking off, processore 100%, USB suspend/PCIe ASPM off.';
     state={ $p=(powercfg /getactivescheme); if($p -match 'high|ultimate|prestazioni elevate'){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Power } }
  @{ cat='gaming'; id='gaming'; name='Boost gaming (Game Mode, HAGS, Game DVR off)'; desc='Game Mode + GPU Scheduling on, Game DVR off (piu FPS in game).';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\GameBar' 'AllowAutoGameMode') -eq 1){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Gaming } }
  @{ cat='gaming'; id='priority'; name='Priorita GPU/CPU ai giochi (MMCSS)'; desc='Piu risorse ai giochi in primo piano + responsiveness al massimo.';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile' 'SystemResponsiveness') -eq 0){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Priority } }
  @{ cat='gaming'; id='mpo'; name='Disabilita MPO (Multi-Plane Overlay)'; desc='Risolve stutter/flickering e lo SCHERMO NERO in OBS Game Capture.';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows\Dwm' 'OverlayTestMode') -eq 5){'Disabilitato'}else{'Attivo (da disabilitare)'} }; apply={ Do-Mpo } }
  @{ cat='gaming'; id='gpu_msi'; name='GPU: MSI mode ON (latenza DPC)'; desc='Message Signaled Interrupts sulla GPU: riduce la latenza DPC (NVIDIA/AMD).';
     state={ $pnp=Get-GpuPnp; if($pnp){ $v=Get-RegVal "HKLM:\SYSTEM\CurrentControlSet\Enum\$pnp\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties" 'MSISupported'; if($v -eq 1){'Attivo'}else{'Da attivare'} }else{'n/d'} }; apply={ Do-GpuMsi } }
  @{ cat='gaming'; id='amd_ulps'; name='AMD: disabilita ULPS'; desc='Ultra Low Power State off sulle Radeon: meno stutter/latenza (solo GPU AMD).';
     state={ if((Get-GpuVendor) -eq 'AMD'){'GPU AMD: applicabile'}else{'Solo GPU AMD'} }; apply={ Do-AmdUlps } }
  @{ cat='gaming'; id='nvidia_tel'; name='NVIDIA: disabilita telemetria'; desc='Disattiva task/servizio di telemetria NVIDIA: meno background (solo GPU NVIDIA).';
     state={ if((Get-GpuVendor) -eq 'NVIDIA'){'GPU NVIDIA: applicabile'}else{'Solo GPU NVIDIA'} }; apply={ Do-NvidiaTel } }
  @{ cat='gaming'; id='hibernate'; name='Disabilita ibernazione'; desc='Rimuove hiberfil.sys: libera diversi GB su disco.';
     state={ 'Applica per liberare spazio' }; apply={ Do-Hibernate } }
  # LATENZA & INPUT
  @{ cat='input'; id='mouse'; name='Accelerazione mouse OFF (raw input)'; desc='Mira piu precisa e costante: disattiva la enhance pointer precision.';
     state={ if("$(Get-RegVal 'HKCU:\Control Panel\Mouse' 'MouseSpeed')" -eq '0'){'Gia disattivata'}else{'Attiva (da disattivare)'} }; apply={ Do-Mouse } }
  @{ cat='input'; id='timer'; name='Timer resolution globale'; desc='Richieste timer resolution globali (Win11): scheduling piu costante nei giochi.';
     state={ if((Get-RegVal 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\kernel' 'GlobalTimerResolutionRequests') -eq 1){'Attivo'}else{'Da attivare'} }; apply={ Do-Timer } }
  @{ cat='input'; id='usb'; name='USB power management OFF'; desc='Evita cali di polling di mouse/tastiera (input drop).';
     state={ 'Applica per input stabile' }; apply={ Do-Usb } }
  @{ cat='input'; id='stickykeys'; name='Sticky/Filter/Toggle Keys OFF'; desc='Niente popup che ti buttano fuori dal gioco premendo Shift ripetuto.';
     state={ if("$(Get-RegVal 'HKCU:\Control Panel\Accessibility\StickyKeys' 'Flags')" -eq '506'){'Disattivati'}else{'Attivi (da disattivare)'} }; apply={ Do-StickyKeys } }
  @{ cat='input'; id='startupdelay'; name='Startup delay app ridotto'; desc='Le app all avvio partono subito, niente ritardo artificiale.';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize' 'StartupDelayInMSec') -eq 0){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-StartupDelay } }
  # RETE & STREAMING
  @{ cat='network'; id='network'; name='Rete: Nagle OFF + TCP tuning'; desc='Riduce la latenza online (Nagle off, autotuning/ECN/RSS).';
     state={ 'Applica per meno lag online' }; apply={ Do-Network } }
  @{ cat='network'; id='dns'; name='DNS veloci (Cloudflare 1.1.1.1)'; desc='DNS 1.1.1.1/1.0.0.1 sulla scheda attiva (reversibile a DHCP).';
     state={ $a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; if($a){ $d=(Get-DnsClientServerAddress -InterfaceAlias $a.Name -AddressFamily IPv4).ServerAddresses -join ','; if($d -match '1.1.1.1'){'Gia Cloudflare'}else{"Attuale: $d"} }else{'n/d'} }; apply={ Do-Dns } }
  @{ cat='network'; id='qos'; name='Rimuovi 20% banda riservata QoS'; desc='NonBestEffortLimit=0: recupera la banda riservata da Windows.';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched' 'NonBestEffortLimit') -eq 0){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-Qos } }
  @{ cat='network'; id='deliveryopt'; name='Delivery Optimization P2P OFF'; desc='Windows non usa piu la tua banda in upload per distribuire aggiornamenti: stream piu stabile.';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config' 'DODownloadMode') -eq 0){'Disattivato'}else{'Attivo (da disattivare)'} }; apply={ Do-DeliveryOpt } }
  @{ cat='network'; id='obs_priority'; name='OBS ad alta priorita'; desc='obs64/obs32.exe partono con priorita CPU alta: encoding piu fluido durante lo stream.';
     state={ if((Get-RegVal 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\obs64.exe\PerfOptions' 'CpuPriorityClass') -eq 3){'Attivo'}else{'Da attivare'} }; apply={ Do-ObsPriority } }
  # SISTEMA & DEBLOAT
  @{ cat='system'; id='clean'; name='Pulizia temp + cache Windows Update'; desc='Rimuove file temporanei, cache aggiornamenti e svuota il DNS.';
     state={ $mb=0; Get-ChildItem $env:TEMP -Recurse -File -Force 2>$null | ForEach-Object { $mb+=$_.Length }; "$([math]::Round($mb/1MB)) MB da pulire" }; apply={ Do-Cleanup } }
  @{ cat='system'; id='visual'; name='Effetti visivi: modalita prestazioni'; desc='Riduce animazioni/trasparenze per una UI piu reattiva.';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting') -eq 2){'Prestazioni'}else{'Da ottimizzare'} }; apply={ Do-Visual } }
  @{ cat='system'; id='telemetry'; name='Telemetria (DiagTrack) OFF'; desc='Disattiva il servizio di telemetria: meno CPU e rete in background.';
     state={ $s=Get-Service DiagTrack -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){'Attiva (da disattivare)'}else{'Disattivata'} }; apply={ Do-Telemetry } }
  @{ cat='system'; id='ads'; name='Suggerimenti/ads di Windows OFF'; desc='Disattiva app suggerite e contenuti promozionali nel menu Start.';
     state={ 'Applica per rimuovere ads' }; apply={ Do-Ads } }
  @{ cat='system'; id='bgapps'; name='App in background OFF (globale)'; desc='Blocca le app UWP in background: meno consumo di CPU/RAM.';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled') -eq 1){'Attivo'}else{'Da ottimizzare'} }; apply={ Do-BgApps } }
  @{ cat='system'; id='gamebar_rec'; name='Xbox Game Bar recording OFF'; desc='Disattiva la registrazione in background della Game Bar.';
     state={ if((Get-RegVal 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' 'AppCaptureEnabled') -eq 0){'Disattivato'}else{'Attivo (da disattivare)'} }; apply={ Do-GamebarRec } }
  @{ cat='system'; id='debloat'; name='Debloat app superflue (UWP)'; desc='Rimuove Xbox/Bing/Solitaire/Candy Crush ecc. (reinstallabili dallo Store).';
     state={ $n=0; foreach($p in $script:BLOAT){ if(Get-AppxPackage -Name $p -ErrorAction SilentlyContinue){$n++} }; "$n app rimovibili" }; apply={ Do-Debloat } }
  @{ cat='system'; id='search_index'; name='Windows Search indexing OFF (invasivo)'; desc='Meno carico disco/CPU, ma disattiva l indicizzazione della ricerca file.';
     state={ $s=Get-Service WSearch -ErrorAction SilentlyContinue; if($s -and $s.Status -eq 'Running'){'Attivo'}else{'Disattivato'} }; apply={ Do-SearchIndex } }
)

$script:PRESETS = @{
  'competitivo' = @('power','gaming','priority','mpo','gpu_msi','amd_ulps','nvidia_tel','mouse','timer','usb','stickykeys','network','qos','visual','bgapps')
  'streaming'   = @('power','gaming','priority','mpo','gpu_msi','amd_ulps','nvidia_tel','network','dns','qos','deliveryopt','obs_priority','telemetry','ads','bgapps','gamebar_rec')
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

# ---------------- GUI ----------------
function Show-Gui {
  try { Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing } catch { return $false }
  [System.Windows.Forms.Application]::EnableVisualStyles()
  $isAdmin = Test-Admin
  $bg   = [System.Drawing.Color]::FromArgb(15,15,18)
  $bg2  = [System.Drawing.Color]::FromArgb(10,10,12)
  $acc  = [System.Drawing.Color]::FromArgb(229,255,0)
  $gray = [System.Drawing.Color]::FromArgb(150,150,160)

  $form = New-Object System.Windows.Forms.Form
  $form.Text = 'BOOST PC AI - Ottimizzazioni'
  $form.Size = New-Object System.Drawing.Size(700, 860)
  $form.StartPosition = 'CenterScreen'
  $form.BackColor = $bg; $form.ForeColor = [System.Drawing.Color]::White
  $form.Font = New-Object System.Drawing.Font('Segoe UI', 9)

  $title = New-Object System.Windows.Forms.Label
  $title.Text = 'BOOST PC  -  Ottimizzazioni per streamer & gamer'
  $title.ForeColor = $acc; $title.Font = New-Object System.Drawing.Font('Segoe UI', 13, [System.Drawing.FontStyle]::Bold)
  $title.Location = New-Object System.Drawing.Point(16, 12); $title.AutoSize = $true
  $form.Controls.Add($title)

  $adminLbl = New-Object System.Windows.Forms.Label
  $adminLbl.Location = New-Object System.Drawing.Point(18, 44); $adminLbl.AutoSize = $true
  if ($isAdmin) { $adminLbl.Text = 'Amministratore: SI - tutte le ottimizzazioni disponibili.'; $adminLbl.ForeColor = [System.Drawing.Color]::FromArgb(0,255,102) }
  else { $adminLbl.Text = 'Amministratore: NO - alcune opzioni non verranno applicate. Usa il pulsante in basso.'; $adminLbl.ForeColor = [System.Drawing.Color]::FromArgb(255,59,48) }
  $form.Controls.Add($adminLbl)

  # Preset buttons
  $presetLbl = New-Object System.Windows.Forms.Label
  $presetLbl.Text = 'Preset:'; $presetLbl.Location = New-Object System.Drawing.Point(18, 70); $presetLbl.AutoSize = $true; $presetLbl.ForeColor = $gray
  $form.Controls.Add($presetLbl)
  function New-Preset($text, $x, $key) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text; $b.Location = New-Object System.Drawing.Point($x, 66); $b.Size = New-Object System.Drawing.Size(150, 30)
    $b.FlatStyle = 'Flat'; $b.ForeColor = [System.Drawing.Color]::White; $b.BackColor = [System.Drawing.Color]::FromArgb(30,30,38)
    $b.Tag = $key
    $b.Add_Click({
      $k = $this.Tag
      foreach ($t in $script:TWEAKS) {
        if ($k -eq 'completo') { $script:CHECKS[$t.id].Checked = $true }
        else { $script:CHECKS[$t.id].Checked = ($script:PRESETS[$k] -contains $t.id) }
      }
    })
    $form.Controls.Add($b)
  }
  New-Preset '🏆 Competitivo' 70 'competitivo'
  New-Preset '🎥 Streaming' 226 'streaming'
  New-Preset '🧰 Completo' 382 'completo'

  # Tabs by category
  $tc = New-Object System.Windows.Forms.TabControl
  $tc.Location = New-Object System.Drawing.Point(14, 104); $tc.Size = New-Object System.Drawing.Size(660, 400)
  $cats = @(
    @{ key='gaming';  title='🎮 Gaming & FPS' },
    @{ key='input';   title='⚡ Latenza & Input' },
    @{ key='network'; title='🌐 Rete & Streaming' },
    @{ key='system';  title='🧹 Sistema & Debloat' }
  )
  $script:CHECKS = @{}
  foreach ($c in $cats) {
    $tp = New-Object System.Windows.Forms.TabPage; $tp.Text = $c.title; $tp.BackColor = $bg2
    $panel = New-Object System.Windows.Forms.Panel; $panel.Dock = 'Fill'; $panel.AutoScroll = $true; $panel.BackColor = $bg2
    $y = 8
    foreach ($t in $script:TWEAKS) {
      if ($t.cat -ne $c.key) { continue }
      $cb = New-Object System.Windows.Forms.CheckBox
      if ($script:PROFILE.Count -gt 0) { $cb.Checked = ($script:PROFILE -contains $t.id) }
      else { $cb.Checked = ($t.id -ne 'search_index') }
      $cb.ForeColor = [System.Drawing.Color]::White
      $cb.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
      $cb.Location = New-Object System.Drawing.Point(10, $y); $cb.AutoSize = $true
      $cb.Text = ("{0}    [{1}]" -f $t.name, (& $t.state))
      $panel.Controls.Add($cb); $script:CHECKS[$t.id] = $cb; $y += 22
      $d = New-Object System.Windows.Forms.Label; $d.Text = $t.desc; $d.ForeColor = $gray
      $d.Location = New-Object System.Drawing.Point(30, $y); $d.MaximumSize = New-Object System.Drawing.Size(600, 0); $d.AutoSize = $true
      $panel.Controls.Add($d); $y += 34
    }
    $tp.Controls.Add($panel); $tc.TabPages.Add($tp)
  }
  $form.Controls.Add($tc)

  $benchCb = New-Object System.Windows.Forms.CheckBox
  $benchCb.Text = 'Esegui benchmark PRIMA/DOPO per misurare il guadagno reale'
  $benchCb.Checked = $true; $benchCb.ForeColor = [System.Drawing.Color]::FromArgb(0,224,255)
  $benchCb.Location = New-Object System.Drawing.Point(18, 512); $benchCb.AutoSize = $true
  $form.Controls.Add($benchCb); $script:BENCHCB = $benchCb

  $out = New-Object System.Windows.Forms.TextBox
  $out.Multiline = $true; $out.ReadOnly = $true; $out.ScrollBars = 'Vertical'
  $out.Location = New-Object System.Drawing.Point(14, 540); $out.Size = New-Object System.Drawing.Size(660, 200)
  $out.BackColor = [System.Drawing.Color]::Black; $out.ForeColor = [System.Drawing.Color]::FromArgb(0,255,102)
  $out.Font = New-Object System.Drawing.Font('Consolas', 9)
  $form.Controls.Add($out); $script:OUT = $out
  function GuiLog($m) { $script:OUT.AppendText("$m`r`n"); [System.Windows.Forms.Application]::DoEvents() }

  $applyBtn = New-Object System.Windows.Forms.Button
  $applyBtn.Text = 'APPLICA SELEZIONATI'; $applyBtn.Location = New-Object System.Drawing.Point(14, 752); $applyBtn.Size = New-Object System.Drawing.Size(200, 42)
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
    foreach ($t in $script:TWEAKS) { $script:CHECKS[$t.id].Text = ("{0}    [{1}]" -f $t.name, (& $t.state)) }
    Send-Data (Get-Specs) (Get-Health) (Get-StartupList)
    GuiLog 'FATTO. Dati inviati a BOOST PC. Riavvio consigliato.'
    $script:APPLYBTN.Enabled = $true
  })

  $restoreBtn = New-Object System.Windows.Forms.Button
  $restoreBtn.Text = 'RIPRISTINA'; $restoreBtn.Location = New-Object System.Drawing.Point(224, 752); $restoreBtn.Size = New-Object System.Drawing.Size(140, 42)
  $restoreBtn.FlatStyle = 'Flat'; $restoreBtn.ForeColor = [System.Drawing.Color]::FromArgb(255,59,48)
  $restoreBtn.Add_Click({ GuiLog 'Ripristino dal backup...'; GuiLog ('  ' + (Invoke-Restore)); foreach ($t in $script:TWEAKS) { $script:CHECKS[$t.id].Text = ("{0}    [{1}]" -f $t.name, (& $t.state)) } })
  $form.Controls.Add($restoreBtn)

  if (-not $isAdmin) {
    $elevBtn = New-Object System.Windows.Forms.Button
    $elevBtn.Text = 'Riavvia come Amministratore'; $elevBtn.Location = New-Object System.Drawing.Point(374, 752); $elevBtn.Size = New-Object System.Drawing.Size(220, 42)
    $elevBtn.FlatStyle = 'Flat'; $elevBtn.ForeColor = [System.Drawing.Color]::White
    $elevBtn.Add_Click({
      $cmd = "irm '$BACKEND/api/agent/script?t=$TOKEN&mode=optimize' | iex"
      Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command',$cmd 2>$null
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
  Say "`n[OK] Benchmark inviato! Vedi il confronto in BOOST PC -> Il mio PC." 'Green'
  return
}

if ($MODE -eq 'optimize') {
  Say "`n[*] Apro il pannello ottimizzazioni..." 'Cyan'
  $ok = Show-Gui
  if (-not $ok) {
    Say '[!] Interfaccia grafica non disponibile. Applico i preset Completo...' 'Yellow'
    $before = Run-Benchmark; Show-Bench $before 'PRIMA'
    foreach ($t in $script:TWEAKS) { if ($t.id -ne 'search_index') { Say ("   -> {0}" -f $t.name); & $t.apply } }
    Save-Backup
    $after = Run-Benchmark; Show-Bench $after 'DOPO'
    Send-Benchmark @{ before = $before; after = $after; ts = (Get-Date).ToString('o') }
    Send-Data (Get-Specs) (Get-Health) (Get-StartupList)
  }
  return
}

if ($MODE -eq 'monitor') {
  Say "`n[*] Monitoraggio live avviato. Lascia aperta questa finestra. Premi Ctrl+C per fermare." 'Cyan'
  Say '   Apri BOOST PC -> Live per i grafici in tempo reale.' 'DarkGray'
  Start-Fps
  $noFpsCount = 0
  try {
    while ($true) {
      $s = Get-TelemetrySample
      $f = Get-Fps
      if ($f) { $s.fps = $f.fps; $s.game = $f.game; $noFpsCount = 0 }
      elseif ($script:PM_ON) { $noFpsCount++; if ($noFpsCount -eq 6) { Show-FpsDiag } }
      Send-Telemetry $s
      $g = if ($s.ContainsKey('gpu_util')) { ("GPU {0}% {1}C {2}MHz" -f $s.gpu_util, $s.gpu_temp, $s.gpu_clock) } else { 'GPU n/d' }
      $ct = if ($s.ContainsKey('cpu_temp')) { ("{0}C" -f $s.cpu_temp) } else { '' }
      $fp = if ($s.ContainsKey('fps')) { (" | {0} FPS ({1})" -f $s.fps, $s.game) } else { '' }
      Say ("   CPU {0}% {1} | RAM {2}% | {3}{4}" -f $s.cpu_util, $ct, $s.ram_used_pct, $g, $fp)
      Start-Sleep -Seconds 2
    }
  } finally { Stop-Fps }
  return
}

if ($MODE -eq 'prematch') {
  Say "`n== BoostPC - Modalita Prima del match ==" 'Cyan'
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
Say "`n[OK] Dati inviati! Apri BOOST PC -> Il mio PC per analisi e consigli." 'Green'
'''
