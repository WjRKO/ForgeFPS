"""I prefissi di severita' della console dell'agent passano dagli helper Say-*.

Prima convivevano una ventina di prefissi inventati sul posto — `[OK]` e
`[ OK ]` insieme, `[i]` accanto a `[INFO]`, `[SKIP]`, `[FAIL]`, `[ATTENZIONE]` —
perche' scrivere la severita' dentro la stringa costava zero e nessuno se ne
accorgeva. In piu' nello stesso slot finiva anche il contesto (`[LAB]`, `[FPS]`),
che e' un asse diverso: da li' veniva buona parte della proliferazione.

Una passata di pulizia non regge da sola: fra tre mesi si torna a venti. Questo
test e' la parte che regge, perche' fa rumore alla prima riga nuova.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

SEVERITIES = ("Ok", "Info", "Step", "Warn", "Err")

_SEV_WORDS = (r"OK|FATTO|INFO|i|nota|STEP|WARN|ATTENZIONE|SKIP|SCARTATO|ERR|FAIL"
              r"|LAB|FPS|TERMICA|ROLLBACK|COPPIA|diag|HW|Sensori")
_RAW_PREFIXED = re.compile(
    r"""Say[ ]+\(?['"][ ]*\[[ ]*(?:""" + _SEV_WORDS + r""")[ ]*\]""")


def _righe_di_codice():
    """I commenti citano i prefissi vecchi per spiegare perche' non ci sono
    piu': parlarne non e' usarli."""
    for n, line in enumerate(ps_agent.PS_SCRIPT.split("\n"), 1):
        if not line.strip().startswith("#"):
            yield n, line


def test_gli_helper_esistono():
    for s in SEVERITIES:
        assert f"function Say-{s}" in ps_agent.PS_SCRIPT, f"manca Say-{s}"


def test_nessun_prefisso_scritto_a_mano_dentro_un_Say():
    """`Say` resta per banner, valori e prose: li' il colore e' formattazione,
    non severita'. Una riga che dichiara uno stato passa da Say-*, e il
    contesto e' il secondo parametro, non un pezzo di testo."""
    offenders = [f"{n}: {l.strip()[:90]}" for n, l in _righe_di_codice()
                 if _RAW_PREFIXED.search(l)]
    assert not offenders, (
        "prefissi scritti a mano invece di Say-Ok/Info/Step/Warn/Err (+ tag):\n"
        + "\n".join(offenders))


def test_una_sola_grafia_per_ogni_severita():
    """`[OK]` e `[ OK ]` convivevano: la stessa severita' con due facce."""
    assert ps_agent.PS_SCRIPT.count("'[ OK ]' 'Green'") == 1, \
        "la grafia di OK deve esistere solo dentro l'helper"
    doppioni = [n for n, l in _righe_di_codice() if "[OK]" in l]
    assert not doppioni, f"grafia alternativa di OK alle righe {doppioni}"


def test_il_contesto_e_un_parametro():
    """Prova che l'asse del contesto esiste davvero come parametro."""
    ps = ps_agent.PS_SCRIPT
    assert "function _SayLvl" in ps
    assert re.search(r"Say-\w+ [^\n]*'(LAB|FPS|TERMICA|HW)'", ps), \
        "nessuna chiamata usa il tag di contesto: la migrazione e' incompleta"


def test_l_helper_conserva_l_indentazione_del_chiamante():
    """L'indentazione e gli a-capo iniziali danno gerarchia alle sotto-voci: se
    l'helper li mangiasse, l'output perderebbe struttura."""
    src = ps_agent.PS_SCRIPT
    corpo = src[src.index("function _SayLvl"):src.index("function Say-Ok")]
    assert "Substring(0, $i)" in corpo and "$s.Substring($i)" in corpo
