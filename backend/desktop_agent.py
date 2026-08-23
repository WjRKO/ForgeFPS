AGENT_SCRIPT = r'''#!/usr/bin/env python3
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
import shlex
import tempfile
import ctypes
import re
import argparse
import urllib.request

_parser = argparse.ArgumentParser(description="FrameForge Agent")
_parser.add_argument("--token", default=os.environ.get("FORGEFPS_TOKEN", "__AGENT_TOKEN__"))
_parser.add_argument("--backend", default=os.environ.get("FORGEFPS_BACKEND", "__BACKEND_URL__"))
_parser.add_argument("--mode", default="optimize")
_args, _ = _parser.parse_known_args()

BACKEND_URL = _args.backend
AGENT_TOKEN = _args.token
AGENT_VERSION = "0.5.0"
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forgefps_backup.json")
_LEGACY_BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boostpc_backup.json")

if not AGENT_TOKEN or AGENT_TOKEN.startswith("__"):
    print("=" * 54)
    print("  FrameForge Agent")
    print("=" * 54)
    print("Incolla il tuo token (pagina 'FrameForge Agent' del tuo account) e premi INVIO.")
    print("Paste your token (from the 'FrameForge Agent' page) and press ENTER.")
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
    # shell=False + list args to avoid shell injection.
    # `cmd` accepts either a list or a string (split with Windows-aware shlex).
    try:
        args = shlex.split(cmd, posix=False) if isinstance(cmd, str) else cmd
        return subprocess.run(args, shell=False, capture_output=True, text=True).stdout.strip()
    except Exception as e:
        return f"errore: {e}"


def ps(cmd):
    # PowerShell invocation via arg list — no shell interpolation.
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            shell=False, capture_output=True, text=True,
        ).stdout.strip()
    except Exception as e:
        return f"errore: {e}"


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


# ---------------- Rilevamento: non vive piu' qui ----------------
# Questo script aveva un suo collect_specs()/collect_health()/collect_startup()
# che scriveva sugli stessi endpoint dello script PowerShell servito dal backend,
# ma con dati piu' poveri: refresh preso dal massimo fra i controller invece che
# dallo schermo primario, risoluzione dal primo controller della lista grezza,
# RAM descritta dal primo modulo, nessun hw_confidence, nessuna temperatura via
# LibreHardwareMonitor.
#
# Era la terza copia della stessa rilevazione (le altre: l'exe di agent-build e
# lo script PowerShell), e la piu' silenziosa: chi scaricava il .py da "FrameForge
# Agent" scriveva nello stesso documento del bottone "Sincronizza ora" specs di
# qualita' diversa, senza che niente lo segnalasse.
#
# Ora tutte le strade portano allo script servito. Qui restano solo le azioni che
# lo script non copre.


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


def _download_agent_script(ua="FrameForge-Agent"):
    """Scarica lo script PowerShell servito dal backend. Ritorna il percorso o None."""
    url = "%s/api/agent/script?t=%s" % (BACKEND_URL, AGENT_TOKEN)
    dest = os.path.join(tempfile.gettempdir(), "forgefps.ps1")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        return dest
    except Exception as e:
        print("    Impossibile scaricare lo script: %s" % e)
        return None


def run_ps_mode_inline(mode):
    """Esegue una mode PowerShell NELLA CONSOLE CORRENTE e aspetta che finisca.

    launch_secure_gui lancia e torna subito, il che va bene per una finestra che
    resta aperta per conto suo; qui invece l'utente sta guardando questa console
    e si aspetta di vedere il risultato prima del prompt successivo.
    """
    dest = _download_agent_script()
    if not dest:
        return 1
    args_list = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", dest, "-Token", AGENT_TOKEN, "-Mode", mode]
    try:
        return subprocess.call(args_list)
    except Exception as e:
        print("    Errore nell'avvio: %s" % e)
        return 1


def sync_now():
    """Rilevamento hardware/salute/avvio: lo esegue lo script servito."""
    print("\n[*] Rilevamento hardware, salute e programmi all'avvio...")
    run_ps_mode_inline("sync")


def launch_secure_gui():
    """Scarica e avvia la GUI sicura FrameForge: per ogni tweak mostra Problema, Motivo,
    Modifica proposta e Impatto stimato, con pulsante Applica per singolo tweak.
    Backup automatico + Ripristina sempre disponibili. Non tocca MAI Windows Defender / Firewall."""
    print("\n[*] Scarico la GUI sicura FrameForge...")
    dest = _download_agent_script()
    if not dest:
        return
    args_list = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", dest, "-Token", AGENT_TOKEN, "-Mode", "optimize"]
    try:
        if not is_admin():
            # ShellExecuteW requires a single args string; use Windows-safe quoting.
            args_str = subprocess.list2cmdline(args_list)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args_str, None, 1)
        else:
            subprocess.Popen(["powershell.exe"] + args_list, shell=False)
        print("    GUI sicura avviata: segui le istruzioni nella finestra (Problema/Motivo/Impatto per ogni tweak).")
    except Exception as e:
        print("    Errore nell'avvio della GUI sicura: %s" % e)


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
        "G": ("GUI SICURA - Problema/Motivo/Impatto per ogni tweak (consigliato)", launch_secure_gui),
        "1": ("Pulizia temp + cache Windows Update", _cleanup),
        "3": ("Piano energetico alte prestazioni", high_performance_power),
        "4": ("Mostra processi pesanti", top_processes),
        "7": ("Rileva hardware/salute e invia al cloud", sync_now),
        "8": ("Ripristina impostazioni (backup)", restore_tweaks),
        "B": ("Benchmark del sistema", benchmark_only),
        "A": ("OTTIMIZZA TUTTO + benchmark prima/dopo (avanzato)", optimize_with_benchmark),
    }
    print("=" * 54)
    print("   FrameForge Agent  v%s" % AGENT_VERSION)
    print("=" * 54)
    if not is_admin():
        print("[WARN] Suggerito eseguire come Amministratore.")
    for k in ["G", "1", "3", "4", "7", "8", "B", "A"]:
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
    if _args.mode == "sync":
        # Stessa rilevazione del bottone "Sincronizza ora" della dashboard.
        sync_now()
        try:
            input("\nPremi INVIO per chiudere...")
        except Exception:
            pass
        sys.exit(0)
    if _args.mode in ("securegui", "gui"):
        launch_secure_gui()
        try:
            input("\nPremi INVIO per chiudere...")
        except Exception:
            pass
        sys.exit(0)
    while True:
        os.system("cls")
        menu()
'''
