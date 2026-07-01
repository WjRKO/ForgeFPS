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


def collect_specs():
    s = {}
    s["os"] = ps("(Get-CimInstance Win32_OperatingSystem).Caption")
    s["cpu"] = ps("(Get-CimInstance Win32_Processor).Name")
    s["gpu"] = ps("(Get-CimInstance Win32_VideoController).Name -join ', '")
    ram = ps("[math]::round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,0)")
    s["ram"] = f"{ram} GB" if ram else ""
    s["motherboard"] = ps("(Get-CimInstance Win32_BaseBoard).Manufacturer + ' ' + "
                          "(Get-CimInstance Win32_BaseBoard).Product")
    disk = ps("(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).Model")
    size = ps("[math]::round(((Get-CimInstance Win32_DiskDrive | Measure-Object -Property Size -Sum).Sum)/1GB,0)")
    s["disk"] = (f"{disk} ({size} GB)" if disk else "").strip()
    res = ps("$v=Get-CimInstance Win32_VideoController | Select-Object -First 1; "
             "\"$($v.CurrentHorizontalResolution)x$($v.CurrentVerticalResolution)\"")
    s["resolution"] = res if res and "x" in res else ""
    return s


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
