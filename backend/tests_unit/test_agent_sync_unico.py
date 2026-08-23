"""Una sola rilevazione hardware, per tutti i modi di avviare l'agent.

La stessa rilevazione esisteva in tre implementazioni che scrivevano sugli
stessi endpoint con qualita' diversa: lo script PowerShell servito dal backend
(la buona), l'exe di `agent-build/` e lo script `.py` scaricabile da "FrameForge
Agent". Le ultime due prendevano il refresh dal massimo fra i controller invece
che dallo schermo primario, la risoluzione dal primo controller della lista
grezza, la RAM dal primo modulo, e non mandavano ne' `hw_confidence` ne' le
temperature via LibreHardwareMonitor.

Quale girasse dipendeva da COME era stato avviato l'agent, quindi lo stesso PC
scriveva specs diverse nello stesso documento senza che niente lo segnalasse.
Questi test impediscono che una seconda rilevazione ritorni.
"""
import ast
import os
import re

import pytest

_RADICE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_EXE = os.path.join(_RADICE, "agent-build", "forgefps_agent.py")
_PY = os.path.join(_RADICE, "backend", "desktop_agent.py")

_MORTI = ("collect_specs", "collect_health", "collect_startup", "send_all")


def _sorgente_exe():
    if not os.path.exists(_EXE):
        pytest.skip("sorgente dell'exe non presente")
    with open(_EXE, encoding="utf-8") as f:
        return f.read()


def _sorgente_py():
    """Lo script scaricabile vive dentro una stringa in desktop_agent.py."""
    with open(_PY, encoding="utf-8") as f:
        esterno = f.read()
    apertura = "AGENT_SCRIPT = r'''"
    i = esterno.index(apertura) + len(apertura)
    return esterno[i:esterno.rindex("'''")]


def _funzioni(src):
    return {n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}


# ---------- vale per entrambi gli agent ----------

@pytest.mark.parametrize("nome,sorgente", [("exe", _sorgente_exe), ("py", _sorgente_py)])
def test_nessun_agent_ha_una_rilevazione_sua(nome, sorgente):
    presenti = _funzioni(sorgente()) & set(_MORTI)
    assert not presenti, "%s: %s sono tornati, due rilevazioni scrivono sullo stesso documento" % (nome, sorted(presenti))


@pytest.mark.parametrize("nome,sorgente", [("exe", _sorgente_exe), ("py", _sorgente_py)])
def test_lo_script_si_scarica_da_un_posto_solo(nome, sorgente):
    src = sorgente()
    assert "_download_agent_script" in _funzioni(src)
    assert src.count("/api/agent/script?t=") == 1, \
        "%s: la richiesta dello script e' di nuovo copiata in piu' punti" % nome


@pytest.mark.parametrize("nome,sorgente", [("exe", _sorgente_exe), ("py", _sorgente_py)])
def test_il_sync_aspetta_la_fine(nome, sorgente):
    """I lanciatori esistenti tornano subito: usarli qui farebbe stampare
    "Premi INVIO per chiudere" mentre lo script sta ancora partendo."""
    src = sorgente()
    assert "run_ps_mode_inline" in _funzioni(src)
    i = src.index("def run_ps_mode_inline")
    corpo = src[i:src.index("\ndef ", i + 1)]
    assert "subprocess.call(" in corpo, "%s: il lancio deve essere sincrono" % nome
    assert "Popen" not in corpo


@pytest.mark.parametrize("nome,sorgente", [("exe", _sorgente_exe), ("py", _sorgente_py)])
def test_l_agent_resta_compilabile(nome, sorgente):
    """Un NameError da funzione rimossa si vede solo eseguendo."""
    compile(sorgente(), "<%s>" % nome, "exec")


# ---------- specifici ----------

def test_il_sync_da_riga_di_comando_dell_exe_passa_dallo_script():
    src = _sorgente_exe()
    i = src.index('if _args.mode == "sync":')
    assert 'run_ps_mode_inline("sync")' in src[i:i + 500]


def test_il_menu_del_py_non_chiama_piu_la_rilevazione_locale():
    """La voce 7 del menu interattivo era l'unica via a send_all."""
    src = _sorgente_py()
    assert re.search(r'"7": \("Rileva hardware/salute e invia al cloud", sync_now\)', src)
    assert "sync_now" in _funzioni(src)


def test_anche_il_py_accetta_mode_sync():
    src = _sorgente_py()
    assert 'if _args.mode == "sync":' in src


def test_clean_resta_in_entrambi():
    """`_clean` sembrava morto insieme ai collector, ma nell'exe viene passato
    dentro TweakContext e nel .py lo usa apply_all_tweaks: toglierlo rompeva
    l'applicazione dei tweak senza che nessun test se ne accorgesse."""
    exe = _sorgente_exe()
    assert "_clean" in _funzioni(exe) and re.search(r"_clean=_clean", exe)
    py = _sorgente_py()
    assert "_clean" in _funzioni(py)
    assert len(re.findall(r"_clean\(", py)) >= 3, "nel .py _clean serve ancora ai tweak"
