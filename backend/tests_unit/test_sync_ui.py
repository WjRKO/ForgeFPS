"""Il sync silent: una voce sola, un'attesa sola, nessuna euristica morta.

Il pulsante "Sincronizza ora" e il badge di freschezza nell'header lanciano la
stessa operazione da due punti diversi. Finche' ognuno teneva le proprie
stringhe e il proprio timeout, "la stessa operazione" era un modo di dire: il
badge mostrava i default italiani dell'hook anche in inglese, perche' chiedeva
silenzio con stringhe vuote e `""` e' falso in JavaScript.

Questi test guardano il sorgente del frontend come fa gia'
test_agent_distribution.py: non sostituiscono una suite JS, impediscono il
ritorno di difetti precisi.
"""
import os
import re

import pytest

_RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC = os.path.join(_RADICE, "frontend", "src")


def _leggi(*pezzi):
    percorso = os.path.join(_SRC, *pezzi)
    if not os.path.exists(percorso):
        pytest.skip("frontend non presente")
    with open(percorso, encoding="utf-8") as f:
        return f.read()


def _chiavi_mypcpage():
    """I nomi di chiave dentro i due blocchi `mypcpage:` di i18n.js (it, en)."""
    src = _leggi("i18n.js")
    blocchi = []
    for m in re.finditer(r"\n      mypcpage: \{\n", src):
        i = m.end()
        fine = src.index("\n      },\n", i)
        blocchi.append(set(re.findall(r"^\s{8}(\w+):", src[i:fine], re.M)))
    return blocchi


def test_le_due_lingue_hanno_le_stesse_chiavi():
    """Una chiave aggiunta solo in italiano non da' errore: mostra il testo
    italiano a chi ha l'app in inglese, che e' il difetto che si voleva togliere."""
    blocchi = _chiavi_mypcpage()
    assert len(blocchi) == 2, "attesi due blocchi mypcpage (it, en), trovati %d" % len(blocchi)
    solo_it = blocchi[0] - blocchi[1]
    solo_en = blocchi[1] - blocchi[0]
    assert not solo_it and not solo_en, "chiavi sbilanciate - solo it: %s, solo en: %s" % (sorted(solo_it), sorted(solo_en))


def test_esistono_le_chiavi_che_spiegano_un_fallimento():
    """Il timeout non e' una causa: servono le frasi per distinguere i casi."""
    for chiave in ("sync_wrong_device", "sync_switch_to", "sync_switched",
                   "sync_launch_failed", "sync_limit_hint", "sync_cancel", "sync_cancelled"):
        for blocco in _chiavi_mypcpage():
            assert chiave in blocco, "manca %s in una delle due lingue" % chiave


def test_una_etichetta_vuota_vuol_dire_silenzio():
    """`labels.starting || default` rende impossibile chiedere silenzio: `""` e'
    falso, quindi chi lo passava riceveva il default. Il badge lo faceva."""
    src = _leggi("hooks", "useSilentLaunch.js")
    assert "labels[k] !== undefined" in src
    assert not re.search(r"labels\.\w+\s*\|\|", src), "risoluzione etichette di nuovo con ||"


def test_l_euristica_del_focus_non_torna():
    """Cercava di indovinare "agent non installato" dal fatto che la tab non
    perdesse il focus. In modalita' silent l'agent non prende MAI il focus,
    quindi il segnale era invertito - e il ramo era comunque vuoto."""
    for percorso in (("hooks", "useSilentLaunch.js"), ("components", "OneClickLaunchButton.jsx")):
        src = _leggi(*percorso)
        assert "initialVis" not in src, "%s ha di nuovo l'euristica sul focus" % "/".join(percorso)


def test_il_timeout_del_sync_e_dichiarato_una_volta_sola():
    src = _leggi("lib", "syncLabels.js")
    assert "export const SYNC_TIMEOUT_MS" in src
    for percorso in (("pages", "MyPc.jsx"), ("hooks", "useAutoSync.js")):
        altro = _leggi(*percorso)
        assert "SYNC_TIMEOUT_MS" in altro, "%s non usa il timeout condiviso" % "/".join(percorso)
        assert not re.search(r"SYNC_TIMEOUT_MS\s*=\s*\d", altro), "%s ridichiara il timeout" % "/".join(percorso)


def test_i_due_punti_di_lancio_usano_le_stesse_etichette():
    """Il pulsante e il badge: se uno dei due torna a scriversi le stringhe in
    casa, torna anche la possibilita' che divergano."""
    for percorso in (("pages", "MyPc.jsx"), ("components", "FreshnessBadge.jsx")):
        src = _leggi(*percorso)
        assert "syncLabels" in src, "%s non usa le etichette condivise" % "/".join(percorso)


def test_la_diagnosi_guarda_tutti_i_pc_non_solo_quello_attivo():
    """/pc-specs legge il device ATTIVO, ma l'agent scrive sul PC su cui gira:
    se sono diversi il sync riesce e la pagina non lo vede. Senza confrontare
    tutti i PC, quel successo veniva riportato come fallimento."""
    src = _leggi("pages", "MyPc.jsx")
    assert "/devices/compare" in src
    assert "specs_updated_at" in src
    assert "/activate" in src, "manca il rimedio: attivare il PC che ha davvero sincronizzato"


# ---------- cosa fa il pulsante quando riesce ----------

# I pannelli di "Il mio PC" che leggono dal backend una volta sola, al mount.
_PANNELLI = ("DevicesPanel", "DeviceCompare", "HwInsightsPanel",
             "HealthHistoryCard", "WhatChangedCard", "SyncTimeline")


def test_dopo_un_sync_si_aggiorna_tutta_la_pagina():
    """Il sync aggiornava due pannelli su sei. Gli altri quattro leggevano al
    mount e restavano fermi: si attivava XMP nel BIOS, si sincronizzava, e la
    griglia mostrava la RAM nuova con sotto il cartello "attiva XMP". Il grafico
    dei sync non conteneva nemmeno il sync appena fatto."""
    src = _leggi("pages", "MyPc.jsx")
    assert "const [syncVersion, setSyncVersion]" in src
    for nome in _PANNELLI:
        assert re.search(r"<%s\s+key=\{" % nome, src), "%s non si rimonta dopo il sync" % nome
    assert src.count("setSyncVersion((v) => v + 1)") >= 2, \
        "il contatore va alzato sia dopo il sync sia dopo il cambio di PC attivo"


def test_il_successo_dice_cosa_e_cambiato():
    """"Sync completato" e' vero e non dice niente. Il diff fra due sync il
    backend lo calcola gia' e lo salva in system_changes: il toast lo cita."""
    hook = _leggi("hooks", "useSilentLaunch.js")
    assert "summarize" in hook, "l'hook non sa raccontare il ramo riuscito"
    src = _leggi("pages", "MyPc.jsx")
    assert "summarize:" in src
    assert "/pc/changes" in src
    for chiave in ("sync_changed", "sync_changed_more", "sync_no_changes"):
        for blocco in _chiavi_mypcpage():
            assert chiave in blocco, "manca %s in una delle due lingue" % chiave


def test_nessuna_modifica_e_una_risposta_non_un_silenzio():
    """Il caso piu' comune e' che non sia cambiato niente: dirlo evita il dubbio
    di aver premuto invano."""
    src = _leggi("pages", "MyPc.jsx")
    assert "sync_no_changes" in src


def test_i_due_pulsanti_non_si_somigliano_piu():
    """Nella barra c'erano "Sincronizza ora" (accende l'agent, un minuto) e
    "Aggiorna" (rilegge il database, un istante) con la STESSA icona, uno
    accanto all'altro. Ora il secondo sta attaccato all'ora dell'ultimo sync,
    dove il suo significato si capisce da solo."""
    src = _leggi("pages", "MyPc.jsx")
    i = src.index("actions={<>")
    barra = src[i:src.index("</>} />", i)]
    assert "silent-sync-btn" in barra
    assert "refresh-pc-btn" not in barra, "il secondo RefreshCw e' tornato nella barra"
    assert "refresh-pc-btn" in src, "il ricarica manuale non deve sparire, solo spostarsi"


def test_le_etichette_dei_cambiamenti_stanno_in_un_posto_solo():
    """Le mostrano sia la card "Cosa e' cambiato" sia il toast del sync."""
    assert "export function changeLabel" in _leggi("lib", "changeLabels.js")
    card = _leggi("components", "WhatChangedCard.jsx")
    assert "changeLabel" in card
    assert "const LABELS = {" not in card, "la mappa e' tornata a vivere in due posti"


# ---------- provenienza per campo ----------

def test_la_pagina_dichiara_i_campi_non_confermati():
    """data_meta serve a distinguere "vecchio" da "sparito": se poi la pagina
    mostra i due casi identici, la distinzione resta solo nel database."""
    src = _leggi("pages", "MyPc.jsx")
    assert "function nonConfermato" in src
    assert "data_meta" in src
    assert "spec_stale" in src


def test_le_chiavi_del_marcatore_esistono_in_entrambe_le_lingue():
    for chiave in ("spec_stale", "spec_stale_title"):
        for blocco in _chiavi_mypcpage():
            assert chiave in blocco, "manca %s in una delle due lingue" % chiave


# ---------- il PC di questa postazione ----------

def test_il_lancio_lascia_una_traccia_e_il_report_la_lega():
    """Il browser non puo' sapere da solo quale PC e' il suo agent: `/pc-specs`
    legge il device attivo, scelto a mano. Il legame si impara per correlazione."""
    percorso = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routers", "pc.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()
    assert "agent_launches" in src
    assert '"launch_id": launch_id' in src
    assert "_bind_launch_device" in src
    i = src.index("async def _bind_launch_device")
    corpo = src[i:src.index("\n    @r.post", i)]
    assert "len(aperti) != 1" in corpo, \
        "con due lanci aperti non si puo' dire quale abbia risposto: attribuirne uno a caso rifa' il messaggio falso"


def test_la_pagina_impara_e_mette_a_fuoco_il_pc_locale():
    src = _leggi("pages", "MyPc.jsx")
    assert "ff_local_device" in src, "il PC locale deve restare noto fra una visita e l'altra"
    assert "/agent/launch/" in src, "senza leggere chi ha risposto non si impara niente"
    assert "sync_focus_local" in src
    i = src.index("beforeLaunch:")
    prima = src[i:src.index("detectDone:", i)]
    assert "/activate" in prima, "la messa a fuoco deve avvenire PRIMA del lancio, non dopo il timeout"


def test_le_chiavi_della_messa_a_fuoco_esistono_in_entrambe_le_lingue():
    for blocco in _chiavi_mypcpage():
        assert "sync_focus_local" in blocco
