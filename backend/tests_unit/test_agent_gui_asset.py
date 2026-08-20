"""La GUI dell'agent vive in agent_gui.html e viene reinserita nello script.

Il file finisce dentro una here-string PowerShell a singolo apice, che ha una
regola sola ma tassativa: nessuna riga puo' iniziare con `'@`, altrimenti la
stringa si chiude a meta' GUI e l'agent scarica uno script rotto. Un errore che
non si vede scrivendo HTML, e che si manifesta solo sul PC dell'utente.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent


def test_il_file_della_gui_esiste_accanto_al_modulo():
    """Va distribuito col backend: senza, l'agent resta senza interfaccia."""
    assert ps_agent._GUI_HTML_PATH.exists()
    assert ps_agent._GUI_HTML_PATH.name == "agent_gui.html"


def test_nessuna_riga_chiude_la_here_string():
    offenders = [n for n, line in enumerate(ps_agent.GUI_HTML.split("\n"), 1)
                 if line.startswith("'@")]
    assert not offenders, f"righe che chiuderebbero la here-string: {offenders}"


def test_il_segnaposto_e_stato_sostituito():
    """Se la sostituzione non avviene, l'agent riceve la stringa letterale
    __GUI_HTML__ al posto della GUI."""
    assert "__GUI_HTML__" not in ps_agent.PS_SCRIPT
    assert "<!DOCTYPE html>" in ps_agent.PS_SCRIPT


def test_la_gui_resta_dentro_i_delimitatori():
    ps = ps_agent.PS_SCRIPT
    apertura = ps.index("$html = @'")
    chiusura = ps.index("\n'@", apertura)
    assert apertura < ps.index("<!DOCTYPE html>") < chiusura


def test_il_segnaposto_del_token_sopravvive_all_estrazione():
    """Lo sostituisce PowerShell a runtime con il token di sessione: se sparisce
    dall'HTML, la GUI non riesce piu' a parlare con il proprio server locale."""
    assert "__TOKEN__" in ps_agent.GUI_HTML


def test_la_gui_non_e_piu_dentro_il_sorgente_python():
    """Il punto dell'estrazione: 97 KB di interfaccia non stanno nel file che
    contiene il motore di misura."""
    src = ps_agent._Path(ps_agent.__file__).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" not in src
    assert "__GUI_HTML__" in src
