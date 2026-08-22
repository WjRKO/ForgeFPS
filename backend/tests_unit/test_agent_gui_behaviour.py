"""Comportamenti della GUI locale: fallback, cronologia delle modifiche, tastiera.

Tre cose che si perdono facilmente in un refactor e che nessuno si accorge
siano sparite finche' non servono a un utente reale.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML


# ---------- fallback della GUI: misurato, non indovinato ----------

def test_il_server_locale_viene_ritentato_prima_di_arrendersi():
    """La porta la sceglie il sistema e viene rilasciata un istante prima di
    legarla: l'unica causa plausibile di fallimento e' che qualcuno l'abbia
    presa in quella finestra, e ritentare costa niente."""
    assert "foreach ($try in 1, 2)" in PS
    assert "riprovo su un altra porta" in PS


def test_il_fallback_dichiara_il_motivo():
    """Prima diceva solo 'interfaccia web non disponibile': l'utente restava
    con una GUI diversa e nessuna idea del perche'."""
    assert 'Say-Warn ("Interfaccia web non disponibile: {0}" -f $guiErr)' in PS
    assert "ha meno funzioni della finestra normale" in PS


def test_il_fallback_viene_registrato():
    """Serve a decidere con i dati se la GUI classica valga le 451 righe che
    costa, invece di cancellarla o tenerla a intuito."""
    assert "Send-AgentDiag 'gui_web_failed'" in PS
    assert "function Send-AgentDiag" in PS
    assert "/api/agent/diag" in PS


def test_la_diagnostica_non_interrompe_mai_l_utente():
    """Una diagnostica che blocca o disturba e' peggio del problema che misura."""
    i = PS.index("function Send-AgentDiag")
    corpo = PS[i:PS.index("function Send-Data", i)]
    assert "} catch {}" in corpo and "Out-Null" in corpo


# ---------- cronologia delle modifiche ----------

def test_il_momento_dell_applicazione_viene_registrato():
    """Il backup sapeva gia' cosa era stato cambiato e come annullarlo, ma non
    quando: senza, la cronologia non si puo' raccontare."""
    assert "$script:TWAT[$t.id] = (Get-Date).ToString('o')" in PS


def test_il_momento_sopravvive_alla_chiusura_dell_agent():
    assert "$__out['__applied_at__'] = $script:TWAT" in PS
    assert "$script:BK.ContainsKey('__applied_at__')" in PS


def test_annullare_un_tweak_ne_dimentica_la_data():
    i = PS.index("function Invoke-RestoreTweak")
    corpo = PS[i:PS.index("\n}", i)]
    assert "$script:TWAT.Remove($id)" in corpo


def test_esiste_l_endpoint_della_cronologia():
    """Era /api/changes, che ricostruiva la cronologia dal file di backup e
    quindi sapeva solo cosa e' modificato ADESSO. Ora la cronologia e' un file
    suo (vedi test_agent_journal.py) e l'endpoint la serve per sessioni."""
    assert "$path -eq '/api/journal'" in PS
    assert "$path -eq '/api/changes'" not in PS
    # il valore precedente va mostrato in chiaro, non come '__ABSENT__'
    assert "'non esisteva'" in PS


def test_la_gui_ha_la_scheda_delle_modifiche():
    assert '{ key: "journal",  label: "Journal" }' in GUI
    assert "function renderJournalTab" in GUI
    assert "loadJournal" in GUI


def test_annullare_invalida_la_cronologia_in_memoria():
    """Altrimenti la scheda continua a mostrare un tweak appena rimosso."""
    assert "state.journal = null;" in GUI


def test_la_scheda_dice_dove_sta_il_backup():
    """La reversibilita' va mostrata, non promessa: il file e' verificabile."""
    assert 'data-testid="journal-file"' in GUI
    assert 'file = "$JOURNAL"' in PS


# ---------- tastiera e token ----------

def test_il_token_non_viaggia_nell_url():
    assert '$localUrl = "http://127.0.0.1:$port/"' in PS
    assert "?tk=$sessionToken" not in PS


def test_la_pagina_ripulisce_comunque_la_barra_degli_indirizzi():
    assert 'location.search.indexOf("tk=")' in GUI
    assert "history.replaceState" in GUI


def test_il_focus_da_tastiera_e_visibile():
    """Un click sbagliato qui modifica il registro di Windows: sapere dove si
    trova il focus conta piu' della media."""
    assert "button:focus-visible" in GUI
    # e nessuno deve poi spegnerlo di nuovo
    assert ":focus-visible { background: rgba(0, 224, 255, 0.08); outline: none; }" not in GUI


def test_le_schede_sono_una_tablist():
    assert 'role="tablist"' in GUI
    assert 'role="tab" aria-selected=' in GUI
