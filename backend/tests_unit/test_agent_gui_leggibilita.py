"""Leggibilita' della GUI dell'agent: contrasto, dimensioni, sfondi dichiarati.

La PR #33 ha fatto questa passata sul dashboard e ha fissato lo standard di
casa: contrasto corretto al livello del token e non con sostituzioni sparse,
niente testo sotto gli 11px. La GUI dell'agent non l'aveva mai ricevuta.

I contrasti qui sono calcolati sui token, che e' dove la regola vive. La
verifica sugli elementi reali — con gli strati semitrasparenti composti, che
altrimenti falsano il conto in entrambe le direzioni — e' stata fatta a schermo
su tutte e otto le schede.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

GUI = ps_agent.GUI_HTML
FONDO = "#0a0a0f"
# Le card sono piu' chiare della pagina, quindi sono il caso peggiore — ed e' li'
# che sta quasi tutto il testo. Tarare sul fondo della pagina lasciava passare
# valori che sulle card scendevano sotto la soglia: e' successo al badge "gia
# attivo", a 4.44:1.
FONDO_CARD = "#14141c"


def _lum(hexcol):
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    canali = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canali]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrasto(fg, bg=FONDO):
    a, b = _lum(fg), _lum(bg)
    chiaro, scuro = max(a, b), min(a, b)
    return round((chiaro + 0.05) / (scuro + 0.05), 2)


def _token(nome):
    m = re.search(rf"--{nome}:\s*(#[0-9a-fA-F]{{3,6}})\s*;", GUI)
    assert m, f"token --{nome} non trovato"
    return m.group(1)


def test_i_tre_livelli_di_testo_passano_lo_standard_AA():
    """`--dim` stava a 2.26:1 e non era usato solo per ornamenti: ci finivano i
    contatori delle categorie, i timestamp del log e la spiegazione di perche'
    un tweak non sia applicabile."""
    for nome in ("text", "muted", "dim"):
        for fondo, dove in ((FONDO, "pagina"), (FONDO_CARD, "card")):
            c = contrasto(_token(nome), fondo)
            assert c >= 4.5, f"--{nome} sul fondo {dove} e' a {c}:1, sotto la soglia AA"


def test_i_tre_livelli_restano_distinguibili():
    """Alzare il contrasto non deve appiattire la gerarchia: se i livelli
    collassano si perde l'informazione che davano."""
    livelli = [contrasto(_token(n), FONDO_CARD) for n in ("text", "muted", "dim")]
    assert livelli[0] > livelli[1] > livelli[2], f"gerarchia persa: {livelli}"
    assert livelli[1] / livelli[2] >= 1.2, "muted e dim troppo vicini per distinguerli"


def test_nessun_testo_sotto_gli_11px():
    """Stessa soglia della PR #33, fermata a 11 e non 12 per non mandare a capo
    le etichette nei layout piu' stretti."""
    misure = re.findall(r"font-size:\s*([0-9.]+)px", GUI)
    sotto = sorted({float(v) for v in misure if float(v) < 11})
    assert not sotto, f"dimensioni sotto gli 11px ancora presenti: {sotto}"


def test_i_bottoni_non_ereditano_il_fondo_chiaro_del_browser():
    """Un <button> senza `background` prende il grigio chiaro di default del
    browser: in una interfaccia scura diventa l'unico elemento bianco della
    pagina, col testo grigio pensato per un fondo scuro. E' successo a
    `.density-toggle`.

    Il rischio dipende dall'elemento HTML, non dal nome della classe — la mia
    prima versione di questo test cercava le classi con 'btn' nel nome e
    segnalava cinque <span> e <label> che non c'entravano nulla. Si neutralizza
    una volta sola nel reset, invece di sperare che ogni regola se lo ricordi.
    """
    assert re.search(r"\n  button\s*\{[^}]*background:\s*transparent", GUI), \
        "manca il reset dello sfondo sui <button>"


def test_la_versione_non_e_scritta_a_mano():
    """Diceva 'GUI v3.2', un numero scollegato da tutto mentre l'agent era alla
    0.8.1: la stessa deriva che era gia' costata una release distribuita
    sbagliata. Il numero puo' restare nei commenti che raccontano la storia del
    file; quello che conta e' che non venga piu' mostrato all'utente."""
    assert 'class="ver-pill">GUI v' not in GUI
    assert "renderVerPill" in GUI
    assert "state.agent && state.agent.installed" in GUI
