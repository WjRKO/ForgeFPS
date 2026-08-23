"""L'Auto-Pilot non applica tweak che hanno effetto solo dopo il riavvio.

L'Auto-Pilot misura la salute, applica, aspetta due secondi e rimisura. Un tweak
che si attiva al riavvio non puo' stare in quel ciclo: verrebbe applicato,
contato fra gli applicati e messo in un confronto prima/dopo in cui non era
ancora attivo. Il rapporto ne uscirebbe piu' povero proprio dei tweak di latenza
- `gpu_msi`, `timer`, `mpo` - e l'utente resterebbe con un riavvio in sospeso
che nessuno gli ha detto.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent
import tweak_catalog

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML

RIAVVIO = {"mpo", "gpu_msi", "timer", "nic_power"}


def _ciclo_autopilot():
    i = PS.index("if ($MODE -eq 'autopilot'")
    return PS[i:PS.index("Save-Backup", i)]


def test_quali_tweak_richiedono_un_riavvio():
    """Elenco fissato: cambiarlo cambia cosa fa l'Auto-Pilot su ogni PC, quindi
    e' una decisione, non un dettaglio da correggere di passaggio."""
    assert {t["id"] for t in tweak_catalog.TWEAKS if t["requires_reboot"]} == RIAVVIO


def test_il_ciclo_li_salta_prima_di_applicare():
    ciclo = _ciclo_autopilot()
    salto = ciclo.index("if ($t.requires_reboot)")
    assert salto < ciclo.index("Invoke-ApplyTracked"), "il salto arriva dopo l'apply: non serve a niente"
    assert "$__apRinviati += $t.name" in ciclo


def test_l_utente_viene_avvisato_di_cosa_e_rimasto_fuori():
    """Esclusi, non spariti: restano applicabili dalla GUI, dove il riavvio si
    puo' chiedere. Un tweak che scompare senza una riga e' un tweak che l'utente
    crede applicato."""
    i = PS.index("if ($MODE -eq 'autopilot'")
    blocco = PS[i:PS.index("[AUTO-PILOT] {0} tweak applicati", i)]
    assert "$__apRinviati.Count -gt 0" in blocco
    assert "Applicali dalla GUI" in blocco


def test_il_criterio_e_il_riavvio_non_il_rischio():
    """`mpo`, `gpu_msi` e `timer` sono 'safe' per l'agent e passavano il filtro
    del rischio: e' proprio per questo che serviva un campo separato."""
    for tid in ("mpo", "gpu_msi", "timer", "nic_power"):
        t = tweak_catalog.by_id(tid)
        assert tweak_catalog.agent_risk(t) == "safe", tid
        assert t["requires_reboot"] is True, tid


def test_il_booleano_non_passa_dalla_stringa():
    """In PowerShell `[bool]'False'` e' $true: interpolare un campo booleano in
    una stringa lo rende vero per sempre, e il filtro escluderebbe tutto."""
    i = PS.index("$script:TWMETA = @{}")
    merge = PS[i:PS.index("$script:TWEAKS = $__twOk", i)]
    assert "$__t['requires_reboot'] = [bool]$__meta.requires_reboot" in merge
    interpolati = re.search(r"foreach \(\$__k in @\(([^)]*)\)\)", merge).group(1)
    assert "requires_reboot" not in interpolati, "il campo e' finito fra quelli interpolati come stringa"


def test_il_campo_arriva_fino_alla_gui():
    """La GUI deduceva il riavvio cercando 'richiede riavvio' nella prosa del
    tweak: funzionava per coincidenza, e una riscrittura del testo avrebbe
    spento in silenzio il filtro, la pillola e il dialogo di fine lavoro."""
    dto = PS[PS.index("function Get-TweakDto"):PS.index("return $arr", PS.index("function Get-TweakDto"))]
    assert "requires_reboot = [bool]$t.requires_reboot" in dto
    fn = GUI[GUI.index("function needsReboot"):]
    fn = fn[:fn.index("\n  }")]
    assert 'typeof t.requires_reboot === "boolean"' in fn
    assert "richiede" in fn, "il ripiego a regex serve agli agent che non inviano il campo"
