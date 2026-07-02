"""PowerShell one-liner agent, served at GET /api/agent/script and run via `irm ... | iex`.
Non-interactive by design. Modes: sync (safe, default), optimize (apply tweaks + backup), restore."""

PS_SCRIPT = r'''
$ErrorActionPreference = 'SilentlyContinue'
$BACKEND = '__BACKEND_URL__'
$TOKEN   = '__AGENT_TOKEN__'
$MODE    = '__MODE__'
$BACKUP  = Join-Path $env:TEMP 'boostpc_backup.json'

function Say($m, $c='Gray') { Write-Host $m -ForegroundColor $c }

Say '======================================' 'Yellow'
Say '   BOOST PC AI - Agent PowerShell' 'Yellow'
Say '======================================' 'Yellow'

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
  $ct = (Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object -First 1)
  if ($ct) { $h.cpu_temp = [math]::Round(($ct.CurrentTemperature - 2732)/10) }
  return $h
}

function Get-StartupList {
  return @(Get-CimInstance Win32_StartupCommand | Select-Object -ExpandProperty Name | Select-Object -First 40)
}

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

function Backup-State {
  $data = @{}
  if (Test-Path $BACKUP) { $data = Get-Content $BACKUP -Raw | ConvertFrom-Json | ConvertTo-HashtableSafe }
  $data.power_plan = (powercfg /getactivescheme)
  $data.game_mode  = "$((Get-ItemProperty 'HKCU:\Software\Microsoft\GameBar' -Name AllowAutoGameMode).AllowAutoGameMode)"
  $data.hags       = "$((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode).HwSchMode)"
  $data | ConvertTo-Json | Set-Content $BACKUP
}

function ConvertTo-HashtableSafe { $h=@{}; foreach($p in $input.PSObject.Properties){ $h[$p.Name]=$p.Value }; return $h }

function Invoke-Optimize {
  Say "`n[*] Applico ottimizzazioni (con backup)..." 'Cyan'
  Backup-State
  # Pulizia temp
  Get-ChildItem $env:TEMP -Recurse -Force 2>$null | Remove-Item -Recurse -Force 2>$null
  Say '   - File temporanei puliti'
  # Piano energetico alte prestazioni
  powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null
  Say '   - Piano energetico: alte prestazioni'
  # Game Mode + HAGS
  reg add "HKCU\Software\Microsoft\GameBar" /v AllowAutoGameMode /t REG_DWORD /d 1 /f | Out-Null
  reg add "HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers" /v HwSchMode /t REG_DWORD /d 2 /f | Out-Null
  Say '   - Game Mode + GPU Scheduling abilitati'
  ipconfig /flushdns | Out-Null
  Say '   - DNS flush eseguito'
  Say '   (Riavvio consigliato. Ripristino: usa il comando "restore")'
}

function Invoke-Restore {
  Say "`n[*] Ripristino dal backup..." 'Cyan'
  if (-not (Test-Path $BACKUP)) { Say '   Nessun backup trovato.' 'Red'; return }
  $b = Get-Content $BACKUP -Raw | ConvertFrom-Json
  if ($b.game_mode) { reg add "HKCU\Software\Microsoft\GameBar" /v AllowAutoGameMode /t REG_DWORD /d $b.game_mode /f | Out-Null }
  if ($b.hags)      { reg add "HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers" /v HwSchMode /t REG_DWORD /d $b.hags /f | Out-Null }
  Say '   Impostazioni ripristinate.' 'Green'
}

if ($MODE -eq 'restore') { Invoke-Restore; return }

Say "`n[*] Rilevamento hardware, salute e avvio..." 'Cyan'
$specs = Get-Specs
Say ("   CPU: {0}" -f $specs.cpu)
Say ("   GPU: {0}" -f $specs.gpu)
Say ("   MB : {0}  ({1} {2})" -f $specs.motherboard, $specs.cpu_socket, $specs.chipset)

if ($MODE -eq 'optimize') {
  if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Say "`n[!] Per le ottimizzazioni esegui PowerShell come Amministratore. Invio solo i dati." 'Yellow'
  } else {
    Invoke-Optimize
  }
}

$health  = Get-Health
$startup = Get-StartupList
Send-Data $specs $health $startup
'''
