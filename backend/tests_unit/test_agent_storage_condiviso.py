"""Un solo backup e un solo journal, per tutti e due gli agent.

FrameForge ha due motori: l'.exe Python (modi da riga di comando) e lo script
PowerShell (finestra e bottoni della dashboard). Hanno cataloghi di tweak
diversi — qui 'tcp-nagle-off', di la' 'network' — ma scrivono le stesse chiavi
di registro, nello stesso formato. Tenevano pero' due file di backup separati e
non comunicanti, per giunta uno accanto all'.exe: "Ripristina" da riga di
comando non annullava quello che aveva fatto la finestra, e viceversa.

"Cosa mi hai fatto al PC" non puo' avere due risposte diverse a seconda di come
si e' aperto il programma.

Il test gira sul sorgente dei due agent: l'unione vera e' verificata a runtime
(percorsi, metadati preservati, journal condiviso) da
tests/prova_storage_condiviso.py, che si lancia a mano su Windows: importa un
modulo che parla col registro, quindi non puo' girare in CI.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML

_EXE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "agent-build", "forgefps_agent.py")
EXE = io.open(_EXE, encoding="utf-8").read()


# ---------- lo stesso posto ----------

def test_i_due_agent_scrivono_nella_stessa_cartella():
    assert '_FF_HOME = os.path.join(os.environ.get("APPDATA") or tempfile.gettempdir(), "FrameForge")' in EXE
    assert '$FF_HOME = if ($env:APPDATA) { Join-Path $env:APPDATA \'FrameForge\' }' in PS


def test_lo_stesso_backup_e_lo_stesso_journal():
    assert 'BACKUP_FILE = os.path.join(_FF_HOME, "backup.json")' in EXE
    assert "$BACKUP  = Join-Path $FF_HOME 'backup.json'" in PS
    assert 'JOURNAL_FILE = os.path.join(_FF_HOME, "journal.jsonl")' in EXE
    assert "$JOURNAL = Join-Path $FF_HOME 'journal.jsonl'" in PS


def test_il_backup_non_sta_piu_accanto_all_exe():
    """Se l'exe e' in Program Files quella cartella non e' scrivibile, se sta in
    Download sparisce col primo riordino, e ogni reinstallazione ci passa sopra:
    era il file piu' fragile del prodotto, e serve ad annullare le modifiche."""
    assert "_BACKUP_DIR = os.path.dirname(os.path.abspath(__file__))" not in EXE
    assert "_OLD_BACKUPS = [" in EXE


def test_i_backup_vecchi_si_fondono_invece_di_essere_abbandonati():
    """Chi aggiorna ha modifiche registrate nel file di prima: ignorarlo
    vorrebbe dire renderle non annullabili da un giorno all'altro."""
    i = EXE.index("def _load_backup")
    corpo = EXE[i:EXE.index("def _save_backup")]
    assert "for old in _OLD_BACKUPS:" in corpo
    assert "if k not in bk:" in corpo, "il piu' recente non va sovrascritto dal piu' vecchio"


def test_il_vecchio_si_cancella_solo_dopo_aver_scritto_il_nuovo():
    i = EXE.index("def _save_backup")
    corpo = EXE[i:EXE.index("def _journal(")]
    assert corpo.index("json.dump(bk, f, indent=2)") < corpo.index("os.remove(old)")


# ---------- ognuno rispetta i dati dell'altro ----------

def test_i_metadati_dell_altro_motore_sopravvivono():
    """__tweak_keys__ e __applied_at__ sono cio' che permette di annullare un
    singolo tweak dalla finestra: se l'exe li perdesse riscrivendo il file,
    resterebbe solo il ripristino totale."""
    assert '_META_KEYS = ("__tweak_keys__", "__applied_at__", "tweaks")' in EXE
    i = EXE.index("def _save_backup")
    assert "json.dump(bk, f, indent=2)" in EXE[i:EXE.index("def _journal(")]


def test_il_ripristino_non_tratta_i_metadati_come_chiavi():
    """Prima finivano nel ramo generico e producevano comandi `reg add` su
    percorsi inventati, che fallivano in silenzio."""
    i = EXE.index("def restore_tweaks")
    corpo = EXE[i:EXE.index("def _menu_logout")]
    assert "if k in _META_KEYS:" in corpo
    assert "continue" in corpo


def test_ripristinare_annulla_anche_quello_che_ha_fatto_la_finestra():
    """E' il punto dell'unione: le chiavi le scrivono tutti e due nello stesso
    formato, quindi un ripristino solo le rimette tutte."""
    i = EXE.index("def restore_tweaks")
    corpo = EXE[i:EXE.index("def _menu_logout")]
    assert 'for _tid in list((bk.get("__tweak_keys__") or {}).keys()):' in corpo
    assert '_journal("revert"' in corpo


def test_nessun_backup_non_e_piu_una_risposta_ambigua():
    i = EXE.index("def restore_tweaks")
    corpo = EXE[i:EXE.index("def _menu_logout")]
    assert "if not [k for k in bk if k not in _META_KEYS]:" in corpo
    assert "non ha modifiche da annullare su questo PC" in corpo


# ---------- una cronologia sola ----------

def test_anche_la_riga_di_comando_scrive_nel_journal():
    """Quella schermata dice di essere il registro completo: se meta' delle
    azioni non ci finisse, non lo sarebbe."""
    assert "def _journal(event, tweak_id, name, cat, ok, err=" in EXE
    assert "def _journal_esiti(" in EXE
    assert "_journal_esiti(selected, bk)" in EXE
    assert "_journal_esiti([one], bk)" in EXE


def test_il_journal_riporta_il_verdetto_vero_non_un_totale():
    """Il Recipe System gia' verifica ogni tweak dopo averlo applicato: la
    cronologia riporta quel verdetto invece di 'n applicati'."""
    i = EXE.index("def _journal_esiti")
    corpo = EXE[i:EXE.index("def _reg_cli_path")]
    assert 'esiti.get(t.id)' in corpo
    assert "applicato ma la verifica non conferma il valore atteso" in corpo


def test_la_cronologia_dice_da_quale_motore_arriva_una_riga():
    """Senza, sembrerebbe che la finestra abbia fatto cose che non ha fatto."""
    assert '"via": "cli",' in EXE
    assert 'via = "$($r.via)"' in PS
    assert 'e.via === "cli"' in GUI


def test_un_journal_che_non_si_scrive_non_ferma_niente():
    i = EXE.index("def _journal(event")
    corpo = EXE[i:EXE.index("def _journal_esiti")]
    assert "except Exception:" in corpo
    assert "pass" in corpo
