#!/usr/bin/env python3
"""
FrameForge Agent (Windows)
Agent locale: ottimizzazioni REALI reversibili + benchmark prima/dopo +
rilevamento hardware/salute per consigli AI su misura.
Uso:  python forgefps_agent.py   (consigliato come Amministratore)
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
import hmac
import hashlib
import argparse
import urllib.parse
import urllib.request

_parser = argparse.ArgumentParser(description="FrameForge Agent")
_parser.add_argument("--token", default=os.environ.get("FORGEFPS_TOKEN", "__AGENT_TOKEN__"))
_parser.add_argument("--backend", default=os.environ.get("FORGEFPS_BACKEND", "https://forgefps.dev"))
_parser.add_argument("--mode", default="optimize")
_parser.add_argument("--uri", default="", help="URI custom-protocol firmato (frameforge://launch?...)")
_parser.add_argument("--register-protocol", action="store_true",
                     help="Registra frameforge:// nel registro utente e esce (idempotente)")
_args, _ = _parser.parse_known_args()

BACKEND_URL = _args.backend
AGENT_TOKEN = _args.token
AGENT_VERSION = "0.7.3"
# v0.7.3+: rinominato da boostpc_backup.json → forgefps_backup.json.
# Fallback lettura del vecchio nome per una release per non perdere il backup
# degli utenti che aggiornano dalla v0.7.2 o precedenti.
_BACKUP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_FILE = os.path.join(_BACKUP_DIR, "forgefps_backup.json")
_LEGACY_BACKUP_FILE = os.path.join(_BACKUP_DIR, "boostpc_backup.json")

# Persistent token storage in %APPDATA%\FrameForge\token.dat (v0.6.8+).
# Se l'utente non passa --token via CLI, provo a leggerlo da disco. Se non c'e',
# lo chiedo una volta e lo salvo. Cosi dal secondo doppio-click in poi la GUI
# parte senza prompt (Steam/Discord-like UX).
def _token_store_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "FrameForge", "token.dat")


def _load_saved_token() -> str:
    try:
        p = _token_store_path()
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                t = fh.read().strip()
            if t and not t.startswith("__"):
                return t
    except Exception:
        pass
    return ""


def _save_token(token: str) -> None:
    try:
        p = _token_store_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(token)
        # NTFS: %APPDATA% e' gia' per-utente, non serve chmod.
    except Exception:
        pass


def _forget_saved_token() -> None:
    try:
        p = _token_store_path()
        if os.path.exists(p):
            os.unlink(p)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Custom URL protocol: frameforge://
# Registrato in HKCU (no admin), permette al browser di lanciare l'agent con
# parametri firmati HMAC. La chiave HMAC e' il token stesso dell'utente, gia'
# salvato in %APPDATA%\FrameForge\token.dat: il server firma con lo stesso
# token, quindi la verifica avviene offline senza mai esporre segreti.
# ---------------------------------------------------------------------------
_PROTOCOL = "frameforge"
_URI_MAX_AGE_SEC = 60


def _agent_exe_path() -> str:
    """Percorso dell'exe attualmente in esecuzione (o dello script .py in dev)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def register_frameforge_protocol(silent: bool = True) -> bool:
    """Registra frameforge:// come URL Protocol per l'utente corrente (HKCU).
    Idempotente: se gia' registrato con lo stesso path non fa nulla. Ritorna True se ok.

    v0.7.1+: include --backend nel command cosi' la registrazione preserva
    l'ambiente da cui l'utente ha scaricato lo ZIP (preview vs produzione).
    Senza questo, i bottoni silent lanciati dalla web preview userebbero
    BACKEND_URL=default (forgefps.dev), disallineando il flusso di sync.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg  # type: ignore
    except Exception:
        if not silent:
            print("[WARN] winreg non disponibile su questa piattaforma.")
        return False
    exe = _agent_exe_path()
    # "%1" contiene l'URI completo passato dal browser. Includiamo anche
    # --backend per preservare l'ambiente attivo (preview / produzione).
    command = f'"{exe}" --backend "{BACKEND_URL}" --uri "%1"'
    root = winreg.HKEY_CURRENT_USER
    base = r"Software\Classes\%s" % _PROTOCOL
    try:
        # Cerca se e' gia' registrato con lo stesso command → skip
        try:
            k = winreg.OpenKey(root, base + r"\shell\open\command", 0, winreg.KEY_READ)
            existing, _ = winreg.QueryValueEx(k, None)
            winreg.CloseKey(k)
            if existing == command:
                return True
        except OSError:
            pass
        # Scrivi/aggiorna
        with winreg.CreateKey(root, base) as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "URL:FrameForge Protocol")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(root, base + r"\DefaultIcon") as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, f'"{exe}",0')
        with winreg.CreateKey(root, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, command)
        if not silent:
            print(f"[ OK ] Protocollo {_PROTOCOL}:// registrato -> {exe} (backend={BACKEND_URL})")
        return True
    except Exception as e:
        if not silent:
            print(f"[ERR ] Impossibile registrare protocollo: {e}")
        return False


def parse_and_verify_uri(uri: str, agent_token: str):
    """Parsa un URI 'frameforge://launch?mode=...&silent=...&ts=...&sig=...' e
    verifica la firma HMAC-SHA256 usando agent_token come chiave. Ritorna dict
    con 'mode' e 'silent' oppure None.

    Note su retrocompat: la firma copre solo 'mode|ts' (per compat con v0.7.0).
    Il flag 'silent' viaggia come hint UX ma non e' autenticato. Manomettere
    silent puo' solo cambiare UX (GUI vs headless), non e' security-critical.
    """
    if not uri or not uri.lower().startswith(f"{_PROTOCOL}://"):
        return None
    try:
        p = urllib.parse.urlparse(uri)
        qs = urllib.parse.parse_qs(p.query or "")
        mode = (qs.get("mode") or [""])[0]
        ts_str = (qs.get("ts") or [""])[0]
        sig = (qs.get("sig") or [""])[0]
        silent = (qs.get("silent") or ["0"])[0] in ("1", "true", "yes")
        if not mode or not ts_str or not sig:
            return None
        ts = int(ts_str)
        # Anti-replay: URI valido per 60s (permette anche piccolo clock skew)
        now = int(time.time())
        if abs(now - ts) > _URI_MAX_AGE_SEC:
            print(f"[WARN] URI scaduto (age={now - ts}s). Riprova dal browser.")
            return None
        expected = hmac.new(
            agent_token.encode("utf-8"),
            f"{mode}|{ts}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            print("[WARN] Firma URI non valida. Ignoro (possibile URI di un altro account).")
            return None
        return {"mode": mode, "ts": ts, "silent": silent}
    except Exception as e:
        print(f"[ERR ] Errore parsing URI: {e}")
        return None


if not AGENT_TOKEN or AGENT_TOKEN.startswith("__"):
    saved = _load_saved_token()
    if saved:
        AGENT_TOKEN = saved
        print("[INFO] Token caricato da %APPDATA%\\FrameForge\\token.dat")
    else:
        # --register-protocol e' un'operazione stand-alone: non serve token per
        # scrivere nel registro utente. Salta il prompt e vai al main.
        if _args.register_protocol:
            AGENT_TOKEN = ""  # placeholder, verra' ignorato
        # Se stiamo per gestire un URI ma non c'e' un token salvato, non possiamo
        # verificare la firma: guida l'utente al primo setup.
        elif _args.uri:
            print("[WARN] Nessun token salvato: prima apri l'app dalla dashboard")
            print("       (scarica lo ZIP da 'FrameForge Agent'), poi il bottone")
            print("       'Avvia' funzionera' senza download.")
            try:
                input("Premi INVIO per chiudere...")
            except Exception:
                pass
            sys.exit(1)
        else:
            print("=" * 54)
            print("  FrameForge Agent")
            print("=" * 54)
            print("Incolla il tuo token (pagina 'FrameForge Agent' del tuo account) e premi INVIO.")
            print("Paste your token (from the 'FrameForge Agent' page) and press ENTER.")
            print("Il token verra' salvato in %APPDATA%\\FrameForge\\ per i prossimi avvii.")
            try:
                AGENT_TOKEN = input("Token > ").strip()
            except Exception:
                AGENT_TOKEN = ""
            if not AGENT_TOKEN:
                print("[ERR ] Nessun token inserito. / No token provided.")
                try:
                    input("Premi INVIO per chiudere... / Press ENTER to close...")
                except Exception:
                    pass
                sys.exit(1)
            _save_token(AGENT_TOKEN)
elif AGENT_TOKEN and not AGENT_TOKEN.startswith("__"):
    # Token fornito da CLI (es. lancio via .bat generato): salvalo se differisce
    # da quello persistito, cosi anche il doppio-click diretto sull'.exe funziona.
    if _load_saved_token() != AGENT_TOKEN:
        _save_token(AGENT_TOKEN)

# Se l'utente ha lanciato con --uri "frameforge://...", verifica la firma e
# imposta la mode: la GUI si aprira' direttamente sull'azione richiesta.
# v0.7.1+: se silent=1 -> lancia PowerShell hidden senza aprire la GUI.
_SILENT_FROM_URI = False
if _args.uri:
    payload = parse_and_verify_uri(_args.uri, AGENT_TOKEN)
    if payload:
        _args.mode = payload["mode"]
        _SILENT_FROM_URI = bool(payload.get("silent"))
        # Se la mode e' 'gui' o 'optimize' apriamo direttamente la finestra sicura
        if _args.mode in ("gui", "optimize") and not _SILENT_FROM_URI:
            _args.mode = "securegui"
    else:
        # URI non valido -> apri la GUI normale in modalita' securegui
        _args.mode = "securegui"


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
    # v0.7.3+: fallback lettura vecchio nome per un upgrade indolore.
    path = BACKUP_FILE if os.path.exists(BACKUP_FILE) else (
        _LEGACY_BACKUP_FILE if os.path.exists(_LEGACY_BACKUP_FILE) else None
    )
    if path:
        try:
            return json.load(open(path))
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
    print("[STEP] Benchmark in corso (CPU / RAM / Disco / DPC / Rete)...")
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

    tmp = os.path.join(tempfile.gettempdir(), "forgefps_bench.bin")
    chunk = os.urandom(8 * 1024 * 1024)
    t = time.perf_counter()
    with open(tmp, "wb") as f:
        for _ in range(32):
            f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
    el = max(time.perf_counter() - t, 0.001)
    r["disk_write_mbps"] = int(round(256 / el))
    t = time.perf_counter()
    with open(tmp, "rb") as f:
        f.read()
    el = max(time.perf_counter() - t, 0.001)
    r["disk_read_mbps"] = int(round(256 / el))
    try:
        import random as _rnd
        b4 = b"\0" * 4096
        ops = 200
        t = time.perf_counter()
        with open(tmp, "r+b") as f:
            for _ in range(ops):
                f.seek(4096 * _rnd.randint(0, 65535))
                f.write(b4)
                f.flush()
                os.fsync(f.fileno())
        el = max(time.perf_counter() - t, 0.001)
        r["iops_4k"] = int(round(ops / el))
    except Exception:
        r["iops_4k"] = 0
    try:
        os.remove(tmp)
    except Exception:
        pass

    lat = []
    prev = time.perf_counter()
    for _ in range(150):
        time.sleep(0.001)
        now = time.perf_counter()
        lat.append(max(0.0, (now - prev) * 1000 - 1))
        prev = now
    lat.sort()
    r["dpc_ms"] = round(lat[int(len(lat) * 0.95)], 1)

    times = []
    for _ in range(10):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            t = time.perf_counter()
            s.connect(("1.1.1.1", 443))
            times.append((time.perf_counter() - t) * 1000)
            s.close()
        except Exception:
            pass
    if times:
        avg = sum(times) / len(times)
        r["ping_ms"] = int(round(avg))
        r["jitter_ms"] = round((sum((x - avg) ** 2 for x in times) / len(times)) ** 0.5, 1)
    else:
        r["ping_ms"] = 0
        r["jitter_ms"] = 0

    try:
        bt = ps("$ev=Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational';Id=100} "
                "-MaxEvents 1 -ErrorAction SilentlyContinue; if($ev){ $x=[xml]$ev.ToXml(); "
                "($x.Event.EventData.Data | Where-Object {$_.Name -eq 'BootTime'}).'#text' }")
        if bt and bt.strip().isdigit():
            r["boot_s"] = round(int(bt.strip()) / 1000, 1)
    except Exception:
        pass

    try:
        fr = ps("$o=Get-CimInstance Win32_OperatingSystem; "
                "[math]::round($o.FreePhysicalMemory/$o.TotalVisibleMemorySize*100,0)")
        r["free_ram_pct"] = int(fr)
    except Exception:
        r["free_ram_pct"] = 0

    cpu_n = min(100, r["cpu_score"] / 100.0)
    ram_n = min(100, r["ram_mbps"] / 200.0)
    dw_n = min(100, r["disk_write_mbps"] / 20.0)
    dr_n = min(100, r["disk_read_mbps"] / 30.0)
    io_n = min(100, r["iops_4k"] / 50.0)
    dpc_n = max(0, 100 - r["dpc_ms"] * 20)
    ping_n = max(0, 100 - r["ping_ms"])
    jit_n = max(0, 100 - r["jitter_ms"] * 10)
    r["score"] = int(round(cpu_n * 0.20 + ram_n * 0.10 + dw_n * 0.15 + dr_n * 0.10 +
                           io_n * 0.10 + dpc_n * 0.15 + ping_n * 0.15 + jit_n * 0.05))
    r["overall"] = int(round(r["cpu_score"] + r["ram_mbps"] / 50.0 + r["disk_write_mbps"] / 50.0 +
                             r["disk_read_mbps"] / 50.0 + max(0, 120 - r["ping_ms"]) + r["free_ram_pct"]))
    return r


def show_bench(r, title):
    print(f"\n    [{title}]")
    print(f"    CPU score        : {r['cpu_score']}")
    print(f"    RAM bandwidth    : {r['ram_mbps']} MB/s")
    print(f"    Disco scrittura  : {r['disk_write_mbps']} MB/s (reale, no cache)")
    print(f"    Disco lettura    : {r['disk_read_mbps']} MB/s")
    print(f"    Disco 4K         : {r.get('iops_4k', 0)} IOPS")
    print(f"    Latenza DPC      : {r.get('dpc_ms', 0)} ms (p95)")
    print(f"    Ping (1.1.1.1)   : {r['ping_ms']} ms (jitter {r.get('jitter_ms', 0)} ms)")
    if r.get("boot_s"):
        print(f"    Avvio Windows    : {r['boot_s']} s")
    print(f"    RAM libera       : {r['free_ram_pct']} %")
    print(f"    PERFORMANCE SCORE: {r.get('score', 0)}/100")
    print("    [INFO] Il Performance Score misura la velocita del PC ora.")
    print("           L'Health Score globale (temp + tweak + freschezza) e su")
    print("           forgefps.dev -> Il mio PC.")


def show_compare(b, a):
    print("\n=== CONFRONTO PRIMA / DOPO ===")
    rows = [("CPU score", b["cpu_score"], a["cpu_score"], True),
            ("RAM MB/s", b["ram_mbps"], a["ram_mbps"], True),
            ("Disco scritt.", b["disk_write_mbps"], a["disk_write_mbps"], True),
            ("Disco lett.", b["disk_read_mbps"], a["disk_read_mbps"], True),
            ("Disco 4K IOPS", b.get("iops_4k", 0), a.get("iops_4k", 0), True),
            ("DPC ms", b.get("dpc_ms", 0), a.get("dpc_ms", 0), False),
            ("Ping ms", b["ping_ms"], a["ping_ms"], False),
            ("Jitter ms", b.get("jitter_ms", 0), a.get("jitter_ms", 0), False),
            ("RAM libera %", b["free_ram_pct"], a["free_ram_pct"], True),
            ("PERF SCORE /100", b.get("score", 0), a.get("score", 0), True)]
    print(f"    {'METRICA':<16}{'PRIMA':>10}{'DOPO':>10}{'VAR':>9}")
    for name, bv, av, hb in rows:
        delta = round((av - bv) / bv * 100) if bv else 0
        sign = "+" if delta >= 0 else ""
        print(f"    {name:<16}{bv:>10}{av:>10}{sign}{delta:>7}%")


# ---------------- Reporting ----------------
def _post(payload):
    if "__AGENT" in AGENT_TOKEN or not BACKEND_URL.startswith("http"):
        print("\n[ERR ] Token non configurato. Riscarica l'agent dal tuo account FrameForge.")
        return False
    req = urllib.request.Request(f"{BACKEND_URL}/api/agent/report-specs",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "X-Agent-Token": AGENT_TOKEN}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print(f"\n[ERR ] Invio fallito: {e}")
        return False


def send_all():
    print("\n[STEP] Rilevamento hardware, salute e programmi all'avvio...")
    specs = collect_specs()
    health = collect_health()
    startup = collect_startup()
    for k, v in specs.items():
        print(f"       {k.upper():12}: {v or 'n/d'}")
    if _post({"data": specs, "health": health, "startup": startup}):
        print("\n[ OK ] Dati inviati! Apri FrameForge -> Il mio PC per analisi e consigli.")


def send_benchmark(rec):
    if _post({"benchmark": rec}):
        print("\n[ OK ] Benchmark inviato! Vedi il confronto in FrameForge -> Il mio PC.")


def benchmark_only():
    print("\n[STEP] Benchmark del sistema...")
    bench = run_benchmark()
    show_bench(bench, "BENCHMARK")
    send_benchmark({"after": bench, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})


# ---------------- Tweaks (deep, reversible) ----------------
def _cleanup():
    print("\n[STEP] Pulizia file temporanei + cache Windows Update...")
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
    print("[ OK ] File temporanei, cache Windows Update e DNS puliti.")


def apply_all_tweaks():
    bk = _load_backup()
    ct = ps("(Get-CimInstance Win32_SystemEnclosure).ChassisTypes -join ','")
    is_laptop = any(x in (ct or "").split(",") for x in ["8", "9", "10", "14", "30", "31", "32"])
    try:
        ram_gb = int(ps("[math]::round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,0)") or 0)
    except Exception:
        ram_gb = 0
    is_ssd = "SSD" in (ps("(Get-Partition -DriveLetter C -ErrorAction SilentlyContinue | Get-Disk | Get-PhysicalDisk).MediaType") or "")
    print("\n[STEP] Profilo hardware: %s, RAM %d GB, disco %s -> tweak adattati." %
          ("Laptop" if is_laptop else "Desktop", ram_gb, "SSD" if is_ssd else "HDD"))
    print("[STEP] Applico ottimizzazioni profonde (con backup)...")
    _cleanup()

    cur = ps("(powercfg /getactivescheme)")
    m = re.search(r"([0-9a-fA-F-]{36})", cur or "")
    if m and "power_plan" not in bk:
        bk["power_plan"] = m.group(1)
    if is_laptop:
        run("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
        print("    Piano energetico: High Performance (adattivo: laptop, protetta batteria/temperature).")
    else:
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

    gcs = r"HKCU:\System\GameConfigStore"
    set_reg(bk, gcs, "GameDVR_FSEBehaviorMode", "DWord", 2)
    set_reg(bk, gcs, "GameDVR_HonorUserFSEBehaviorMode", "DWord", 1)
    set_reg(bk, gcs, "GameDVR_DXGIHonorFSEWindowsCompatible", "DWord", 1)
    print("    Fullscreen Optimizations disattivate (fullscreen esclusivo reale).")

    set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched", "NonBestEffortLimit", "DWord", 0)
    print("    Banda riservata QoS (20%) rimossa.")

    if not is_laptop:
        set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", "DWord", 1)
        print("    Power throttling CPU disattivato (adattivo: desktop).")

    if ram_gb >= 16:
        set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                "DisablePagingExecutive", "DWord", 1)
        print(f"    Kernel tenuto in RAM (adattivo: {ram_gb} GB rilevati).")

    if is_ssd:
        st_sm = _clean(ps("(Get-Service SysMain -ErrorAction SilentlyContinue).StartType"))
        if st_sm and "svc::SysMain" not in bk:
            bk["svc::SysMain"] = st_sm
            run("net stop SysMain")
            run("sc config SysMain start= disabled")
        run("fsutil behavior set DisableDeleteNotify 0")
        print("    Adattivo SSD: SysMain/Superfetch off + TRIM verificato.")

    set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", "DWord", 0)
    set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", "DWord", 0)
    print("    Edge preload/background disattivato.")

    _save_backup(bk)
    print("\n[ OK ] Ottimizzazioni applicate. Riavvio consigliato. Per annullare: opzione 4 (Ripristina).")


def optimize_with_benchmark():
    if not is_admin():
        print("\n[WARN] Esegui come Amministratore per applicare le ottimizzazioni.")
        return
    before = run_benchmark()
    show_bench(before, "PRIMA")
    apply_all_tweaks()
    print("\n[STEP] Benchmark post-ottimizzazione...")
    after = run_benchmark()
    show_bench(after, "DOPO")
    show_compare(before, after)
    send_benchmark({"before": before, "after": after, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})


def launch_secure_gui():
    """Scarica e avvia la GUI sicura FrameForge: per ogni tweak mostra Problema, Motivo,
    Modifica proposta e Impatto stimato, con pulsante Applica per singolo tweak.
    Backup automatico + Ripristina sempre disponibili. Non tocca MAI Windows Defender / Firewall."""
    url = "%s/api/agent/script?t=%s" % (BACKEND_URL, AGENT_TOKEN)
    dest = os.path.join(tempfile.gettempdir(), "forgefps.ps1")
    print("\n[STEP] Scarico la GUI sicura FrameForge...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FrameForge-Agent"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
    except Exception as e:
        print("[ERR ] Impossibile scaricare lo script: %s" % e)
        return
    args = '-NoProfile -ExecutionPolicy Bypass -File "%s" -Token %s -Mode optimize' % (dest, AGENT_TOKEN)
    try:
        if not is_admin():
            # rilancia PowerShell elevato: la finestra sicura chiedera' conferma UAC
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 1)
        else:
            subprocess.Popen("powershell.exe %s" % args, shell=True)
        print("[ OK ] GUI sicura avviata: segui le istruzioni nella finestra (Problema/Motivo/Impatto per ogni tweak).")
    except Exception as e:
        print("[ERR ] Errore nell'avvio della GUI sicura: %s" % e)


def launch_silent_mode(mode: str) -> bool:
    """v0.7.1+: esegue la mode PowerShell in background senza aprire finestre.
    Usato dai bottoni 'silent' della web dashboard (sync/benchmark ambientali).
    Ritorna True se il processo e' stato lanciato con successo, False altrimenti.

    Nota: il PowerShell script standalone sync/benchmark termina da solo (unlike
    'monitor' che e' un loop infinito). Se qualcuno passasse mode='monitor' in
    silent avremmo un processo orfano - il backend impedisce comunque questa
    combinazione a livello di API (silent + monitor = rifiutato).
    """
    if mode not in ("sync", "benchmark", "cleanup", "optimize"):
        # Whitelist di mode adatte al lancio silent (non-interattive, terminano).
        print(f"[WARN] Mode '{mode}' non supporta il lancio silent. Uso GUI.")
        return False
    url = "%s/api/agent/script?t=%s" % (BACKEND_URL, AGENT_TOKEN)
    dest = os.path.join(tempfile.gettempdir(), "forgefps.ps1")
    print(f"[STEP] Silent {mode}: scarico script...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FrameForge-Agent-Silent"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
    except Exception as e:
        print(f"[ERR ] Impossibile scaricare lo script: {e}")
        return False

    # PowerShell hidden: -WindowStyle Hidden nasconde la finestra, subprocess con
    # CREATE_NO_WINDOW (0x08000000) impedisce anche il flash della console.
    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-WindowStyle", "Hidden",
        "-File", dest,
        "-Token", AGENT_TOKEN,
        "-Mode", mode,
    ]
    try:
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.Popen(
            args,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
        print(f"[ OK ] Silent {mode} avviato in background (PID via Task Manager).")
        return True
    except Exception as e:
        print(f"[ERR ] Errore nel lancio silent: {e}")
        return False


def restore_tweaks():
    print("\n[STEP] Ripristino impostazioni dal backup...")
    if not (os.path.exists(BACKUP_FILE) or os.path.exists(_LEGACY_BACKUP_FILE)):
        print("       Nessun backup trovato.")
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
    for _p in (BACKUP_FILE, _LEGACY_BACKUP_FILE):
        try:
            if os.path.exists(_p):
                os.remove(_p)
        except Exception:
            pass
    print("[ OK ] Impostazioni ripristinate ai valori precedenti.")


def _menu_logout():
    """Rimuove il token dal PC. Esposto anche come pulsante 'Cambia account' nella GUI.
    Utile via CLI power-user: `forgefps-agent.exe --mode logout`.
    """
    _forget_saved_token()
    print("\n[ OK ] Token rimosso. Al prossimo avvio verra' richiesto un nuovo token.")


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Questo agent e' progettato per Windows.")
        sys.exit(1)
    # Registrazione esplicita e uscita (es. installer / repair)
    if _args.register_protocol:
        ok = register_frameforge_protocol(silent=False)
        sys.exit(0 if ok else 1)
    # Registrazione silenziosa best-effort al primo avvio: cosi il bottone
    # "Avvia" della dashboard funziona senza download da qui in avanti.
    try:
        register_frameforge_protocol(silent=True)
    except Exception:
        pass
    # v0.7.1+: se URI includeva silent=1 -> esegui in background e esci subito.
    # Nessuna finestra visibile all'utente. Per sync/benchmark ambientali dal web.
    if _SILENT_FROM_URI:
        ok = launch_silent_mode(_args.mode if _args.mode not in ("securegui", "gui") else "sync")
        # Nessun input('Premi INVIO'): l'utente non sta guardando la console.
        sys.exit(0 if ok else 1)

    # v0.7.3+: menu CLI rimosso. Doppio-click sull'.exe = apri direttamente la GUI sicura.
    # Le vecchie azioni CLI (benchmark, sync, ripristina) sono TUTTE nella GUI:
    #   - Benchmark PRIMA/DOPO: toggle in fondo alla finestra
    #   - Ripristina: bottone "Ripristina tutto" nella bottom bar
    #   - Sync hardware: partita silent al boot dell'agent
    #   - Cambia account: bottone in header GUI
    # Backward-compat: --mode benchmark/sync/optimize/restore/logout continuano a funzionare
    # (usati dal protocol handler frameforge:// e dai power user).
    if _args.mode == "logout":
        _menu_logout()
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0)

    if _args.mode == "sync":
        send_all()
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0)
    if _args.mode == "benchmark":
        benchmark_only()
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0)
    if _args.mode == "restore":
        restore_tweaks()
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0)

    # Default = securegui/optimize/gui = apre la GUI sicura
    launch_secure_gui()
    try:
        input("\nPremi INVIO per chiudere...")
    except Exception:
        pass
    sys.exit(0)
