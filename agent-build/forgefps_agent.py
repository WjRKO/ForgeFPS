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

# v0.7.6 (A+B+E+H): Recipe System dei tweak in un modulo separato
from tweaks import (
    TWEAKS, CATEGORIES, TweakContext,
    get_by_categories, get_by_id, apply_selected,
    revert_tweak as tweaks_revert_tweak,
    revert_by_categories as tweaks_revert_by_cats,
)

_parser = argparse.ArgumentParser(description="FrameForge Agent")
_parser.add_argument("--token", default=os.environ.get("FORGEFPS_TOKEN", "__AGENT_TOKEN__"))
_parser.add_argument("--backend", default=os.environ.get("FORGEFPS_BACKEND", "https://forgefps.dev"))
_parser.add_argument("--mode", default="optimize")
_parser.add_argument("--uri", default="", help="URI custom-protocol firmato (frameforge://launch?...)")
_parser.add_argument("--register-protocol", action="store_true",
                     help="Registra frameforge:// nel registro utente e esce (idempotente)")
_parser.add_argument("--no-console", action="store_true",
                     help="v0.7.6+: forza hide console anche in modalita' non-silent (usato da launcher.vbs)")
_parser.add_argument("--from-updater", action="store_true",
                     help="v0.7.6+: flag interno set dal .bat updater dopo self-update")
_parser.add_argument("--skip-update-check", action="store_true",
                     help="v0.7.6+: salta il check auto-update all'avvio")
_parser.add_argument("--categories", default="",
                     help="v0.7.6+: comma-separated list di categorie da applicare (latency,gaming,privacy,bloatware,system,visual). Default: tutte.")
_parser.add_argument("--tweak-id", default="",
                     help="v0.7.6+: applica/ripristina un singolo tweak (usato con --mode restore-one)")
_args, _ = _parser.parse_known_args()

# v0.7.6: hide the console window IMMEDIATELY if this launch was triggered
# from a "silent" web dashboard button (frameforge://...&silent=1). This must
# happen BEFORE any print() — otherwise the console flashes on screen even for
# a fraction of a second, which the user perceives as a scary "terminal popup".
# The signature check happens later; hiding the window is a pure UX layer.
# Extended in v0.7.6: also hide when --no-console is explicitly set (from vbs
# launcher for regular GUI launches — the actual UI is the PowerShell window
# that we spawn, so our own console has zero value).
def _hide_console_if_silent(uri: str) -> None:
    should_hide = _args.no_console or (uri and "silent=1" in uri)
    if not should_hide:
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass  # non-Windows or restricted env: fail silently
    # Silence any stdout/stderr so subsequent prints don't buffer/leak.
    try:
        _null = open(os.devnull, "w")
        sys.stdout = _null
        sys.stderr = _null
    except Exception:
        pass

_hide_console_if_silent(_args.uri)

BACKEND_URL = _args.backend
AGENT_TOKEN = _args.token
AGENT_VERSION = "0.8.1"
# ---------------------------------------------------------------------------
# Backup e journal: gli stessi file dell'agent PowerShell
# ---------------------------------------------------------------------------
# Il backup stava accanto all'.exe. Se l'exe e' in Program Files quella cartella
# non e' scrivibile, se sta in Download sparisce col primo riordino, e ogni
# reinstallazione ci passa sopra: il file che serve ad annullare le modifiche
# era il piu' fragile del prodotto.
#
# E soprattutto era un SECONDO backup. I due agent hanno cataloghi di tweak
# diversi (qui 'tcp-nagle-off', di la' 'network') ma scrivono le stesse chiavi
# di registro nello stesso formato: erano due file che non si parlavano, quindi
# "Ripristina" da riga di comando non annullava quello che aveva fatto la
# finestra, e viceversa. La domanda "cosa mi hai fatto al PC" non puo' avere due
# risposte diverse a seconda di come si e' aperto il programma.
_FF_HOME = os.path.join(os.environ.get("APPDATA") or tempfile.gettempdir(), "FrameForge")
try:
    os.makedirs(_FF_HOME, exist_ok=True)
except Exception:
    pass
BACKUP_FILE = os.path.join(_FF_HOME, "backup.json")
JOURNAL_FILE = os.path.join(_FF_HOME, "journal.jsonl")
# I percorsi di prima: si leggono finche' esistono e si fondono nel condiviso.
_OLD_BACKUPS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "forgefps_backup.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "boostpc_backup.json"),
]
# Chiavi che non sono modifiche da annullare ma metadati dell'altro motore: si
# preservano quando si riscrive il file, si saltano quando si ripristina.
_META_KEYS = ("__tweak_keys__", "__applied_at__", "tweaks")
# Una sessione per esecuzione, come di la': e' il raggruppamento con cui la
# schermata Journal racconta "quella volta".
_SESSION = "s-" + time.strftime("%Y%m%d-%H%M%S")


# ---------------------------------------------------------------------------
# Progress bar UX (v0.7.6) — b4
# ---------------------------------------------------------------------------
# Progress bar reale (ANSI + custom) invece di sequenze di print("[STEP]...").
# - Se stdout e' un TTY (console visibile) -> barra grafica con \r updates
# - Se stdout e' nascosto/redirected -> log strutturato "[N/T] task: msg" (no \r)
# Nessuna dipendenza esterna: zero peso aggiuntivo al bundle PyInstaller.
class Progress:
    def __init__(self, total: int, title: str = ""):
        self.total = max(1, int(total))
        self.n = 0
        self.title = title
        self._tty = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False
        if self._tty and title:
            sys.stdout.write(f"\n\033[1;33m▸ {title}\033[0m\n")
            sys.stdout.flush()

    def step(self, msg: str = "", success: bool = True) -> None:
        self.n += 1
        try:
            if self._tty:
                # rendering grafico: bar + pct + msg (60ch max, right-truncated)
                bar_w = 24
                filled = int(bar_w * self.n / self.total)
                bar = "█" * filled + "░" * (bar_w - filled)
                pct = int(100 * self.n / self.total)
                icon = "\033[32m✔\033[0m" if success else "\033[31m✘\033[0m"
                msg_trunc = (msg[:57] + "...") if len(msg) > 60 else msg
                sys.stdout.write(f"\r  \033[36m[{bar}]\033[0m {pct:3d}% {icon} {msg_trunc:<62}")
                sys.stdout.flush()
                if self.n >= self.total:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
            else:
                # fallback log-style: una riga per step, no overwrite
                mark = "OK" if success else "ERR"
                print(f"[{self.n}/{self.total}] {mark} · {msg}")
        except Exception:
            pass

    def done(self, msg: str = "Completato") -> None:
        if self._tty:
            sys.stdout.write(f"\n  \033[1;32m✔ {msg}\033[0m\n")
            sys.stdout.flush()
        else:
            print(f"[DONE] {msg}")


# ---------------------------------------------------------------------------
# Auto-update in-place (v0.7.6) — c1
# ---------------------------------------------------------------------------
# All'avvio (dopo protocol registration) contatta /api/agent/status e:
#  - se l'agent locale e' outdated -> scarica il nuovo .zip in %APPDATA%\FrameForge\update\
#  - estrae, poi genera un update.bat che:
#     1) attende 2s (l'exe corrente esce)
#     2) copia il nuovo .exe sopra quello attuale
#     3) rilancia con --from-updater --skip-update-check
#  - il main exe esce con exit(0) senza toccare nulla
# Non blocca l'avvio: se timeout o rete morta -> continua normalmente.
def _update_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "FrameForge", "update")


def _current_agent_version_tuple() -> tuple:
    try:
        return tuple(int(x) for x in AGENT_VERSION.split("."))
    except Exception:
        return (0, 0, 0)


# Da dove accettiamo un pacchetto di aggiornamento. Il backend dice quale URL
# scaricare, ma non puo' mandarci ovunque: se una risposta (per errore di
# configurazione, per un backend sbagliato passato con --backend, o perche'
# manomessa) puntasse altrove, l'updater diventerebbe un downloader-esecutore
# generico.
_UPDATE_HOST = "github.com"
_UPDATE_PATH_PREFIX = "/WjRKO/ForgeFPS/releases/download/"


def _is_allowed_update_url(url: str) -> bool:
    try:
        u = urllib.parse.urlparse((url or "").strip())
    except Exception:
        return False
    if u.scheme != "https" or u.netloc.lower() != _UPDATE_HOST:
        return False
    return u.path.startswith(_UPDATE_PATH_PREFIX) and ".." not in u.path


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_sha256(v: str) -> bool:
    return len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _check_and_apply_update(relaunch: bool = True) -> bool:
    """Ritorna True se ha avviato l'updater (chi chiama deve fare sys.exit).
    False se non serve aggiornare o se qualcosa e' fallito (continua normale).

    v0.7.9: relaunch=False -> il bat copia i file SENZA riavviare l'exe.
    Usato per gli update in background dopo un'azione via URI (i bottoni della
    dashboard): il vecchio comportamento riavviava l'exe senza argomenti, che
    apriva la GUI optimize -> ShellExecute runas -> popup UAC inatteso."""
    if _args.from_updater or _args.skip_update_check or not getattr(sys, "frozen", False):
        return False  # dev mode / updater loop protection
    try:
        url = f"{BACKEND_URL}/api/agent/status"
        # Endpoint richiede auth cookie: qui usiamo un endpoint pubblico separato
        # per la versione. Fallback: prendiamo la versione dal file .json embedded
        # nel release GitHub. Timeout aggressivo per non bloccare l'avvio.
        pub_url = f"{BACKEND_URL}/api/agent/latest-version"
        req = urllib.request.Request(pub_url, headers={"User-Agent": "FrameForge-Updater", "X-Agent-Version": AGENT_VERSION})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        latest = data.get("version", "")
        zip_url = data.get("download_url", "")
        expected_sha = str(data.get("sha256") or "").strip().lower()
        if not latest or not zip_url:
            return False
        latest_t = tuple(int(x) for x in latest.split(".")) if all(x.isdigit() for x in latest.split(".")) else (0, 0, 0)
        if latest_t <= _current_agent_version_tuple():
            return False  # gia' aggiornato
        if not _is_allowed_update_url(zip_url):
            print("[WARN] Aggiornamento ignorato: URL di download non consentito (%s)." % zip_url[:120])
            return False
        # Nessun hash, nessun aggiornamento. L'eseguibile non e' firmato, quindi
        # il confronto con lo SHA256 dichiarato dal backend e' l'unica cosa che
        # sta fra una release e il xcopy sopra l'installazione dell'utente.
        # Un backend vecchio che non lo espone semplicemente non aggiorna: non
        # aggiornarsi e' un fallimento innocuo, sovrascriversi con un pacchetto
        # non verificato no.
        if not _looks_like_sha256(expected_sha):
            print("[WARN] Aggiornamento ignorato: il backend non dichiara lo SHA256 del pacchetto.")
            return False
        # Scarica lo zip
        upd_dir = _update_dir()
        os.makedirs(upd_dir, exist_ok=True)
        zip_path = os.path.join(upd_dir, "forgefps-agent.zip")
        req2 = urllib.request.Request(zip_url, headers={"User-Agent": "FrameForge-Updater"})
        with urllib.request.urlopen(req2, timeout=30) as r:
            with open(zip_path, "wb") as f:
                shutil.copyfileobj(r, f)
        got_sha = _sha256_file(zip_path)
        if got_sha != expected_sha:
            print("[ERR ] Aggiornamento ANNULLATO: il pacchetto scaricato non corrisponde.")
            print("       atteso  %s" % expected_sha)
            print("       ricevuto %s" % got_sha)
            try:
                os.unlink(zip_path)
            except Exception:
                pass
            return False
        # Estrai
        import zipfile as _zip
        with _zip.ZipFile(zip_path) as z:
            z.extractall(upd_dir)
        # Trova il nuovo exe (potrebbe essere in upd_dir o in una sotto-cartella)
        new_exe = None
        for root_p, _dirs, files in os.walk(upd_dir):
            for fn in files:
                if fn.lower() == "forgefps-agent.exe":
                    new_exe = os.path.join(root_p, fn)
                    break
            if new_exe:
                break
        if not new_exe or not os.path.exists(new_exe):
            return False
        current_exe = _agent_exe_path()
        current_dir = os.path.dirname(current_exe)
        new_dir = os.path.dirname(new_exe)
        # Genera l'updater .bat (sopravvive alla morte del nostro processo)
        # v0.7.9: copia TUTTA la cartella onedir (exe + _internal), non solo
        # l'exe: mescolare exe nuovo con _internal vecchio crashava il boot
        # PyInstaller se le versioni di Python/PyInstaller differivano.
        bat_path = os.path.join(upd_dir, "update.bat")
        relaunch_line = ""
        if relaunch:
            orig_args = " ".join('"%s"' % a.replace('"', "") for a in sys.argv[1:])
            relaunch_line = f'start "" "{current_exe}" --from-updater --skip-update-check {orig_args}\r\n'
        bat_content = (
            "@echo off\r\n"
            "REM FrameForge Agent updater - auto-generated\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'xcopy /E /Y /Q "{new_dir}\\*" "{current_dir}\\" >nul\r\n'
            + relaunch_line +
            "REM cleanup temp update dir best-effort\r\n"
            f'rd /S /Q "{upd_dir}" >nul 2>&1\r\n'
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        # Lancia il .bat hidden e ritorna True (main deve sys.exit)
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except Exception:
        return False


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
_APPDATA_DIR = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "FrameForge")


def _agent_exe_path() -> str:
    """Percorso dell'exe attualmente in esecuzione (o dello script .py in dev)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def _parse_launcher_target(vbs_path: str):
    """v0.8.0: legge il marker '## target=...|version=x.y.z' dal launcher.vbs.
    Ritorna (exe_path, version_string) o (None, None)."""
    try:
        with open(vbs_path, "r", encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r"' ## target=(.+?)\|version=(\d+\.\d+\.\d+)", txt)
        if m:
            return m.group(1).strip(), m.group(2)
    except Exception:
        pass
    return None, None


def _write_hidden_launcher() -> str:
    """v0.7.6: crea un launcher .vbs in %APPDATA%\\FrameForge\\launcher.vbs che
    esegue l'agent SENZA MAI mostrare una finestra console — nemmeno il flash
    iniziale che si vede quando Windows crea la console prima che Python
    esegua ShowWindow(SW_HIDE).

    `wscript.exe` con WshShell.Run(cmd, 0, False) spawna il processo con
    SW_HIDE fin dal primo istante: e' il modo canonico Microsoft-approved per
    eseguire un exe --console in background su Windows.

    Il .vbs viene rigenerato ad ogni avvio dell'agent (ottimistico: se l'utente
    ha spostato l'exe, tracciamo il nuovo path). Fallback: se non si riesce a
    scriverlo, `register_frameforge_protocol` cade su registrazione diretta.

    v0.8.0 ANTI-DOWNGRADE: se il launcher esistente punta a un exe PIU' NUOVO
    che esiste ancora su disco, NON viene riscritto. Un exe vecchio avviato per
    sbaglio (es. copia dimenticata in Downloads) non puo' piu' rubarsi la
    registrazione del protocollo — causa storica dei popup UAC ricorrenti.
    """
    try:
        os.makedirs(_APPDATA_DIR, exist_ok=True)
        my_exe = _agent_exe_path()
        vbs_path = os.path.join(_APPDATA_DIR, "launcher.vbs")
        old_exe, old_ver = _parse_launcher_target(vbs_path)
        if (old_exe and old_ver and os.path.exists(old_exe)
                and os.path.normcase(old_exe) != os.path.normcase(my_exe)):
            try:
                if tuple(int(x) for x in old_ver.split(".")) > _current_agent_version_tuple():
                    print(f"[INFO] Launcher lasciato alla versione piu' recente {old_ver} ({old_exe}).")
                    return vbs_path
            except Exception:
                pass
        exe = my_exe.replace('"', '""')
        backend = BACKEND_URL.replace('"', '""')
        content = (
            "' FrameForge silent launcher — v0.8.0\n"
            "' Auto-generated by forgefps-agent.exe. Runs the agent with no console flash.\n"
            f"' ## target={my_exe}|version={AGENT_VERSION}\n"
            "Option Explicit\n"
            "Dim shell, uri, cmd\n"
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            "If WScript.Arguments.Count < 1 Then WScript.Quit 1\n"
            "uri = WScript.Arguments(0)\n"
            f'cmd = """{exe}"" --no-console --backend ""{backend}"" --uri """ & Replace(uri, """", """""") & """"\n'
            "shell.Run cmd, 0, False\n"  # 0 = SW_HIDE, False = don't wait
        )
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return vbs_path
    except Exception:
        return ""


def _clear_runasadmin_compat_flag() -> None:
    """v0.8.0: rimuove il flag 'Esegui questo programma come amministratore'
    (RUNASADMIN) dalle proprieta' di compatibilita' dell'exe corrente e del
    target del launcher. E' la causa piu' subdola di popup UAC con manifest
    asInvoker: il flag vive in HKCU AppCompatFlags\\Layers, e' keyed sul PATH
    e sopravvive alla sostituzione del file exe."""
    if not sys.platform.startswith("win"):
        return
    try:
        import winreg  # type: ignore
    except Exception:
        return
    key_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    paths = {_agent_exe_path()}
    t_exe, _v = _parse_launcher_target(os.path.join(_APPDATA_DIR, "launcher.vbs"))
    if t_exe:
        paths.add(t_exe)
    for exe in paths:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                               winreg.KEY_READ | winreg.KEY_SET_VALUE)
        except OSError:
            return
        try:
            try:
                val, _t = winreg.QueryValueEx(k, exe)
            except OSError:
                continue
            tokens = str(val).split()
            cleaned = [t for t in tokens if t.upper() != "RUNASADMIN"]
            if cleaned != tokens:
                if cleaned:
                    winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, " ".join(cleaned))
                else:
                    winreg.DeleteValue(k, exe)
                print(f"[ OK ] Rimosso flag 'Esegui come amministratore' da: {exe}")
        except Exception:
            pass
        finally:
            try:
                winreg.CloseKey(k)
            except Exception:
                pass


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
    # v0.7.6: prova il launcher .vbs -> ZERO flash console. Se fallisce, fallback
    # a exe diretto (che con _hide_console_if_silent almeno riduce il flash a
    # pochi ms).
    vbs = _write_hidden_launcher()
    if vbs:
        # wscript.exe path standard su tutti i Windows moderni
        wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
        command = f'"{wscript}" "{vbs}" "%1"'
    else:
        # Fallback: registra l'exe direttamente (con --backend). Il flash sara'
        # comunque minimizzato da _hide_console_if_silent() eseguito post-parse.
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
            via = "vbs launcher (no flash)" if vbs else "direct exe (mini-flash)"
            print(f"[ OK ] Protocollo {_PROTOCOL}:// registrato via {via} -> {exe} (backend={BACKEND_URL})")
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
            # v0.7.4+: ritorna info sul silent hint anche in errore, cosi'
            # il chiamante puo' decidere se aprire una GUI (bad UX per silent).
            return {"invalid_reason": "expired", "silent_hint": silent}
        expected = hmac.new(
            agent_token.encode("utf-8"),
            f"{mode}|{ts}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            print("[WARN] Firma URI non valida. Token locale potrebbe essere di un altro account.")
            print("       Fix: apri la GUI locale -> 'Cambia account' e reincolla il token dell'account attuale,")
            print("       oppure lancia 'Avvia-FrameForge.bat' dal ZIP scaricato dall'account attuale.")
            return {"invalid_reason": "sig_mismatch", "silent_hint": silent}
        # v0.7.6: estrai anche categories e tweak_id (non firmati, sono UX hints).
        # Non sono security-critical: alterando questi param si puo' solo cambiare
        # QUALI tweak vengono applicati tra quelli gia' autenticati via 'mode'.
        categories = (qs.get("categories") or [""])[0]
        tweak_id = (qs.get("tweak_id") or [""])[0]
        return {"mode": mode, "ts": ts, "silent": silent, "categories": categories, "tweak_id": tweak_id}
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
            # v0.7.6: se il chiamante voleva "silent" (bottoni dashboard) NON
            # aprire prompt visibili (la console e' gia' nascosta) — esci muto.
            if "silent=1" in _args.uri:
                sys.exit(2)
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
# v0.7.4+: se firma fallita ma silent=1 era richiesto, NON aprire una GUI
#          visibile (bad UX: l'utente pensa di aver premuto un bottone silent
#          e vede spuntare una finestra). Esci silenziosamente con codice 2.
_SILENT_FROM_URI = False
_INVALID_URI_SILENT_HINT = False
if _args.uri:
    payload = parse_and_verify_uri(_args.uri, AGENT_TOKEN)
    if payload and not payload.get("invalid_reason"):
        _args.mode = payload["mode"]
        _SILENT_FROM_URI = bool(payload.get("silent"))
        # v0.7.6: URI param categories/tweak_id -> _args (override CLI)
        if payload.get("categories"):
            _args.categories = payload["categories"]
        if payload.get("tweak_id"):
            _args.tweak_id = payload["tweak_id"]
        # Se la mode e' 'gui' o 'optimize' apriamo direttamente la finestra sicura
        if _args.mode in ("gui", "optimize") and not _SILENT_FROM_URI:
            _args.mode = "securegui"
    elif payload and payload.get("invalid_reason") and payload.get("silent_hint"):
        # Firma invalida MA il chiamante voleva silent -> exit silenzioso
        # (nessuna GUI visibile). Il web dashboard mostrera' il toast di errore
        # dopo il timeout e guidera' l'utente al riallineamento del token.
        _INVALID_URI_SILENT_HINT = True
        _args.mode = "silent_signature_error"
    else:
        # URI non valido e senza hint silent -> apri la GUI normale in modalita' securegui
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
    bk = {}
    if os.path.exists(BACKUP_FILE):
        try:
            bk = json.load(open(BACKUP_FILE, encoding="utf-8"))
        except Exception:
            bk = {}
    # Un backup vecchio accanto all'exe non si abbandona: le sue chiavi entrano
    # in quello condiviso senza sovrascrivere niente — chi c'e' gia' e' stato
    # scritto dopo — e il file vecchio se ne va al primo salvataggio riuscito.
    for old in _OLD_BACKUPS:
        if not os.path.exists(old):
            continue
        try:
            vecchio = json.load(open(old, encoding="utf-8"))
        except Exception:
            continue
        for k, v in vecchio.items():
            if k not in bk:
                bk[k] = v
    return bk


def _save_backup(bk):
    # I metadati dell'altro motore (__tweak_keys__, __applied_at__) viaggiano
    # dentro `bk` e vengono riscritti insieme al resto: se li perdessimo, di la'
    # sparirebbe la possibilita' di annullare un singolo tweak.
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(bk, f, indent=2)
    for old in _OLD_BACKUPS:
        try:
            if os.path.exists(old):
                os.remove(old)
        except Exception:
            pass


def _journal(event, tweak_id, name, cat, ok, err=""):
    """Una riga nel journal condiviso: quello che si fa da riga di comando deve
    comparire nella stessa cronologia di quello che si fa dalla finestra,
    altrimenti quella schermata dice di essere il registro completo e non lo e'.
    `via` dice da quale dei due motori e' passato."""
    try:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session": _SESSION,
            "event": event,
            "tweak": str(tweak_id),
            "name": str(name),
            "cat": str(cat),
            "ok": bool(ok),
            "via": "cli",
        }
        if err:
            rec["err"] = str(err)
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # Un journal che non si scrive non deve impedire un'ottimizzazione.
        pass


def _journal_esiti(selezionati, bk, event="apply"):
    """Legge gli esiti che apply_selected ha gia' marcato in bk['tweaks'] e ne
    scrive una riga ciascuno. Cosi' il journal riporta il verdetto vero del
    Recipe System (applicato / applicato ma non verificato / fallito) invece di
    un totale."""
    esiti = (bk or {}).get("tweaks") or {}
    for t in selezionati:
        e = esiti.get(t.id) or {}
        applicato = bool(e.get("applied"))
        verificato = bool(e.get("verified"))
        err = ""
        if not applicato:
            err = "l'apply non e' riuscito"
        elif not verificato:
            err = "applicato ma la verifica non conferma il valore atteso"
        _journal(event, t.id, t.name, getattr(t, "category", ""), applicato and verificato, err)


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


def _build_tweak_context():
    """v0.7.6 (A): Detecta hardware profile e crea il TweakContext per il Recipe System."""
    ct = ps("(Get-CimInstance Win32_SystemEnclosure).ChassisTypes -join ','")
    is_laptop = any(x in (ct or "").split(",") for x in ["8", "9", "10", "14", "30", "31", "32"])
    try:
        ram_gb = int(ps("[math]::round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,0)") or 0)
    except Exception:
        ram_gb = 0
    is_ssd = "SSD" in (ps("(Get-Partition -DriveLetter C -ErrorAction SilentlyContinue | Get-Disk | Get-PhysicalDisk).MediaType") or "")
    return TweakContext(
        run=run, ps=ps, reg_get=reg_get, set_reg=set_reg, _clean=_clean,
        is_laptop=is_laptop, ram_gb=ram_gb, is_ssd=is_ssd,
    )


def apply_all_tweaks():
    """v0.7.6 (A+B+E+H) — orchestrator sopra il Recipe System in tweaks.py.
    - Rispetta --categories="latency,gaming" (o applica tutti)
    - Rispetta --tweak-id="tcp-nagle-off" per applicare un solo tweak
    - Ogni tweak viene verificato dopo l'apply e marcato in bk["tweaks"][id]
    - Progress bar reale con simbolo ✔/⚠ per verified/applied-but-not-verified
    """
    bk = _load_backup()
    ctx = _build_tweak_context()
    print("\n[STEP] Profilo hardware: %s, RAM %d GB, disco %s" %
          ("Laptop" if ctx.is_laptop else "Desktop", ctx.ram_gb, "SSD" if ctx.is_ssd else "HDD"))
    _cleanup()

    # Selezione: --tweak-id (uno solo) o --categories (filtro) o tutti
    if _args.tweak_id:
        one = get_by_id(_args.tweak_id)
        if not one:
            print(f"[ERR ] Tweak id '{_args.tweak_id}' non trovato.")
            return
        selected = [one]
        title = f"Applico 1 tweak: {one.name}"
    else:
        cats = [c.strip() for c in (_args.categories or "").split(",") if c.strip()]
        selected = get_by_categories(cats)
        if cats:
            title = f"Applico {len(selected)} tweak in categorie: {', '.join(cats)}"
        else:
            title = f"Applico {len(selected)} ottimizzazioni (tutte le categorie)"

    prog = Progress(total=len(selected), title=title)
    stats = apply_selected(selected, ctx, bk, progress=prog)
    _save_backup(bk)
    _journal_esiti(selected, bk)

    prog.done(
        f"Applicati {stats['applied']}/{len(selected)} · verificati {stats['verified']} · "
        f"skipped {stats['skipped']} (hardware gate) · falliti {stats['failed']}"
    )
    if stats["reboot_needed"]:
        print("\n[INFO] Alcuni tweak richiedono riavvio per attivarsi completamente.")


def apply_tweak_by_id(tweak_id: str) -> bool:
    """v0.7.6 (E): Applica un singolo tweak per id (wrapper CLI-friendly)."""
    bk = _load_backup()
    ctx = _build_tweak_context()
    one = get_by_id(tweak_id)
    if not one:
        print(f"[ERR ] Tweak '{tweak_id}' non trovato. Elenco disponibili:")
        for t in TWEAKS:
            print(f"  - {t.id} ({t.category})")
        return False
    prog = Progress(total=1, title=f"Applico: {one.name}")
    stats = apply_selected([one], ctx, bk, progress=prog)
    _save_backup(bk)
    _journal_esiti([one], bk)
    prog.done(f"{stats['applied']} applicati, {stats['verified']} verificati")
    return stats["applied"] > 0


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


def launch_secure_gui(mode: str = "optimize", allow_elevation: bool = True):
    """Scarica ed esegue lo script FrameForge PowerShell nella mode specificata.

    v0.7.4+: prende un parametro `mode` (default: 'optimize' per la GUI).
    Prima era hardcodato a 'optimize', quindi URI come mode=monitor/fullbench/
    booster/prematch/bufferbloat venivano SILENZIOSAMENTE convertiti in optimize
    (l'utente cliccava 'Avvia monitor' e vedeva partire il primo scan della GUI).

    Modes UI-visibili (con finestra PowerShell): optimize (GUI sicura),
    monitor (loop di telemetria), fullbench (~3min), prematch, booster.
    Modes 'silent' via URL vanno passate a launch_silent_mode() invece.

    v0.8.0: `allow_elevation=False` per i lanci via URI (bottoni dashboard):
    NESSUN ShellExecute 'runas' in nessun caso — un click sul web non deve MAI
    produrre un popup UAC. La GUI si apre non-elevata e mostra
    'Amministratore: NO'; l'elevazione resta riservata al doppio-click diretto.
    """
    url = "%s/api/agent/script?t=%s" % (BACKEND_URL, AGENT_TOKEN)
    dest = os.path.join(tempfile.gettempdir(), "forgefps.ps1")
    print("\n[STEP] Scarico lo script FrameForge (mode=%s)..." % mode)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FrameForge-Agent", "X-Agent-Version": AGENT_VERSION})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
    except Exception as e:
        print("[ERR ] Impossibile scaricare lo script: %s" % e)
        return
    # Solo la mode 'optimize' beneficia dell'elevazione UAC (per applicare tweak).
    # Le altre mode (monitor, benchmark ecc.) girano in user-space senza UAC.
    args = '-NoProfile -ExecutionPolicy Bypass -File "%s" -Token %s -Mode %s' % (dest, AGENT_TOKEN, mode)
    try:
        if mode == "optimize" and not is_admin() and allow_elevation:
            # rilancia PowerShell elevato: la finestra sicura chiedera' conferma UAC
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 1)
        else:
            subprocess.Popen("powershell.exe %s" % args, shell=True)
        print("[ OK ] Script avviato in mode=%s." % mode)
    except Exception as e:
        print("[ERR ] Errore nell'avvio: %s" % e)


def launch_silent_mode(mode: str) -> bool:
    """v0.7.1+: esegue la mode PowerShell in background senza aprire finestre.
    Usato dai bottoni 'silent' della web dashboard (sync/benchmark ambientali).
    Ritorna True se il processo e' stato lanciato con successo, False altrimenti.

    Nota: il PowerShell script standalone sync/benchmark termina da solo (unlike
    'monitor' che e' un loop infinito). Se qualcuno passasse mode='monitor' in
    silent avremmo un processo orfano - il backend impedisce comunque questa
    combinazione a livello di API (silent + monitor = rifiutato).
    """
    if mode not in ("sync", "benchmark", "cleanup", "autopilot", "optimize", "apply-one", "restore-one", "restore"):
        # Whitelist di mode adatte al lancio silent (non-interattive, terminano).
        print(f"[WARN] Mode '{mode}' non supporta il lancio silent. Uso GUI.")
        return False
    url = "%s/api/agent/script?t=%s" % (BACKEND_URL, AGENT_TOKEN)
    dest = os.path.join(tempfile.gettempdir(), "forgefps.ps1")
    print(f"[STEP] Silent {mode}: scarico script...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FrameForge-Agent-Silent", "X-Agent-Version": AGENT_VERSION})
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
    bk = _load_backup()
    if not [k for k in bk if k not in _META_KEYS]:
        print("       Nessun backup trovato: FrameForge non ha modifiche da annullare su questo PC.")
        return
    print("       Backup: %s" % BACKUP_FILE)
    if bk.get("power_plan"):
        run("powercfg -setactive %s" % bk["power_plan"])
    for k, v in bk.items():
        if k == "power_plan":
            continue
        # Metadati dell'altro motore: non sono chiavi da riscrivere. Prima
        # finivano nel ramo generico e producevano comandi `reg add` su percorsi
        # inventati, che fallivano in silenzio.
        if k in _META_KEYS:
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
    # Una riga per tweak tracciato dall'altro motore, cosi' la cronologia sa
    # che quelle modifiche non sono piu' attive.
    for _tid in list((bk.get("__tweak_keys__") or {}).keys()):
        _journal("revert", _tid, _tid, "", True)
    for _tid, _info in list((bk.get("tweaks") or {}).items()):
        _journal("revert", _tid, _tid, "", True)
    for _p in [BACKUP_FILE] + _OLD_BACKUPS:
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
        try:
            _clear_runasadmin_compat_flag()
        except Exception:
            pass
        sys.exit(0 if ok else 1)
    # Registrazione silenziosa best-effort al primo avvio: cosi il bottone
    # "Avvia" della dashboard funziona senza download da qui in avanti.
    try:
        register_frameforge_protocol(silent=True)
    except Exception:
        pass
    # v0.8.0: auto-riparazione del flag di compatibilita' 'Esegui come admin'
    # (RUNASADMIN in AppCompatFlags\Layers): con manifest asInvoker e' l'unica
    # causa rimasta di UAC all'avvio dell'exe, e sopravvive ai reinstall.
    try:
        _clear_runasadmin_compat_flag()
    except Exception:
        pass
    # v0.7.6: auto-update in-place. Se una nuova versione e' disponibile,
    # scarica ed esegue l'updater .bat, poi esce. In dev-mode (non frozen)
    # o dopo un self-update (--from-updater) skippa per non fare loop.
    # v0.7.9: se il lancio arriva da un URI frameforge:// (bottoni dashboard),
    # NON bloccare l'azione richiesta: l'update viene applicato in background
    # DOPO aver avviato l'azione, senza riavviare l'exe (niente GUI/UAC inattesi).
    if not _args.uri and _check_and_apply_update():
        sys.exit(0)
    # v0.7.1+: se URI includeva silent=1 -> esegui in background e esci subito.
    # Nessuna finestra visibile all'utente. Per sync/benchmark ambientali dal web.
    if _SILENT_FROM_URI:
        ok = launch_silent_mode(_args.mode if _args.mode not in ("securegui", "gui") else "sync")
        try:
            _check_and_apply_update(relaunch=False)
        except Exception:
            pass
        # Nessun input('Premi INVIO'): l'utente non sta guardando la console.
        sys.exit(0 if ok else 1)

    # v0.7.4+: firma URI invalida ma il chiamante voleva silent -> exit silenzioso.
    # Non apriamo alcuna GUI perche' l'utente ha premuto un bottone 'silent' e non
    # si aspetta una finestra. Il browser mostrera' il toast di errore dopo timeout.
    if _INVALID_URI_SILENT_HINT:
        print("[INFO] Uscita silenziosa: token locale disallineato con l'account che ha generato l'URI.")
        print("       Riallinea aprendo l'exe direttamente e usando 'Cambia account', oppure lancia")
        print("       'Avvia-FrameForge.bat' scaricato dall'account corretto.")
        sys.exit(2)

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

    # v0.7.6 (E): revert per singolo tweak — `--mode restore-one --tweak-id tcp-nagle-off`
    if _args.mode == "restore-one":
        if not _args.tweak_id:
            print("[ERR ] --tweak-id richiesto con --mode restore-one")
            print("       Es: forgefps-agent.exe --mode restore-one --tweak-id tcp-nagle-off")
            sys.exit(1)
        bk = _load_backup()
        ctx = _build_tweak_context()
        ok = tweaks_revert_tweak(ctx, bk, _args.tweak_id)
        _save_backup(bk)
        print(f"[{'OK' if ok else 'ERR'}] Revert tweak '{_args.tweak_id}': {'completato' if ok else 'fallito o non trovato'}")
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0 if ok else 1)

    # v0.7.6 (B): applica singolo tweak — `--mode apply-one --tweak-id tcp-nagle-off`
    if _args.mode == "apply-one":
        if not _args.tweak_id:
            print("[ERR ] --tweak-id richiesto con --mode apply-one")
            sys.exit(1)
        ok = apply_tweak_by_id(_args.tweak_id)
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0 if ok else 1)

    # v0.7.6 (A): elenca i tweak disponibili — utility per power user e dashboard
    if _args.mode == "list-tweaks":
        print(f"\nFrameForge Agent v{AGENT_VERSION} — Recipe System")
        print(f"{len(TWEAKS)} tweak disponibili in {len(CATEGORIES)} categorie:\n")
        for cat_id, cat in CATEGORIES.items():
            group = [t for t in TWEAKS if t.category == cat_id]
            if not group:
                continue
            print(f"  {cat['icon']} {cat['name']} ({cat_id}) — {cat['desc']}")
            for t in group:
                reboot = " [reboot]" if t.requires_reboot else ""
                gate = " [conditional]" if t.hardware_gate else ""
                print(f"      - {t.id}: {t.name}  ({t.impact}){reboot}{gate}")
            print()
        try: input("\nPremi INVIO per chiudere...")
        except Exception: pass
        sys.exit(0)

    # v0.7.4+: modes che passano allo script PowerShell in finestra visibile
    # (senza UAC per quelle che non modificano il sistema). Prima venivano
    # tutte silenziosamente convertite in 'optimize' -> l'utente cliccava
    # 'Avvia monitor' e vedeva partire il primo scan della GUI.
    _PS_UI_MODES = ("monitor", "fullbench", "prematch", "booster", "bufferbloat", "lab", "autopilot")
    if _args.mode in _PS_UI_MODES:
        launch_secure_gui(mode=_args.mode, allow_elevation=not _args.uri)
        if _args.uri:
            try:
                _check_and_apply_update(relaunch=False)
            except Exception:
                pass
        sys.exit(0)

    # Default = securegui/optimize/gui = apre la GUI sicura.
    # v0.8.0: se il lancio arriva da un URI (bottone dashboard, anche con firma
    # invalida/scaduta) NIENTE elevazione: mai UAC da un click sul web.
    launch_secure_gui(mode="optimize", allow_elevation=not _args.uri)
    try:
        input("\nPremi INVIO per chiudere...")
    except Exception:
        pass
    sys.exit(0)
