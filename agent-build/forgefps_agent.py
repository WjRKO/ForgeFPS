#!/usr/bin/env python3
"""
FrameForge - Desktop Agent (Windows)
Companion locale: ottimizzazioni REALI reversibili + benchmark prima/dopo +
rilevamento hardware/salute per consigli AI su misura.
Uso:  python boostpc_agent.py   (consigliato come Amministratore)
"""
import os
import sys
import json
import time
import shutil
import socket
import subprocess
import tempfile
import ctypes
import re
import argparse
import urllib.request

_parser = argparse.ArgumentParser(description="FrameForge Desktop Agent")
_parser.add_argument("--token", default=os.environ.get("FORGEFPS_TOKEN", "__AGENT_TOKEN__"))
_parser.add_argument("--backend", default=os.environ.get("FORGEFPS_BACKEND", "https://forgefps.dev"))
_parser.add_argument("--mode", default="optimize")
_args, _ = _parser.parse_known_args()

BACKEND_URL = _args.backend
AGENT_TOKEN = _args.token
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boostpc_backup.json")

if not AGENT_TOKEN or AGENT_TOKEN.startswith("__"):
    print("=" * 50)
    print("  FrameForge Desktop Agent")
    print("=" * 50)
    print("Incolla il tuo token (pagina 'Collega il PC' del tuo account) e premi INVIO.")
    print("Paste your token (from the 'Connect PC' page) and press ENTER.")
    try:
        AGENT_TOKEN = input("Token > ").strip()
    except Exception:
        AGENT_TOKEN = ""
    if not AGENT_TOKEN:
        print("Nessun token inserito. / No token provided.")
        try:
            input("Premi INVIO per chiudere... / Press ENTER to close...")
        except Exception:
            pass
        sys.exit(1)


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


# ---------------- Backup / registry helpers ----------------
def _load_backup():
    if os.path.exists(BACKUP_FILE):
        try:
            return json.load(open(BACKUP_FILE))
        except Exception:
            return {}
    return {}


def _save_backup(bk):
    json.dump(bk, open(BACKUP_FILE, "w"), indent=2)


def _reg_cli_path(path):
    return path.replace("HKCU:", "HKCU").replace("HKLM:", "HKLM").replace(":", "")


def reg_get(path, name):
    v = ps("(Get-ItemProperty -Path '%s' -Name '%s' -ErrorAction SilentlyContinue).'%s'"
           % (path, name, name))
    return v if v != "" else None


def set_reg(bk, path, name, rtype, value):
    key = "%s::%s" % (path, name)
    if key not in bk:
        old = reg_get(path, name)
        bk[key] = "__ABSENT__" if old is None else "%s|%s" % (rtype, old)
    t = "REG_DWORD" if rtype == "DWord" else "REG_SZ"
    run('reg add "%s" /v "%s" /t %s /d "%s" /f' % (_reg_cli_path(path), name, t, value))


# ---------------- Detection ----------------
def collect_specs():
    s = {}
    s["os"] = _clean(ps("(Get-CimInstance Win32_OperatingSystem).Caption"))
    s["os_build"] = _clean(ps("(Get-CimInstance Win32_OperatingSystem).BuildNumber"))
    ct = ps("(Get-CimInstance Win32_SystemEnclosure).ChassisTypes -join ','")
    s["form_factor"] = "Laptop" if any(x in (ct or "") for x in ["8", "9", "10", "14", "30", "31", "32"]) else "Desktop"
    s["cpu"] = _clean(ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"))
    s["cpu_cores"] = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfCores")
    s["cpu_threads"] = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfLogicalProcessors")
    s["cpu_clock_ghz"] = ps("[math]::round((Get-CimInstance Win32_Processor | Select-Object -First 1).MaxClockSpeed/1000,2)")
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
    ram_total = ps("[math]::round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,0)")
    s["ram"] = f"{ram_total} GB" if ram_total else ""
    s["ram_speed_mhz"] = ps("(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).Speed")
    s["ram_modules"] = ps("(Get-CimInstance Win32_PhysicalMemory | Measure-Object).Count")
    smt = ps("(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).SMBIOSMemoryType")
    s["ram_type"] = {"20": "DDR", "21": "DDR2", "24": "DDR3", "26": "DDR4", "34": "DDR5"}.get((smt or "").strip(), "")
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
    socket_v = _clean(ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).SocketDesignation"))
    chip_m = re.search(r"\b([XZBHA]\d{3}E?)\b", s.get("motherboard", ""), re.IGNORECASE)
    chipset = chip_m.group(1).upper() if chip_m else ""
    s["chipset"] = chipset
    if not re.search(r"AM\d|LGA|sTR|sWRX|SP\d|FM\d|TR4", socket_v, re.IGNORECASE):
        cs = chipset.upper()
        if cs in ("X570", "B550", "A520", "X470", "B450", "X370", "B350", "A320"):
            socket_v = "AM4"
        elif cs in ("X670E", "X670", "B650E", "B650", "A620"):
            socket_v = "AM5"
        elif cs in ("Z790", "B760", "H770", "H610", "Z690", "B660", "H670"):
            socket_v = "LGA1700"
        elif cs in ("Z590", "B560", "H570", "H510", "Z490", "B460", "H470", "H410"):
            socket_v = "LGA1200"
    s["cpu_socket"] = socket_v
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


# ---------------- Benchmark ----------------
def _ping_ms():
    times = []
    for _ in range(4):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            t = time.perf_counter()
            s.connect(("1.1.1.1", 443))
            times.append((time.perf_counter() - t) * 1000)
            s.close()
        except Exception:
            pass
    return int(round(sum(times) / len(times))) if times else 0


def run_benchmark():
    print("    Benchmark in corso (CPU / RAM / Disco / Rete)...")
    r = {}
    t = time.perf_counter()
    acc = 0.0
    for i in range(3000000):
        acc += i ** 0.5
    el = max(time.perf_counter() - t, 0.001)
    r["cpu_score"] = int(round(3000000 / el / 1000))

    size = 64 * 1024 * 1024
    buf = bytearray(size)
    dst = bytearray(size)
    t = time.perf_counter()
    for _ in range(5):
        dst[:] = buf
    el = max(time.perf_counter() - t, 0.001)
    r["ram_mbps"] = int(round((5 * size / (1024 * 1024)) / el))

    tmp = os.path.join(tempfile.gettempdir(), "boostpc_bench.bin")
    data = os.urandom(64 * 1024 * 1024)
    t = time.perf_counter()
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    el = max(time.perf_counter() - t, 0.001)
    r["disk_write_mbps"] = int(round(64 / el))
    t = time.perf_counter()
    with open(tmp, "rb") as f:
        f.read()
    el = max(time.perf_counter() - t, 0.001)
    r["disk_read_mbps"] = int(round(64 / el))
    try:
        os.remove(tmp)
    except Exception:
        pass

    r["ping_ms"] = _ping_ms()
    try:
        fr = ps("$o=Get-CimInstance Win32_OperatingSystem; "
                "[math]::round($o.FreePhysicalMemory/$o.TotalVisibleMemorySize*100,0)")
        r["free_ram_pct"] = int(fr)
    except Exception:
        r["free_ram_pct"] = 0
    r["overall"] = int(round(r["cpu_score"] + r["ram_mbps"] / 50.0 + r["disk_write_mbps"] / 50.0 +
                             r["disk_read_mbps"] / 50.0 + max(0, 120 - r["ping_ms"]) + r["free_ram_pct"]))
    return r


def show_bench(r, title):
    print(f"\n    [{title}]")
    print(f"    CPU score      : {r['cpu_score']}")
    print(f"    RAM bandwidth  : {r['ram_mbps']} MB/s")
    print(f"    Disco scrittura: {r['disk_write_mbps']} MB/s")
    print(f"    Disco lettura  : {r['disk_read_mbps']} MB/s")
    print(f"    Ping (1.1.1.1) : {r['ping_ms']} ms")
    print(f"    RAM libera     : {r['free_ram_pct']} %")
    print(f"    PUNTEGGIO      : {r['overall']}")


def show_compare(b, a):
    print("\n=== CONFRONTO PRIMA / DOPO ===")
    rows = [("CPU score", b["cpu_score"], a["cpu_score"], True),
            ("RAM MB/s", b["ram_mbps"], a["ram_mbps"], True),
            ("Disco scritt.", b["disk_write_mbps"], a["disk_write_mbps"], True),
            ("Disco lett.", b["disk_read_mbps"], a["disk_read_mbps"], True),
            ("Ping ms", b["ping_ms"], a["ping_ms"], False),
            ("RAM libera %", b["free_ram_pct"], a["free_ram_pct"], True),
            ("PUNTEGGIO", b["overall"], a["overall"], True)]
    print(f"    {'METRICA':<14}{'PRIMA':>10}{'DOPO':>10}{'VAR':>9}")
    for name, bv, av, hb in rows:
        delta = round((av - bv) / bv * 100) if bv else 0
        sign = "+" if delta >= 0 else ""
        print(f"    {name:<14}{bv:>10}{av:>10}{sign}{delta:>7}%")


# ---------------- Reporting ----------------
def _post(payload):
    if "__AGENT" in AGENT_TOKEN or not BACKEND_URL.startswith("http"):
        print("\n[!] Token non configurato. Riscarica l'agent dal tuo account FrameForge.")
        return False
    req = urllib.request.Request(f"{BACKEND_URL}/api/agent/report-specs",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "X-Agent-Token": AGENT_TOKEN}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print(f"\n[!] Invio fallito: {e}")
        return False


def send_all():
    print("\n[*] Rilevamento hardware, salute e programmi all'avvio...")
    specs = collect_specs()
    health = collect_health()
    startup = collect_startup()
    for k, v in specs.items():
        print(f"    {k.upper():12}: {v or 'n/d'}")
    if _post({"data": specs, "health": health, "startup": startup}):
        print("\n[OK] Dati inviati! Apri FrameForge -> Il mio PC / Upgrade per analisi e consigli.")


def send_benchmark(rec):
    if _post({"benchmark": rec}):
        print("\n[OK] Benchmark inviato! Vedi il confronto in FrameForge -> Il mio PC.")


def benchmark_only():
    print("\n[B] Benchmark del sistema...")
    bench = run_benchmark()
    show_bench(bench, "BENCHMARK")
    send_benchmark({"after": bench, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})


# ---------------- Tweaks (deep, reversible) ----------------
def _cleanup():
    print("\n[1] Pulizia file temporanei + cache Windows Update...")
    for t in [tempfile.gettempdir(), os.path.expandvars(r"%SystemRoot%\\Temp"),
              os.path.expandvars(r"%LOCALAPPDATA%\\Temp")]:
        if not os.path.isdir(t):
            continue
        for name in os.listdir(t):
            path = os.path.join(t, name)
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
    run("net stop wuauserv")
    wu = os.path.expandvars(r"%SystemRoot%\\SoftwareDistribution\\Download")
    if os.path.isdir(wu):
        shutil.rmtree(wu, ignore_errors=True)
    run("net start wuauserv")
    run("ipconfig /flushdns")
    print("    File temporanei, cache Windows Update e DNS puliti.")


def apply_all_tweaks():
    bk = _load_backup()
    print("\n[*] Applico ottimizzazioni profonde (con backup)...")
    _cleanup()

    cur = ps("(powercfg /getactivescheme)")
    m = re.search(r"([0-9a-fA-F-]{36})", cur or "")
    if m and "power_plan" not in bk:
        bk["power_plan"] = m.group(1)
    ultimate = "e9a42b02-d5df-448d-aa00-03f14749eb61"
    run(f"powercfg -duplicatescheme {ultimate}")
    if "0x0" not in (run(f"powercfg -setactive {ultimate}") or "").lower():
        pass
    run("powercfg -setactive e9a42b02-d5df-448d-aa00-03f14749eb61")
    print("    Piano energetico: prestazioni massime.")

    set_reg(bk, r"HKCU:\Software\Microsoft\GameBar", "AllowAutoGameMode", "DWord", 1)
    set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", "DWord", 2)
    set_reg(bk, r"HKCU:\System\GameConfigStore", "GameDVR_Enabled", "DWord", 0)
    set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", "DWord", 0)
    print("    Game Mode + GPU Scheduling attivi, Game DVR disattivato.")

    sp = r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    set_reg(bk, sp, "SystemResponsiveness", "DWord", 0)
    set_reg(bk, sp, "NetworkThrottlingIndex", "DWord", 4294967295)
    games = sp + r"\Tasks\Games"
    set_reg(bk, games, "GPU Priority", "DWord", 8)
    set_reg(bk, games, "Priority", "DWord", 6)
    set_reg(bk, games, "Scheduling Category", "String", "High")
    set_reg(bk, games, "SFIO Priority", "String", "High")
    set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", "DWord", 26)
    print("    Priorita GPU/CPU per i giochi + network throttling off.")

    set_reg(bk, r"HKCU:\Control Panel\Mouse", "MouseSpeed", "String", "0")
    set_reg(bk, r"HKCU:\Control Panel\Mouse", "MouseThreshold1", "String", "0")
    set_reg(bk, r"HKCU:\Control Panel\Mouse", "MouseThreshold2", "String", "0")
    print("    Accelerazione mouse disattivata (mira piu precisa).")

    set_reg(bk, r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
            "VisualFXSetting", "DWord", 2)
    print("    Effetti visivi: modalita prestazioni.")

    ifaces = ps("Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces' | "
                "Select-Object -ExpandProperty PSChildName")
    for guid in [l.strip() for l in (ifaces or "").splitlines() if l.strip()]:
        p = r"HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\%s" % guid
        set_reg(bk, p, "TcpAckFrequency", "DWord", 1)
        set_reg(bk, p, "TCPNoDelay", "DWord", 1)
    run("netsh int tcp set global autotuninglevel=normal")
    run("netsh int tcp set global ecncapability=enabled")
    run("netsh int tcp set global rss=enabled")
    print("    Nagle disattivato + TCP ottimizzato (meno latenza online).")

    alias = _clean(ps("$a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; $a.Name"))
    if alias and ("dns::" + alias) not in bk:
        bk["dns::" + alias] = "reset"
        ps("Set-DnsClientServerAddress -InterfaceAlias '%s' -ServerAddresses ('1.1.1.1','1.0.0.1')" % alias)
        print(f"    DNS impostati su Cloudflare (1.1.1.1) su '{alias}'.")

    st = _clean(ps("(Get-Service DiagTrack -ErrorAction SilentlyContinue).StartType"))
    if st and "svc::DiagTrack" not in bk:
        bk["svc::DiagTrack"] = st
        run("net stop DiagTrack")
        run("sc config DiagTrack start= disabled")
        print("    Telemetria (DiagTrack) disattivata.")

    cdm = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    set_reg(bk, cdm, "SilentInstalledAppsEnabled", "DWord", 0)
    set_reg(bk, cdm, "SystemPaneSuggestionsEnabled", "DWord", 0)
    set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent",
            "DisableWindowsConsumerFeatures", "DWord", 1)
    print("    Suggerimenti/ads di Windows disattivati.")

    bloat = ["Microsoft.549981C3F5F10", "Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.GetHelp",
             "Microsoft.Getstarted", "Microsoft.WindowsFeedbackHub", "Microsoft.MicrosoftSolitaireCollection",
             "Microsoft.People", "Microsoft.WindowsMaps", "Microsoft.3DBuilder", "Microsoft.MixedReality.Portal",
             "king.com.CandyCrushSaga", "Microsoft.SkypeApp"]
    removed = 0
    for pkg in bloat:
        out = ps("$a=Get-AppxPackage -Name %s -ErrorAction SilentlyContinue; "
                 "if($a){ $a | Remove-AppxPackage -ErrorAction SilentlyContinue; 'ok' }" % pkg)
        if out.strip() == "ok":
            removed += 1
    print(f"    Debloat: rimosse {removed} app superflue (reinstallabili dallo Store).")

    _save_backup(bk)
    print("\n    Ottimizzazioni applicate. Riavvio consigliato. Per annullare: opzione 8 (Ripristina).")


def optimize_with_benchmark():
    if not is_admin():
        print("\n[!] Esegui come Amministratore per applicare le ottimizzazioni.")
        return
    before = run_benchmark()
    show_bench(before, "PRIMA")
    apply_all_tweaks()
    print("\n[*] Benchmark post-ottimizzazione...")
    after = run_benchmark()
    show_bench(after, "DOPO")
    show_compare(before, after)
    send_benchmark({"before": before, "after": after, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})


def restore_tweaks():
    print("\n[8] Ripristino impostazioni dal backup...")
    if not os.path.exists(BACKUP_FILE):
        print("    Nessun backup trovato.")
        return
    bk = _load_backup()
    if bk.get("power_plan"):
        run("powercfg -setactive %s" % bk["power_plan"])
    for k, v in bk.items():
        if k == "power_plan":
            continue
        if k.startswith("svc::"):
            name = k[5:]
            mode = "auto" if str(v).lower().startswith("auto") else ("disabled" if str(v).lower() == "disabled" else "demand")
            run("sc config %s start= %s" % (name, mode))
            if mode != "disabled":
                run("net start %s" % name)
            continue
        if k.startswith("dns::"):
            ps("Set-DnsClientServerAddress -InterfaceAlias '%s' -ResetServerAddresses" % k[5:])
            continue
        path, _, name = k.partition("::")
        cli = _reg_cli_path(path)
        if v == "__ABSENT__":
            run('reg delete "%s" /v "%s" /f' % (cli, name))
        else:
            tp, _, vv = v.partition("|")
            t = "REG_DWORD" if tp == "DWord" else "REG_SZ"
            run('reg add "%s" /v "%s" /t %s /d "%s" /f' % (cli, name, t, vv))
    run("netsh int tcp set global autotuninglevel=normal")
    try:
        os.remove(BACKUP_FILE)
    except Exception:
        pass
    print("    Impostazioni ripristinate ai valori precedenti.")


def high_performance_power():
    print("\n[3] Piano energetico ad alte prestazioni...")
    bk = _load_backup()
    cur = ps("(powercfg /getactivescheme)")
    m = re.search(r"([0-9a-fA-F-]{36})", cur or "")
    if m and "power_plan" not in bk:
        bk["power_plan"] = m.group(1)
        _save_backup(bk)
    run("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
    print("    Attivato 'High Performance' (backup salvato).")


def top_processes():
    print("\n[4] Processi che consumano piu' RAM:")
    print(ps("Get-Process | Sort-Object WS -Descending | Select-Object -First 8 "
             "Name,@{N='RAM_MB';E={[math]::round($_.WS/1MB,1)}} | Format-Table -AutoSize | Out-String") or "    n/d")


def menu():
    actions = {
        "1": ("Pulizia temp + cache Windows Update", _cleanup),
        "3": ("Piano energetico alte prestazioni", high_performance_power),
        "4": ("Mostra processi pesanti", top_processes),
        "7": ("Rileva hardware/salute e invia al cloud", send_all),
        "8": ("Ripristina impostazioni (backup)", restore_tweaks),
        "B": ("Benchmark del sistema", benchmark_only),
        "A": ("OTTIMIZZA TUTTO + benchmark prima/dopo", optimize_with_benchmark),
    }
    print("=" * 54)
    print("   FrameForge - Desktop Agent")
    print("=" * 54)
    if not is_admin():
        print("[!] Suggerito eseguire come Amministratore.")
    for k in ["1", "3", "4", "7", "8", "B", "A"]:
        print(f"  {k}. {actions[k][0]}")
    print("  Q. Esci")
    choice = input("\nScegli un'azione: ").strip().upper()
    if choice == "Q":
        sys.exit(0)
    if choice in actions:
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
