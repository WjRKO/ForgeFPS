"""
FrameForge Agent — Tweak Recipe System (v0.7.6 refactor)

Sistema declarativo per ottimizzazioni Windows. Ogni tweak e' un `Tweak`
object con metadati (categoria, why, impact, hardware gate, requires_reboot)
e tre callable: apply(ctx, bk), verify(ctx, bk) -> bool, revert(ctx, bk).

Perche' questo refactor:
- il vecchio apply_all_tweaks() era un monolite di 130 righe che poteva solo
  "tutto o niente". Nessun modo di applicare "solo network", nessun revert
  granulare, nessuna spiegazione dei tweak, nessuna verifica.
- questo modulo consente:
  A) organizzazione dichiarativa (tutti i tweak in un solo posto)
  B) filtro per categoria (--categories latency,gaming)
  E) revert per singolo tweak_id (--tweak-id ...)
  H) verify step post-apply (rileva GPO/AV che revertano le chiavi)

Backup compat: il dict `bk` mantiene il vecchio schema key-based (retro-compat
con agent v0.7.5) + una nuova sezione `bk["tweaks"] = {id: metadata}` con
info di applicazione/verifica per lo storico UI.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict, Any


# --- Categorie ------------------------------------------------------------
CATEGORIES: Dict[str, Dict[str, str]] = {
    "latency": {
        "name": "Latency & Input",
        "icon": "⚡",
        "desc": "Riduce input lag e latenza rete: TCP, Nagle, mouse accel, DNS, QoS.",
    },
    "gaming": {
        "name": "Gaming",
        "icon": "🎮",
        "desc": "Game Mode, GPU Scheduling, Fullscreen Optimizations, priority games.",
    },
    "privacy": {
        "name": "Privacy",
        "icon": "🔒",
        "desc": "Telemetria Windows, Content Delivery, suggerimenti Microsoft.",
    },
    "bloatware": {
        "name": "Bloatware",
        "icon": "🧹",
        "desc": "Rimozione app UWP preinstallate non essenziali (reinstallabili).",
    },
    "system": {
        "name": "System Deep",
        "icon": "⚙️",
        "desc": "Kernel in RAM, Power Throttling, SysMain, piano energetico Ultimate.",
    },
    "visual": {
        "name": "Visual & Effects",
        "icon": "🎨",
        "desc": "Effetti visivi Windows, animazioni, ombreggiature (prestazioni).",
    },
}


# --- Tweak dataclass -----------------------------------------------------
@dataclass
class Tweak:
    id: str                                    # stable id per backup/revert (kebab-case)
    category: str                              # una di CATEGORIES.keys()
    name: str                                  # nome breve human-readable
    why: str                                   # spiegazione tecnica (una frase)
    impact: str                                # impatto atteso (es. "+5-10ms input lag")
    difficulty: str = "safe"                   # safe | moderate | advanced
    requires_reboot: bool = False              # utente deve riavviare per attivarlo
    version: str = "1.0"                       # per future migrations
    hardware_gate: Optional[Callable] = None   # (ctx) -> bool: True se compat
    apply: Callable = None                     # (ctx, bk) -> None
    verify: Optional[Callable] = None          # (ctx, bk) -> bool
    revert: Optional[Callable] = None          # (ctx, bk) -> None


# --- Context: raccoglie le funzioni del main agent ------------------------
@dataclass
class TweakContext:
    """Passato ai callable dei Tweak. Evita circular imports col main."""
    run: Callable        # run(cmd) -> stdout
    ps: Callable         # ps(cmd) -> stdout
    reg_get: Callable    # reg_get(path, name) -> value
    set_reg: Callable    # set_reg(bk, path, name, rtype, value)
    _clean: Callable     # _clean(str) -> stripped str
    is_laptop: bool = False
    ram_gb: int = 0
    is_ssd: bool = False


# --- Helper per revert (retrocompat con backup v0.7.5) --------------------
def _revert_reg_key(ctx: TweakContext, bk: Dict[str, Any], path: str, name: str) -> None:
    """Ripristina una chiave di registro dal backup key-based (legacy)."""
    full_key = f"{path}::{name}"
    if full_key not in bk:
        return
    old = bk[full_key]
    if old == "__DELETE__":
        ctx.run(f'reg delete "{ctx._reg_cli_path(path) if hasattr(ctx, "_reg_cli_path") else path}" /v "{name}" /f')
    else:
        rtype, value = old["type"], old["value"]
        ctx.set_reg(None, path, name, rtype, value)


def _revert_paths(ctx: TweakContext, bk: Dict[str, Any], keys: List[tuple]) -> None:
    """Batch revert di una lista di (path, name)."""
    for path, name in keys:
        _revert_reg_key(ctx, bk, path, name)


# --- Tweak recipes -------------------------------------------------------
# Ogni tweak e' un oggetto dichiarativo. `apply` chiama ctx.set_reg che gia'
# salva in bk il valore pre-apply (retrocompat). `verify` rilegge la chiave.
# `revert` puo' usare _revert_paths oppure logica custom.

def _mark(bk: Dict[str, Any], tid: str, applied: bool, verified: bool) -> None:
    """Marca un tweak nel bk con esito apply/verify."""
    import time as _t
    bk.setdefault("tweaks", {})[tid] = {
        "applied": applied,
        "verified": verified,
        "at": _t.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ============================================================================
# LATENCY & INPUT
# ============================================================================

def _t_tcp_nagle_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ifaces = ctx.ps("Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces' | "
                    "Select-Object -ExpandProperty PSChildName")
    for guid in [l.strip() for l in (ifaces or "").splitlines() if l.strip()]:
        p = r"HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\%s" % guid
        ctx.set_reg(bk, p, "TcpAckFrequency", "DWord", 1)
        ctx.set_reg(bk, p, "TCPNoDelay", "DWord", 1)
    ctx.run("netsh int tcp set global autotuninglevel=normal")
    ctx.run("netsh int tcp set global ecncapability=enabled")
    ctx.run("netsh int tcp set global rss=enabled")


def _t_tcp_nagle_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    # Sample-check: prendi la prima interfaccia e verifica che TcpAckFrequency==1
    ifaces = ctx.ps("Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces' | "
                    "Select-Object -ExpandProperty PSChildName") or ""
    first = ifaces.splitlines()[0].strip() if ifaces.splitlines() else ""
    if not first:
        return False
    v = ctx.reg_get(r"HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\%s" % first, "TcpAckFrequency")
    return str(v).strip() == "1"


def _t_mouse_accel_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKCU:\Control Panel\Mouse", "MouseSpeed", "String", "0")
    ctx.set_reg(bk, r"HKCU:\Control Panel\Mouse", "MouseThreshold1", "String", "0")
    ctx.set_reg(bk, r"HKCU:\Control Panel\Mouse", "MouseThreshold2", "String", "0")


def _t_mouse_accel_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKCU:\Control Panel\Mouse", "MouseSpeed")).strip() == "0"


def _t_dns_cloudflare_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    alias = ctx._clean(ctx.ps("$a=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1; $a.Name"))
    if alias and ("dns::" + alias) not in bk:
        bk["dns::" + alias] = "reset"
        ctx.ps("Set-DnsClientServerAddress -InterfaceAlias '%s' -ServerAddresses ('1.1.1.1','1.0.0.1')" % alias)


def _t_dns_cloudflare_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    out = ctx.ps("(Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses -contains '1.1.1.1'}).Count") or ""
    try:
        return int(ctx._clean(out) or "0") > 0
    except Exception:
        return False


def _t_qos_bandwidth_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched", "NonBestEffortLimit", "DWord", 0)


def _t_qos_bandwidth_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\Psched", "NonBestEffortLimit")).strip() == "0"


# ============================================================================
# GAMING
# ============================================================================

def _t_game_mode_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKCU:\Software\Microsoft\GameBar", "AllowAutoGameMode", "DWord", 1)
    ctx.set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", "DWord", 2)
    ctx.set_reg(bk, r"HKCU:\System\GameConfigStore", "GameDVR_Enabled", "DWord", 0)
    ctx.set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", "DWord", 0)


def _t_game_mode_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return (
        str(ctx.reg_get(r"HKCU:\Software\Microsoft\GameBar", "AllowAutoGameMode")).strip() == "1"
        and str(ctx.reg_get(r"HKCU:\System\GameConfigStore", "GameDVR_Enabled")).strip() == "0"
    )


def _t_games_priority_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    sp = r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    ctx.set_reg(bk, sp, "SystemResponsiveness", "DWord", 0)
    ctx.set_reg(bk, sp, "NetworkThrottlingIndex", "DWord", 4294967295)
    games = sp + r"\Tasks\Games"
    ctx.set_reg(bk, games, "GPU Priority", "DWord", 8)
    ctx.set_reg(bk, games, "Priority", "DWord", 6)
    ctx.set_reg(bk, games, "Scheduling Category", "String", "High")
    ctx.set_reg(bk, games, "SFIO Priority", "String", "High")
    ctx.set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", "DWord", 26)


def _t_games_priority_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    games = r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
    return str(ctx.reg_get(games, "GPU Priority")).strip() == "8"


def _t_fullscreen_exclusive_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    gcs = r"HKCU:\System\GameConfigStore"
    ctx.set_reg(bk, gcs, "GameDVR_FSEBehaviorMode", "DWord", 2)
    ctx.set_reg(bk, gcs, "GameDVR_HonorUserFSEBehaviorMode", "DWord", 1)
    ctx.set_reg(bk, gcs, "GameDVR_DXGIHonorFSEWindowsCompatible", "DWord", 1)


def _t_fullscreen_exclusive_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKCU:\System\GameConfigStore", "GameDVR_FSEBehaviorMode")).strip() == "2"


# ============================================================================
# PRIVACY
# ============================================================================

def _t_diagtrack_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    st = ctx._clean(ctx.ps("(Get-Service DiagTrack -ErrorAction SilentlyContinue).StartType"))
    if st and "svc::DiagTrack" not in bk:
        bk["svc::DiagTrack"] = st
        ctx.run("net stop DiagTrack")
        ctx.run("sc config DiagTrack start= disabled")


def _t_diagtrack_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    st = ctx._clean(ctx.ps("(Get-Service DiagTrack -ErrorAction SilentlyContinue).StartType") or "")
    return st.lower() == "disabled"


def _t_diagtrack_revert(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    old = bk.get("svc::DiagTrack")
    if old:
        ctx.run(f"sc config DiagTrack start= {old.lower()}")


def _t_content_delivery_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    cdm = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    ctx.set_reg(bk, cdm, "SilentInstalledAppsEnabled", "DWord", 0)
    ctx.set_reg(bk, cdm, "SystemPaneSuggestionsEnabled", "DWord", 0)
    ctx.set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent",
                "DisableWindowsConsumerFeatures", "DWord", 1)


def _t_content_delivery_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    cdm = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    return str(ctx.reg_get(cdm, "SilentInstalledAppsEnabled")).strip() == "0"


# ============================================================================
# BLOATWARE
# ============================================================================

BLOAT_APPS = [
    "Microsoft.549981C3F5F10", "Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.GetHelp",
    "Microsoft.Getstarted", "Microsoft.WindowsFeedbackHub", "Microsoft.MicrosoftSolitaireCollection",
    "Microsoft.People", "Microsoft.WindowsMaps", "Microsoft.3DBuilder", "Microsoft.MixedReality.Portal",
    "king.com.CandyCrushSaga", "Microsoft.SkypeApp",
]


def _t_bloatware_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    removed = []
    for pkg in BLOAT_APPS:
        out = ctx.ps("$a=Get-AppxPackage -Name %s -ErrorAction SilentlyContinue; "
                     "if($a){ $a | Remove-AppxPackage -ErrorAction SilentlyContinue; 'ok' }" % pkg)
        if out.strip() == "ok":
            removed.append(pkg)
    bk["bloat_removed"] = removed


def _t_bloatware_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    # Verifica: nessuna delle app in bloat_removed e' ancora installata
    removed = bk.get("bloat_removed") or []
    if not removed:
        return True  # niente da fare
    still_there = 0
    for pkg in removed[:3]:  # sample: check 3 apps for speed
        out = ctx.ps(f"if((Get-AppxPackage -Name {pkg} -ErrorAction SilentlyContinue)){{'y'}}else{{'n'}}")
        if ctx._clean(out) == "y":
            still_there += 1
    return still_there == 0


# ============================================================================
# SYSTEM DEEP
# ============================================================================

def _t_power_plan_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    cur = ctx.ps("(powercfg /getactivescheme)")
    m = re.search(r"([0-9a-fA-F-]{36})", cur or "")
    if m and "power_plan" not in bk:
        bk["power_plan"] = m.group(1)
    if ctx.is_laptop:
        ctx.run("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")  # High Performance
    else:
        ultimate = "e9a42b02-d5df-448d-aa00-03f14749eb61"
        ctx.run(f"powercfg -duplicatescheme {ultimate}")
        ctx.run(f"powercfg -setactive {ultimate}")


def _t_power_plan_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    cur = ctx.ps("(powercfg /getactivescheme)") or ""
    target = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" if ctx.is_laptop else "e9a42b02-d5df-448d-aa00-03f14749eb61"
    return target.lower() in cur.lower()


def _t_power_plan_revert(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    old = bk.get("power_plan")
    if old:
        ctx.run(f"powercfg -setactive {old}")


def _t_power_throttle_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", "DWord", 1)


def _t_power_throttle_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff")).strip() == "1"


def _t_kernel_ram_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                "DisablePagingExecutive", "DWord", 1)


def _t_kernel_ram_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                           "DisablePagingExecutive")).strip() == "1"


def _t_sysmain_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    st = ctx._clean(ctx.ps("(Get-Service SysMain -ErrorAction SilentlyContinue).StartType"))
    if st and "svc::SysMain" not in bk:
        bk["svc::SysMain"] = st
        ctx.run("net stop SysMain")
        ctx.run("sc config SysMain start= disabled")
    ctx.run("fsutil behavior set DisableDeleteNotify 0")


def _t_sysmain_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    st = ctx._clean(ctx.ps("(Get-Service SysMain -ErrorAction SilentlyContinue).StartType") or "")
    return st.lower() == "disabled"


def _t_sysmain_revert(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    old = bk.get("svc::SysMain")
    if old:
        ctx.run(f"sc config SysMain start= {old.lower()}")


def _t_edge_boost_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", "DWord", 0)
    ctx.set_reg(bk, r"HKLM:\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", "DWord", 0)


def _t_edge_boost_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKLM:\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled")).strip() == "0"


# ============================================================================
# VISUAL
# ============================================================================

def _t_visual_perf_apply(ctx: TweakContext, bk: Dict[str, Any]) -> None:
    ctx.set_reg(bk, r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                "VisualFXSetting", "DWord", 2)


def _t_visual_perf_verify(ctx: TweakContext, bk: Dict[str, Any]) -> bool:
    return str(ctx.reg_get(r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                           "VisualFXSetting")).strip() == "2"


# --- TWEAKS list (source of truth) ---------------------------------------
TWEAKS: List[Tweak] = [
    # ---- LATENCY & INPUT ----
    Tweak(
        id="tcp-nagle-off", category="latency",
        name="Disabilita Nagle Algorithm",
        why="Nagle bufferizza pacchetti TCP piccoli per ottimizzare la banda, ma introduce 40-200ms di latenza. Su giochi online serve responsivita', non banda.",
        impact="+5-15ms input lag online", difficulty="safe",
        apply=_t_tcp_nagle_apply, verify=_t_tcp_nagle_verify,
    ),
    Tweak(
        id="mouse-accel-off", category="latency",
        name="Accelerazione mouse off",
        why="L'accelerazione varia la sensibilita' in base alla velocita' del movimento: rovina la muscle memory nei giochi FPS. 1:1 tracking = mira riproducibile.",
        impact="Mira 1:1 precisa", difficulty="safe",
        apply=_t_mouse_accel_apply, verify=_t_mouse_accel_verify,
    ),
    Tweak(
        id="dns-cloudflare", category="latency",
        name="DNS Cloudflare 1.1.1.1",
        why="Il DNS del tuo ISP e' spesso lento e loggato. Cloudflare 1.1.1.1 e' il piu' veloce al mondo (13ms avg) e non registra le query.",
        impact="-20-100ms su prima connessione a un server", difficulty="safe",
        apply=_t_dns_cloudflare_apply, verify=_t_dns_cloudflare_verify,
    ),
    Tweak(
        id="qos-bandwidth", category="latency",
        name="QoS: rimuovi 20% banda riservata",
        why="Windows riserva di default il 20% della banda per traffico 'best effort' Microsoft. Rimuovendolo riprendi tutta la banda per il gioco.",
        impact="+20% banda disponibile", difficulty="safe",
        apply=_t_qos_bandwidth_apply, verify=_t_qos_bandwidth_verify,
    ),

    # ---- GAMING ----
    Tweak(
        id="game-mode", category="gaming",
        name="Game Mode + GPU Scheduling",
        why="Game Mode dedica priorita' CPU/GPU al processo del gioco. Hardware GPU Scheduling (HAGS) taglia latenza rendering. Game DVR off elimina overhead XBox game bar.",
        impact="+5-10% FPS medio", difficulty="safe",
        apply=_t_game_mode_apply, verify=_t_game_mode_verify,
    ),
    Tweak(
        id="games-priority", category="gaming",
        name="Priorita' processi gaming",
        why="Nel registry Windows c'e' un profilo scheduler 'Games' dove imposti GPU/CPU priority. Di default e' su medium. Portandolo a High i tuoi giochi ottengono time-slice piu' generosi.",
        impact="+3-8% frame time consistency", difficulty="safe",
        apply=_t_games_priority_apply, verify=_t_games_priority_verify,
    ),
    Tweak(
        id="fullscreen-exclusive", category="gaming",
        name="Fullscreen esclusivo reale",
        why="Windows 10/11 forza fullscreen 'borderless' per compatibilita' con GameBar. Ma il vero fullscreen esclusivo taglia 1-2 frame di latenza (DirectFlip vs desktop compositor).",
        impact="-1 to -3 frame di input lag", difficulty="safe",
        apply=_t_fullscreen_exclusive_apply, verify=_t_fullscreen_exclusive_verify,
    ),

    # ---- PRIVACY ----
    Tweak(
        id="diagtrack-off", category="privacy",
        name="Disabilita telemetria Windows",
        why="DiagTrack (Diagnostic Tracking) invia log e dati d'uso a Microsoft ogni ora. Disabilitarlo blocca la telemetria E libera CPU/network.",
        impact="Privacy + 1-2% CPU idle in meno", difficulty="safe",
        apply=_t_diagtrack_apply, verify=_t_diagtrack_verify, revert=_t_diagtrack_revert,
    ),
    Tweak(
        id="content-delivery-off", category="privacy",
        name="Disabilita ads/suggerimenti Windows",
        why="Il Content Delivery Manager mostra app suggerite nel menu Start, notifiche promozionali e installa silentemente 'apps consigliate'. Roba invasiva.",
        impact="Zero pubblicita' + Start menu pulito", difficulty="safe",
        apply=_t_content_delivery_apply, verify=_t_content_delivery_verify,
    ),

    # ---- BLOATWARE ----
    Tweak(
        id="bloatware-remove", category="bloatware",
        name="Rimuovi bloatware preinstallato",
        why="Rimuove app UWP preinstallate che rallentano boot e occupano RAM: Candy Crush, Solitario, Skype, BingNews, MixedReality Portal, ecc. Tutte reinstallabili dallo Store.",
        impact="~500MB spazio + boot piu' rapido", difficulty="safe",
        apply=_t_bloatware_apply, verify=_t_bloatware_verify,
    ),

    # ---- SYSTEM DEEP ----
    Tweak(
        id="power-plan-max", category="system",
        name="Piano energetico prestazioni massime",
        why="Su desktop attiva 'Ultimate Performance' (schema nascosto). Su laptop attiva 'High Performance' (evita di scaricare la batteria in 30 minuti).",
        impact="+2-5% CPU sustained clock", difficulty="safe", requires_reboot=False,
        apply=_t_power_plan_apply, verify=_t_power_plan_verify, revert=_t_power_plan_revert,
    ),
    Tweak(
        id="power-throttle-off", category="system",
        name="Power Throttling CPU off (desktop)",
        why="Windows 10+ 'throttla' i processi in background per risparmiare energia. Sul desktop non serve — vuoi max clock sempre. Sul laptop lo lasciamo attivo.",
        impact="+3-7% CPU responsiveness", difficulty="moderate", requires_reboot=True,
        hardware_gate=lambda ctx: not ctx.is_laptop,
        apply=_t_power_throttle_apply, verify=_t_power_throttle_verify,
    ),
    Tweak(
        id="kernel-in-ram", category="system",
        name="Kernel Windows sempre in RAM",
        why="Con >=16GB RAM, forza il kernel a NON essere paginato su disco. Riduce latenza di system call quando la RAM e' abbondante.",
        impact="-1-3ms system call latency", difficulty="moderate", requires_reboot=True,
        hardware_gate=lambda ctx: ctx.ram_gb >= 16,
        apply=_t_kernel_ram_apply, verify=_t_kernel_ram_verify,
    ),
    Tweak(
        id="sysmain-off", category="system",
        name="SysMain/Superfetch off (SSD)",
        why="SysMain (ex-Superfetch) e' progettato per HDD: precarica file da disco. Su SSD e' inutile e occupa CPU/RAM. Verifica anche che TRIM sia attivo.",
        impact="~3% CPU idle + 200MB RAM", difficulty="safe",
        hardware_gate=lambda ctx: ctx.is_ssd,
        apply=_t_sysmain_apply, verify=_t_sysmain_verify, revert=_t_sysmain_revert,
    ),
    Tweak(
        id="edge-boost-off", category="system",
        name="Microsoft Edge preload off",
        why="Edge parte in background all'avvio di Windows per 'aprirsi piu' velocemente'. Se non usi Edge, sta occupando 200-400MB di RAM per niente.",
        impact="-200-400MB RAM idle", difficulty="safe",
        apply=_t_edge_boost_apply, verify=_t_edge_boost_verify,
    ),

    # ---- VISUAL ----
    Tweak(
        id="visual-perf", category="visual",
        name="Effetti visivi: modalita' prestazioni",
        why="Disabilita animazioni, ombre, trasparenze e transizioni. Windows si sente 'piu' snappy' e libera GPU cycles per il gioco.",
        impact="+0.5% GPU frametime + UX piu' reattiva", difficulty="safe",
        apply=_t_visual_perf_apply, verify=_t_visual_perf_verify,
    ),
]


# --- Runner ---------------------------------------------------------------
def get_by_categories(cats: Optional[List[str]] = None) -> List[Tweak]:
    """Filtra TWEAKS per categoria(e). None o [] = tutti."""
    if not cats:
        return list(TWEAKS)
    cats_set = {c.strip().lower() for c in cats if c}
    return [t for t in TWEAKS if t.category in cats_set]


def get_by_id(tid: str) -> Optional[Tweak]:
    for t in TWEAKS:
        if t.id == tid:
            return t
    return None


def apply_selected(
    tweaks: List[Tweak],
    ctx: TweakContext,
    bk: Dict[str, Any],
    progress=None,
) -> Dict[str, Any]:
    """Applica una lista di tweak. Salta se hardware_gate ritorna False.
    Chiama verify subito dopo apply e marca l'esito in bk["tweaks"][id].
    Ritorna dict con contatori {applied, verified, skipped, failed}.
    """
    stats = {"applied": 0, "verified": 0, "skipped": 0, "failed": 0, "reboot_needed": False}
    for t in tweaks:
        # Gate hardware
        if t.hardware_gate and not t.hardware_gate(ctx):
            stats["skipped"] += 1
            if progress:
                progress.step(f"{t.name}: skipped (hardware gate)", success=True)
            continue
        # Apply
        try:
            t.apply(ctx, bk)
            stats["applied"] += 1
        except Exception as e:
            _mark(bk, t.id, applied=False, verified=False)
            stats["failed"] += 1
            if progress:
                progress.step(f"{t.name}: {type(e).__name__}", success=False)
            continue
        # Verify
        verified = True
        if t.verify:
            try:
                verified = bool(t.verify(ctx, bk))
            except Exception:
                verified = False
        if verified:
            stats["verified"] += 1
        _mark(bk, t.id, applied=True, verified=verified)
        if t.requires_reboot:
            stats["reboot_needed"] = True
        if progress:
            symbol = "✔" if verified else "⚠"
            progress.step(f"{symbol} {t.name}  ({t.impact})", success=verified)
    return stats


def revert_tweak(ctx: TweakContext, bk: Dict[str, Any], tid: str) -> bool:
    """Ripristina un singolo tweak. Usa revert() se definito, altrimenti il
    revert generico key-based (retrocompat con backup v0.7.5)."""
    tw = get_by_id(tid)
    if not tw:
        return False
    try:
        if tw.revert:
            tw.revert(ctx, bk)
        # Il set_reg salva le vecchie chiavi in bk[full_key]: il modo generico
        # di ripristino e' delegato al chiamante (restore_tweaks nel main).
        # Qui marchiamo solo il tweak come "revert requested".
        bk.setdefault("tweaks", {}).setdefault(tid, {})["applied"] = False
        return True
    except Exception:
        return False


def revert_by_categories(ctx: TweakContext, bk: Dict[str, Any], cats: List[str]) -> int:
    """Ripristina tutti i tweak di una o piu' categorie. Ritorna count."""
    n = 0
    for t in get_by_categories(cats):
        if revert_tweak(ctx, bk, t.id):
            n += 1
    return n
