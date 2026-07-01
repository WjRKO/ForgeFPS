AGENT_SCRIPT = r'''#!/usr/bin/env python3
"""
BOOST PC AI - Desktop Agent (Windows)
Companion locale che esegue azioni REALI di ottimizzazione sul PC
e rileva l'hardware per inviarlo al tuo account BOOST PC (consigli AI su misura).
Uso:  python boostpc_agent.py
Richiede Windows. Alcune azioni richiedono privilegi di amministratore.
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


def detect_hardware():
    print("\n[*] Rilevamento hardware in corso...")
    specs = {}
    specs["os"] = ps("(Get-CimInstance Win32_OperatingSystem).Caption + ' ' + "
                     "(Get-CimInstance Win32_OperatingSystem).Version") or "Windows"
    specs["cpu"] = ps("(Get-CimInstance Win32_Processor).Name")
    gpu = ps("(Get-CimInstance Win32_VideoController).Name -join ', '")
    specs["gpu"] = gpu
    ram = ps("[math]::round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,0)")
    specs["ram"] = f"{ram} GB" if ram else ""
    specs["motherboard"] = ps("(Get-CimInstance Win32_BaseBoard).Manufacturer + ' ' + "
                              "(Get-CimInstance Win32_BaseBoard).Product")
    disk = ps("(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).Model")
    size = ps("[math]::round(((Get-CimInstance Win32_DiskDrive | "
              "Measure-Object -Property Size -Sum).Sum)/1GB,0)")
    specs["disk"] = (f"{disk} ({size} GB)" if disk else "").strip()
    res = ps("$s=Get-CimInstance Win32_VideoController | Select-Object -First 1; "
             "\"$($s.CurrentHorizontalResolution)x$($s.CurrentVerticalResolution)\"")
    specs["resolution"] = res if res and "x" in res else ""
    for k, v in specs.items():
        print(f"    {k.upper():14}: {v or 'n/d'}")
    return specs


def send_specs():
    if "__AGENT" in AGENT_TOKEN or not BACKEND_URL.startswith("http"):
        print("\n[!] Token non configurato. Riscarica l'agent dal tuo account BOOST PC.")
        return
    specs = detect_hardware()
    payload = json.dumps({"data": specs}).encode("utf-8")
    req = urllib.request.Request(f"{BACKEND_URL}/api/agent/report-specs", data=payload,
                                 headers={"Content-Type": "application/json",
                                          "X-Agent-Token": AGENT_TOKEN}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                print("\n[OK] Specifiche inviate! Apri l'AI Advisor per consigli su misura.")
            else:
                print(f"\n[!] Risposta server: {r.status}")
    except Exception as e:
        print(f"\n[!] Invio fallito: {e}")


def clean_temp():
    print("\n[1] Pulizia file temporanei...")
    freed = 0
    targets = [tempfile.gettempdir(), os.path.expandvars(r"%SystemRoot%\\Temp"),
               os.path.expandvars(r"%LOCALAPPDATA%\\Temp")]
    for t in targets:
        if not os.path.isdir(t):
            continue
        for name in os.listdir(t):
            path = os.path.join(t, name)
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    freed += os.path.getsize(path)
                    os.remove(path)
                elif os.path.isdir(path):
                    freed += sum(os.path.getsize(os.path.join(dp, f))
                                 for dp, _, fs in os.walk(path) for f in fs
                                 if os.path.exists(os.path.join(dp, f)))
                    shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
    print(f"    Liberati ~{freed / (1024*1024):.1f} MB")


def flush_dns():
    print("\n[2] Flush DNS...")
    print("    " + (run("ipconfig /flushdns") or "OK"))


def high_performance_power():
    print("\n[3] Attivazione piano energetico ad alte prestazioni...")
    run("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
    print("    Piano 'High Performance' attivato (se disponibile).")


def top_processes():
    print("\n[4] Processi che consumano piu' RAM:")
    out = ps("Get-Process | Sort-Object WS -Descending | Select-Object -First 8 "
             "Name,@{N='RAM_MB';E={[math]::round($_.WS/1MB,1)}} | Format-Table -AutoSize | Out-String")
    print(out or "    (impossibile leggere i processi)")


def gaming_tweaks():
    print("\n[5] Tweak gaming (Game Mode + GPU scheduling)...")
    run('reg add "HKCU\\Software\\Microsoft\\GameBar" /v AllowAutoGameMode /t REG_DWORD /d 1 /f')
    run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers" '
        '/v HwSchMode /t REG_DWORD /d 2 /f')
    print("    Game Mode e Hardware-Accelerated GPU Scheduling abilitati (riavvio consigliato).")


def disk_cleanup():
    print("\n[6] Avvio pulizia disco di Windows...")
    run("cleanmgr /sagerun:1")
    print("    Pulizia disco avviata.")


def menu():
    actions = {
        "1": ("Pulizia file temporanei", clean_temp),
        "2": ("Flush DNS", flush_dns),
        "3": ("Piano energetico alte prestazioni", high_performance_power),
        "4": ("Mostra processi pesanti", top_processes),
        "5": ("Tweak gaming (Game Mode/GPU)", gaming_tweaks),
        "6": ("Pulizia disco Windows", disk_cleanup),
        "7": ("Rileva hardware e invia al cloud", send_specs),
        "A": ("Esegui ottimizzazioni (1-6)", None),
    }
    print("=" * 52)
    print("   BOOST PC AI - Desktop Agent")
    print("=" * 52)
    if not is_admin():
        print("[!] Suggerito eseguire come Amministratore per tutte le azioni.")
    for k, (label, _) in actions.items():
        print(f"  {k}. {label}")
    print("  Q. Esci")
    choice = input("\nScegli un'azione: ").strip().upper()
    if choice == "Q":
        sys.exit(0)
    if choice == "A":
        for k in ["1", "2", "3", "4", "5", "6"]:
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
