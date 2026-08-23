"""Il monitoraggio live: cosa gira una volta al secondo, per sempre.

Il meccanismo funzionava; i difetti stavano tutti in cio' che si ripete a ogni
campione - un binario eseguito senza controlli, uno stop che valeva per tutto
l'account, un documento da 1800 campioni letto per restituirne 60.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
_RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _leggi(*pezzi):
    with open(os.path.join(_RADICE, *pezzi), encoding="utf-8") as f:
        return f.read()


# ---------- 1. l'exe di PresentMon ----------

def test_presentmon_non_vive_piu_in_temp():
    """In %TEMP% scrive qualunque processo che gira come l'utente. E' la stessa
    ragione per cui il backup dell'agent non sta li'."""
    assert "$script:PM_EXE = Join-Path $FF_HOME 'PresentMon.exe'" in PS
    assert "Join-Path $env:TEMP 'PresentMon.exe'" not in PS


def test_si_esegue_solo_l_exe_che_abbiamo_scaricato_noi():
    """Prima bastava che un file con quel nome esistesse: veniva lanciato senza
    un solo controllo, e con l'agent elevato veniva lanciato elevato."""
    i = PS.index("function Confirm-PresentMon")
    corpo = PS[i:PS.index("function Start-Fps")]
    assert "Get-FileSha256 $script:PM_EXE) -eq $atteso" in corpo
    assert "Remove-Item $script:PM_EXE" in corpo, "un file che non corrisponde va buttato, non tenuto"
    avvio = PS[PS.index("function Start-Fps"):PS.index("function Stop-Fps")]
    assert "Confirm-PresentMon" in avvio
    assert "Invoke-WebRequest" not in avvio, "il download non deve tornare a vivere fuori dalla verifica"


def test_la_firma_si_racconta_ma_non_decide():
    """Se una release uscisse non firmata, gating sulla firma spegnerebbe la
    cattura FPS per tutti senza che nessuno capisca perche'."""
    i = PS.index("function Confirm-PresentMon")
    corpo = PS[i:PS.index("function Start-Fps")]
    assert "Get-AuthenticodeSignature" in corpo
    assert "senza firma valida" in corpo


# ---------- 2 e 3. lo stop ----------

def test_lo_stop_riguarda_un_pc_non_l_account():
    src = _leggi("backend", "routers", "pc.py")
    i = src.index('@r.post("/agent/telemetry")')
    corpo = src[i:src.index('@r.post("/monitor/stop")')]
    assert '"device_id": _did' in corpo, "il segnale di stop deve sapere di quale macchina si parla"
    for punto in ('async def monitor_stop', 'async def monitor_reset', 'async def monitor_state'):
        j = src.index(punto)
        assert "device_filter" in src[j:j + 700], "%s ragiona ancora per account" % punto


def test_il_flag_si_spegne_quando_l_agent_lo_legge():
    """Restava acceso finche' la pagina Live non chiamava /monitor/reset, quindi
    chi riavviava dal link copiato o dal comando manuale vedeva la finestra
    aprirsi e chiudersi al primo giro."""
    src = _leggi("backend", "routers", "pc.py")
    i = src.index('@r.post("/agent/telemetry")')
    corpo = src[i:src.index('@r.post("/monitor/stop")')]
    assert '"stop_requested": False, "acked_at"' in corpo


# ---------- 4, 5, 9. cosa costa un campione ----------

def test_si_leggono_i_campioni_che_servono():
    src = _leggi("backend", "routers", "pc.py")
    i = src.index('async def pc_telemetry')
    corpo = src[i:i + 900]
    assert '"samples": {"$slice": -_LIVE_SAMPLES}' in corpo
    assert "[-60:]" not in corpo, "il taglio in Python arriva dopo aver gia' trasferito tutto"


def test_l_etichetta_del_pc_si_cerca_solo_quando_serve():
    """Era una query al database ogni secondo per una stringa che serve quando
    un alert scatta davvero, cioe' quasi mai."""
    src = _leggi("backend", "routers", "pc.py")
    i = src.index("async def _check_temp_alerts")
    corpo = src[i:src.index('@r.get("/alerts")')]
    assert corpo.index("if not superate:") < corpo.index("db.devices.find_one")


def test_le_collezioni_interrogate_ogni_secondo_hanno_un_indice():
    src = _leggi("backend", "server.py")
    for coll in ("monitor_control", "alert_settings", "agent_launches"):
        assert "db.%s.create_index" % coll in src, "%s non ha indice" % coll


def test_la_traccia_dei_lanci_scade_da_sola():
    """Un indice TTL su una stringa non da' errore: semplicemente non cancella
    niente, e non se ne accorgerebbe nessuno."""
    src = _leggi("backend", "server.py")
    assert 'db.agent_launches.create_index("expires_at", expireAfterSeconds=0)' in src
    pc = _leggi("backend", "routers", "pc.py")
    assert '"expires_at": datetime.now(timezone.utc) + timedelta(days=1)' in pc


def test_il_tetto_dei_campioni_ha_un_nome_e_una_spiegazione():
    src = _leggi("backend", "routers", "pc.py")
    assert "_TELEMETRY_KEEP = 1800" in src
    assert "$slice\": -_TELEMETRY_KEEP" in src
    assert "Gameplay Doctor" in src[src.index("_TELEMETRY_KEEP = 1800") - 700:src.index("_TELEMETRY_KEEP = 1800")]


# ---------- 6 e 7. la pagina ----------

def test_la_pagina_rallenta_quando_non_c_e_niente():
    src = _leggi("frontend", "src", "pages", "Live.jsx")
    assert "POLL_FERMO_MS" in src
    assert "pianifica(data?.live ? POLL_LIVE_MS : POLL_FERMO_MS)" in src


def test_l_insieme_dei_campioni_visti_viene_potato():
    src = _leggi("frontend", "src", "pages", "Live.jsx")
    assert "seenRef.current.size > 300" in src


# ---------- il gioco mostrato e' quello misurato? ----------

def test_get_fps_si_legge_una_volta_sola_per_giro():
    """Get-Fps CONSUMA le righe nuove di PresentMon e sposta il segnalibro: due
    chiamate nello stesso secondo e la seconda trova il vuoto. Il ciclo del
    monitor ne faceva due - una dentro il rilevatore del gioco, che teneva solo
    il nome e buttava FPS, latenza e frametime, e una qui - quindi nel ramo in
    cui il rilevatore arriva a PresentMon il campione partiva con il nome del
    gioco e senza una sola misura."""
    i = PS.index("if ($MODE -eq 'monitor')")
    ciclo = PS[i:PS.index("if ($MODE -eq 'prematch')", i)]
    chiamate = [r for r in ciclo.splitlines() if "Get-Fps" in r and not r.strip().startswith("#")]
    assert len(chiamate) == 1, "il ciclo del monitor legge Get-Fps piu' di una volta: %s" % chiamate
    assert "Get-TelemetrySample $f $true" in ciclo, "il risultato gia' letto va passato, non riletto"


def test_il_rilevatore_non_rilegge_se_gli_e_stato_dato():
    i = PS.index("function Get-CurrentGame")
    corpo = PS[i:PS.index("function Get-TelemetrySample")]
    assert "if (-not $fpsGiaLetto) { $f = Get-Fps }" in corpo


def test_anche_la_live_sync_non_butta_i_frame():
    i = PS.index("function Push-LiveSample")
    corpo = PS[i:PS.index("# ---------------- FPS via PresentMon")]
    assert "Get-TelemetrySample $f $true" in corpo
    assert "Add-FpsToSample" in corpo


def test_chi_disegna_di_piu_non_e_automaticamente_un_gioco():
    """PresentMon riporta ogni processo che presenta. Senza filtro, con nessun
    gioco aperto il vincitore era il browser, e da li' finiva nel campo `game`,
    nella card degli FPS e fra i "giochi rilevati" dei trofei."""
    i = PS.index("function Get-Fps")
    corpo = PS[i:PS.index("function Get-HistBucket") if "function Get-HistBucket" in PS[i:] else i + 6000]
    assert "$script:NON_GIOCHI" in corpo
    assert "if ($giochi.Count -eq 0) { return $null }" in corpo, \
        "senza giochi la risposta e' 'niente FPS', non 'il primo processo disponibile'"


def test_la_lista_dei_non_giochi_e_una_sola():
    """Esisteva in due copie dentro i rilevatori e non era applicata a Get-Fps."""
    assert PS.count("$script:NON_GIOCHI = ") == 1
    assert PS.count("$skipRe = ") == 0, "una copia locale della lista e' tornata"
    assert PS.count("$script:NON_GIOCHI") >= 4


def test_l_istogramma_appartiene_a_un_applicazione():
    """1% e 0.1% low si calcolano sull'istogramma cumulativo di sessione: i
    frametime di due applicazioni diverse non stanno nella stessa distribuzione."""
    i = PS.index("function Get-Fps")
    corpo = PS[i:i + 6000]
    assert "$script:GD_APP -ne $top.Key" in corpo
    assert "$script:GD_HIST = $null" in corpo


def test_la_pagina_dichiara_quando_i_due_nomi_non_coincidono():
    """Nome del gioco e FPS arrivano da due catene indipendenti."""
    card = _leggi("frontend", "src", "components", "CurrentGameCard.jsx")
    assert "fpsApp" in card and "stessoProcesso" in card
    assert "game_fps_mismatch" in card
    live = _leggi("frontend", "src", "pages", "Live.jsx")
    assert "fpsApp={last.game}" in live
