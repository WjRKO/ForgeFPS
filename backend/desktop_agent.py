AGENT_SCRIPT = r'''#!/usr/bin/env python3
"""
BOOST PC AI - Desktop Agent (Windows)
Companion locale: ottimizzazioni REALI + rilevamento hardware/salute per consigli AI su misura.
Uso:  python boostpc_agent.py   (consigliato come Amministratore)
"""
import os
import sys
import json
import shutil
import subprocess
import tempfile
import ctypes
import re
import urllib.request

BACKEND_URL = "__BACKEND_URL__"
AGENT_TOKEN = "__AGENT_TOKEN__"
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boostpc_backup.json")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
    except Exception as e:
        return f"errore: {e}"


def ps(cmd):
    return run('powershell -NoProfile -Command "%s"' % cmd)


def _folder_size_mb(path):
    total = 0
    if os.path.isdir(path):
        for dp, _, fs in os.walk(path):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except Exception:
                    pass
    return round(total / (1024 * 1024), 1)


def _clean(v):
    return " ".join(v.split()).strip() if v else ""


def nvsmi():
    """Return dict from nvidia-smi if available, else None."""
    out = run("nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu,"
              "utilization.gpu,driver_version --format=csv,noheader,nounits")
    if not out or "not recognized" in out.lower() or "not found" in out.lower() or out.startswith("errore"):
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    if len(parts) < 6:
        return None
    try:
        return {"name": parts[0], "vram_total_mb": int(float(parts[1])),
                "vram_used_mb": int(float(parts[2])), "temp": int(float(parts[3])),
                "util": int(float(parts[4])), "driver": parts[5]}
    except Exception:
        return None


_NV = None


def get_nv():
    global _NV
    if _NV is None:
        _NV = nvsmi() or {}
    return _NV


def collect_specs():
    s = {}
    s["os"] = _clean(ps("(Get-CimInstance Win32_OperatingSystem).Caption"))
    s["os_build"] = _clean(ps("(Get-CimInstance Win32_OperatingSystem).BuildNumber"))
    # chassis: laptop vs desktop
    ct = ps("(Get-CimInstance Win32_SystemEnclosure).ChassisTypes -join ','")
    s["form_factor"] = "Laptop" if any(x in (ct or "") for x in ["8", "9", "10", "14", "30", "31", "32"]) else "Desktop"
    # CPU with cores/threads/clock
    s["cpu"] = _clean(ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"))
    s["cpu_cores"] = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfCores")
    s["cpu_threads"] = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfLogicalProcessors")
    s["cpu_clock_ghz"] = ps("[math]::round((Get-CimInstance Win32_Processor | Select-Object -First 1).MaxClockSpeed/1000,2)")
    # GPU: prefer nvidia-smi (exact), else discrete via WMI
    nv = get_nv()
    if nv.get("name"):
        s["gpu"] = nv["name"]
        s["gpu_vram_gb"] = str(round(nv["vram_total_mb"] / 1024))
        s["gpu_driver_version"] = nv["driver"]
    else:
        gpu_name = _clean(ps("$g=Get-CimInstance Win32_VideoController | "
                             "Where-Object { $_.Name -notmatch 'Basic|Virtual|Remote|Meta|Parsec|Citrix' } | "
                             "Select-Object -First 1; $g.Name"))
        if not gpu_name:
            gpu_name = _clean(ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name"))
        s["gpu"] = gpu_name
        vram = ps("$k=Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}' "
                  "-ErrorAction SilentlyContinue; $m=0; foreach($i in $k){ $q=(Get-ItemProperty $i.PSPath -Name "
                  "'HardwareInformation.qwMemorySize' -ErrorAction SilentlyContinue).'HardwareInformation.qwMemorySize'; "
                  "if($q -and $q -gt $m){$m=$q} }; if($m -gt 0){[math]::round($m/1GB,0)}")
        if not vram:
            vram = ps("[math]::round((Get-CimInstance Win32_VideoController | Select-Object -First 1).AdapterRAM/1GB,0)")
        s["gpu_vram_gb"] = vram
        s["gpu_driver_version"] = _clean(ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).DriverVersion"))
    s["refresh_hz"] = ps("(Get-CimInstance Win32_VideoController | "
                         "Where-Object {$_.CurrentRefreshRate -gt 0} | "
                         "Sort-Object CurrentRefreshRate -Descending | Select-Object -First 1).CurrentRefreshRate")
    # RAM: total + speed + module count + DDR type
    ram_total = ps("[math]::round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,0)")
    s["ram"] = f"{ram_total} GB" if ram_total else ""
    s["ram_speed_mhz"] = ps("(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).Speed")
    s["ram_modules"] = ps("(Get-CimInstance Win32_PhysicalMemory | Measure-Object).Count")
    smt = ps("(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).SMBIOSMemoryType")
    s["ram_type"] = {"20": "DDR", "21": "DDR2", "24": "DDR3", "26": "DDR4", "34": "DDR5"}.get((smt or "").strip(), "")
    # Motherboard: robustly pick the primary physical board (some systems expose multiple
    # Win32_BaseBoard instances; without -First 1 the fields get mixed / wrong board picked).
    mb_raw = ps("$b = Get-CimInstance Win32_BaseBoard | "
                "Where-Object { $_.Product -and $_.Product -notmatch 'Base Board|Default string|To be filled|None|^\\s*$' } | "
                "Select-Object -First 1; "
                "if(-not $b){ $b = Get-CimInstance Win32_BaseBoard | Select-Object -First 1 }; "
                "\"$($b.Manufacturer)|$($b.Product)|$($b.Version)\"")
    mb_mfg, mb_prod, mb_ver = ((mb_raw or "").split("|") + ["", "", ""])[:3]
    mb_mfg, mb_prod, mb_ver = _clean(mb_mfg), _clean(mb_prod), _clean(mb_ver)
    vendor_map = {"micro-star": "MSI", "asustek": "ASUS", "asus": "ASUS", "gigabyte": "Gigabyte",
                  "asrock": "ASRock", "hewlett": "HP", "dell": "Dell", "lenovo": "Lenovo",
                  "acer": "Acer", "biostar": "Biostar", "nzxt": "NZXT", "msi": "MSI"}
    low = mb_mfg.lower()
    for k, v in vendor_map.items():
        if k in low:
            mb_mfg = v
            break
    # Avoid duplicating vendor if already present in product name
    if mb_prod and mb_mfg and mb_mfg.lower() in mb_prod.lower():
        mb = mb_prod
    else:
        mb = " ".join(x for x in [mb_mfg, mb_prod] if x)
    if mb_ver and mb_ver.lower() not in ("1.0", "x.x", "default string", mb_prod.lower()) and len(mb_ver) > 2:
        clean_ver = mb_ver[3:].strip() if mb_ver.lower().startswith("rev") else mb_ver
        if clean_ver and clean_ver.lower() not in ("x.0x", "x.x"):
            mb += f" (rev {clean_ver})"
    s["motherboard"] = _clean(mb)
    sys_model = _clean(ps("(Get-CimInstance Win32_ComputerSystem | Select-Object -First 1).Model"))
    if sys_model.lower() not in ("system product name", "default string", "to be filled by o.e.m.", ""):
        s["system_model"] = sys_model
    s["bios"] = _clean(ps("$bi=Get-CimInstance Win32_BIOS | Select-Object -First 1; "
                          "\"$($bi.Manufacturer) $($bi.SMBIOSBIOSVersion)\""))
    # Socket + chipset (direct where possible, else derived from chipset family in board name)
    socket = _clean(ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).SocketDesignation"))
    chip_m = re.search(r"\b([XZBHA]\d{3}E?)\b", s.get("motherboard", ""), re.IGNORECASE)
    chipset = chip_m.group(1).upper() if chip_m else ""
    s["chipset"] = chipset
    # If socket looks generic (not AM*/LGA/sTR/sWRX), derive it from the chipset family
    if not re.search(r"AM\d|LGA|sTR|sWRX|SP\d|FM\d|TR4", socket, re.IGNORECASE):
        cs = chipset.upper()
        if cs in ("X570", "B550", "A520", "X470", "B450", "X370", "B350", "A320"):
            socket = "AM4"
        elif cs in ("X670E", "X670", "B650E", "B650", "A620"):
            socket = "AM5"
        elif cs in ("Z790", "B760", "H770", "H610", "Z690", "B660", "H670"):
            socket = "LGA1700"
        elif cs in ("Z590", "B560", "H570", "H510", "Z490", "B460", "H470", "H410"):
            socket = "LGA1200"
    s["cpu_socket"] = socket
    # Storage: primary disk model + type (SSD/HDD/NVMe) + size
    try:
        disk_info = ps("$d=Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object -First 1; "
                       "if($d){ $t=switch($d.MediaType){3{'HDD'}4{'SSD'}default{''}}; "
                       "$bus=if($d.BusType -eq 17){'NVMe '}else{''}; "
                       "$sz=[math]::round($d.Size/1GB,0); \"$($d.FriendlyName)|$bus$t|$sz\" }")
    except Exception:
        disk_info = ""
    if disk_info and "|" in disk_info:
        model, dtype, dsize = (disk_info.split("|") + ["", "", ""])[:3]
        s["disk"] = _clean(f"{model} {dtype} ({dsize} GB)")
    else:
        model = _clean(ps("(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).Model"))
        size = ps("[math]::round(((Get-CimInstance Win32_DiskDrive | Measure-Object -Property Size -Sum).Sum)/1GB,0)")
        s["disk"] = _clean(f"{model} ({size} GB)") if model else ""
    res = ps("$v=Get-CimInstance Win32_VideoController | Select-Object -First 1; "
             "\"$($v.CurrentHorizontalResolution)x$($v.CurrentVerticalResolution)\"")
    s["resolution"] = res if res and "x" in res else ""
    return {k: v for k, v in s.items() if v not in (None, "", "0")}


def collect_health():
    h = {}
    temp = _folder_size_mb(tempfile.gettempdir())
    temp += _folder_size_mb(os.path.expandvars(r"%LOCALAPPDATA%\\Temp"))
    h["temp_mb"] = round(temp, 1)
    su = ps("(Get-CimInstance Win32_StartupCommand | Measure-Object).Count")
    try:
        h["startup_count"] = int(su)
    except Exception:
        h["startup_count"] = 0
    h["power_plan"] = ps("(powercfg /getactivescheme)") or ""
    gm = ps("(Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\GameBar' -Name AllowAutoGameMode "
            "-ErrorAction SilentlyContinue).AllowAutoGameMode")
    h["game_mode"] = (gm.strip() == "1") if gm else False
    hags = ps("(Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers' "
              "-Name HwSchMode -ErrorAction SilentlyContinue).HwSchMode")
    h["gpu_scheduling"] = (hags.strip() == "2") if hags else False
    ramp = ps("$o=Get-CimInstance Win32_OperatingSystem; "
              "[math]::round(($o.TotalVisibleMemorySize-$o.FreePhysicalMemory)/$o.TotalVisibleMemorySize*100,0)")
    try:
        h["ram_used_pct"] = int(ramp)
    except Exception:
        pass
    dfp = ps("$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"; "
             "[math]::round($d.FreeSpace/$d.Size*100,0)")
    try:
        h["disk_free_pct"] = int(dfp)
    except Exception:
        pass
    h["gpu"] = ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name")
    h["gpu_driver_version"] = ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).DriverVersion")
    ddate = ps("$d=(Get-CimInstance Win32_VideoController | Select-Object -First 1).DriverDate; "
               "if($d){$d.ToString('yyyy-MM-dd')}")
    h["gpu_driver_date"] = ddate if ddate and "-" in ddate else None
    # Temperatures (GPU via nvidia-smi, CPU via WMI thermal zone - best effort)
    nv = get_nv()
    if nv.get("temp") is not None:
        h["gpu_temp"] = nv["temp"]
        h["gpu"] = nv.get("name") or h["gpu"]
        h["gpu_driver_version"] = nv.get("driver") or h["gpu_driver_version"]
        if nv.get("vram_total_mb"):
            h["vram_used_pct"] = round(nv["vram_used_mb"] / nv["vram_total_mb"] * 100)
    cpu_t = ps("$t=Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
               "-ErrorAction SilentlyContinue | Select-Object -First 1; "
               "if($t){[math]::round(($t.CurrentTemperature-2732)/10,0)}")
    try:
        if cpu_t and int(cpu_t) > 0:
            h["cpu_temp"] = int(cpu_t)
    except Exception:
        pass
    return h


def collect_startup():
    out = ps("Get-CimInstance Win32_StartupCommand | Select-Object -ExpandProperty Name")
    items = [l.strip() for l in out.splitlines() if l.strip()] if out else []
    return items[:40]


def send_all():
    if "__AGENT" in AGENT_TOKEN or not BACKEND_URL.startswith("http"):
        print("\n[!] Token non configurato. Riscarica l'agent dal tuo account BOOST PC.")
        return
    print("\n[*] Rilevamento hardware, salute e programmi all'avvio...")
    specs = collect_specs()
    health = collect_health()
    startup = collect_startup()
    for k, v in specs.items():
        print(f"    {k.upper():12}: {v or 'n/d'}")
    print(f"    Punteggio inviato: temp={health.get('temp_mb')}MB, avvio={health.get('startup_count')}, "
          f"driver={health.get('gpu_driver_version')}")
    payload = json.dumps({"data": specs, "health": health, "startup": startup}).encode("utf-8")
    req = urllib.request.Request(f"{BACKEND_URL}/api/agent/report-specs", data=payload,
                                 headers={"Content-Type": "application/json",
                                          "X-Agent-Token": AGENT_TOKEN}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print("\n[OK] Dati inviati!" if r.status == 200 else f"\n[!] Risposta: {r.status}")
            print("    Apri BOOST PC -> Il mio PC / Upgrade per analisi e consigli su misura.")
    except Exception as e:
        print(f"\n[!] Invio fallito: {e}")


def _backup(state):
    data = {}
    if os.path.exists(BACKUP_FILE):
        try:
            data = json.load(open(BACKUP_FILE))
        except Exception:
            data = {}
    data.update(state)
    json.dump(data, open(BACKUP_FILE, "w"), indent=2)


def clean_temp():
    print("\n[1] Pulizia file temporanei...")
    freed = 0
    for t in [tempfile.gettempdir(), os.path.expandvars(r"%SystemRoot%\\Temp"),
              os.path.expandvars(r"%LOCALAPPDATA%\\Temp")]:
        if not os.path.isdir(t):
            continue
        for name in os.listdir(t):
            path = os.path.join(t, name)
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    freed += os.path.getsize(path); os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
    print(f"    Liberati file temporanei (~{freed/(1024*1024):.1f} MB diretti)")


def flush_dns():
    print("\n[2] Flush DNS..."); print("    " + (run("ipconfig /flushdns") or "OK"))


def high_performance_power():
    print("\n[3] Piano energetico ad alte prestazioni...")
    current = ps("(powercfg /getactivescheme)")
    _backup({"power_plan": current})
    run("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
    print("    Attivato 'High Performance' (backup salvato).")


def top_processes():
    print("\n[4] Processi che consumano piu' RAM:")
    print(ps("Get-Process | Sort-Object WS -Descending | Select-Object -First 8 "
             "Name,@{N='RAM_MB';E={[math]::round($_.WS/1MB,1)}} | Format-Table -AutoSize | Out-String") or "    n/d")


def gaming_tweaks():
    print("\n[5] Tweak gaming (Game Mode + GPU scheduling)...")
    old_gm = ps("(Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\GameBar' -Name AllowAutoGameMode "
                "-ErrorAction SilentlyContinue).AllowAutoGameMode")
    old_hags = ps("(Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers' "
                  "-Name HwSchMode -ErrorAction SilentlyContinue).HwSchMode")
    _backup({"game_mode": old_gm, "hags": old_hags})
    run('reg add "HKCU\\Software\\Microsoft\\GameBar" /v AllowAutoGameMode /t REG_DWORD /d 1 /f')
    run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers" /v HwSchMode /t REG_DWORD /d 2 /f')
    print("    Game Mode + GPU Scheduling abilitati (backup salvato, riavvio consigliato).")


def disk_cleanup():
    print("\n[6] Pulizia disco di Windows..."); run("cleanmgr /sagerun:1"); print("    Avviata.")


def restore_tweaks():
    print("\n[8] Ripristino impostazioni dal backup...")
    if not os.path.exists(BACKUP_FILE):
        print("    Nessun backup trovato."); return
    b = json.load(open(BACKUP_FILE))
    if b.get("game_mode") is not None:
        run('reg add "HKCU\\Software\\Microsoft\\GameBar" /v AllowAutoGameMode /t REG_DWORD /d %s /f'
            % (b["game_mode"] or "0"))
    if b.get("hags") is not None:
        run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers" /v HwSchMode /t REG_DWORD /d %s /f'
            % (b["hags"] or "2"))
    print("    Impostazioni ripristinate ai valori precedenti.")


def menu():
    actions = {
        "1": ("Pulizia file temporanei", clean_temp),
        "2": ("Flush DNS", flush_dns),
        "3": ("Piano energetico alte prestazioni", high_performance_power),
        "4": ("Mostra processi pesanti", top_processes),
        "5": ("Tweak gaming (Game Mode/GPU)", gaming_tweaks),
        "6": ("Pulizia disco Windows", disk_cleanup),
        "7": ("Rileva hardware/salute e invia al cloud", send_all),
        "8": ("Ripristina impostazioni (backup)", restore_tweaks),
        "A": ("Esegui ottimizzazioni (1-3,5,6)", None),
    }
    print("=" * 54)
    print("   BOOST PC AI - Desktop Agent")
    print("=" * 54)
    if not is_admin():
        print("[!] Suggerito eseguire come Amministratore.")
    for k, (label, _) in actions.items():
        print(f"  {k}. {label}")
    print("  Q. Esci")
    choice = input("\nScegli un'azione: ").strip().upper()
    if choice == "Q":
        sys.exit(0)
    if choice == "A":
        for k in ["1", "2", "3", "5", "6"]:
            actions[k][1]()
    elif choice in actions and actions[choice][1]:
        actions[choice][1]()
    else:
        print("Scelta non valida.")
    input("\nPremi INVIO per continuare...")


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Questo agent e' progettato per Windows.")
        sys.exit(1)
    while True:
        os.system("cls")
        menu()
'''
