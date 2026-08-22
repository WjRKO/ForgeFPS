"""Lo stato di un tweak e' un codice deciso dal tweak, non una frase da indovinare.

Prima ogni `state={...}` restituiva testo libero e tre consumatori diversi
(la GUI web, la GUI classica, il conteggio dei "gia' ottimali") lo
classificavano ognuno con la propria regex sull'italiano. La stessa parola pero'
vale il contrario a seconda del tweak, e da li' nascevano due bug veri:

  - `search_index` risponde 'Attivo' quando il servizio di indicizzazione STA
    GIRANDO, cioe' quando il tweak NON e' applicato: la GUI lo mostrava verde
    e lo contava fra i gia' ottimizzati;
  - i due tweak GPU rispondono 'applicabile' per dire che si POSSONO applicare,
    e venivano letti come 'applicati'.

Dalla passata di leggibilita' in poi il tweak non sceglie nemmeno piu' la parola
da mostrare: quella dipende dallo stato, uguale per tutti. Il tweak puo'
aggiungere un dettaglio, che e' un'informazione in piu' ("261 MB da pulire") e
non un modo alternativo di dire lo stato.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

CODICI = {"ok", "todo", "na", "unknown"}
_BLOCKS = re.findall(r"id='([a-z_0-9]+)';.*?state=\{(.*?)\};?\s*apply=",
                     ps_agent.PS_SCRIPT, re.S)


def _body(tweak_id):
    return next(b for t, b in _BLOCKS if t == tweak_id)


def test_tutti_i_tweak_dichiarano_uno_stato():
    assert len(_BLOCKS) >= 30, f"trovati solo {len(_BLOCKS)} blocchi state"
    senza = [tid for tid, body in _BLOCKS if "Tw " not in body]
    assert not senza, f"tweak che restituiscono ancora testo libero: {senza}"


def test_si_usano_solo_i_quattro_codici():
    usati = set(re.findall(r"\(Tw '([a-z]+)'", ps_agent.PS_SCRIPT))
    assert usati <= CODICI, f"codici di stato non previsti: {usati - CODICI}"


def test_indicizzazione_attiva_significa_da_applicare():
    """Il caso che rendeva sbagliato il conteggio dei gia' ottimizzati."""
    b = _body("search_index")
    assert "Running'){(Tw 'todo')}" in b
    assert "else{(Tw 'ok')}" in b


def test_applicabile_non_vuol_dire_applicato():
    for tid in ("amd_ulps", "nvidia_tel"):
        b = _body(tid)
        assert "(Tw 'todo')" in b, f"{tid}: 'applicabile' non e' 'applicato'"
        assert "(Tw 'na' 'solo su GPU" in b, f"{tid}: vendor diverso = non applicabile"


def test_attivo_resta_ottimale_dove_lo_e():
    """La correzione non deve aver ribaltato tutti gli altri."""
    b = _body("power")
    assert "(Tw 'ok')" in b and "(Tw 'todo')" in b


def test_zero_app_da_rimuovere_e_uno_stato_ottimale():
    assert "(Tw 'ok' 'nessuna app da rimuovere')" in _body("debloat")


def test_nessun_tweak_scrive_la_propria_parola_di_stato():
    """'Attivo', 'Disattivato', 'Prestazioni', 'TRIM attivo' e 'Gia disattivata'
    dicevano tutte "e' a posto" con cinque facce diverse, e l'utente doveva
    tradurre ogni volta."""
    parole = ("Attivo", "Attiva", "Attivi", "Disattivat", "Disabilitat",
              "Prestazioni", "Da ottimizzare", "Da attivare", "TRIM attivo",
              "Applica per", "n/d")
    colpevoli = [(tid, p) for tid, body in _BLOCKS for p in parole
                 if f"'{p}" in body]
    assert not colpevoli, f"parole di stato scritte dal tweak: {colpevoli}"


def test_le_quattro_parole_stanno_in_un_posto_solo():
    ps = ps_agent.PS_SCRIPT
    assert "$script:TW_WORDS = @{" in ps
    for parola in ("Ottimale", "Da applicare", "Non applicabile", "Sconosciuto"):
        assert f"'{parola}'" in ps, f"manca la parola {parola}"


def test_il_dettaglio_resta_dove_aggiunge_qualcosa():
    """Non tutto va appiattito: quanti MB ci sono da pulire, o su quale DNS si
    e' gia', sono informazioni che lo stato da solo non da'."""
    assert "MB da pulire" in _body("clean")
    assert "gia su Cloudflare" in _body("dns")
    assert "solo su GPU AMD" in _body("amd_ulps")


def test_il_dto_manda_codice_ed_etichetta():
    ps = ps_agent.PS_SCRIPT
    assert "state = $st.label; state_code = $st.code" in ps
    assert "$st = Get-TwState $t" in ps


def test_la_gui_classifica_dal_codice_non_dalla_frase():
    gui = ps_agent.GUI_HTML
    assert "STATE_CLASSES" in gui and "t.state_code" in gui
    # la vecchia regex sull'italiano non deve piu' decidere nulla
    assert "prestazioni|nessun|applicabile" not in gui


def test_la_gui_classica_colora_dal_codice():
    assert "if ($s.code -eq 'ok')" in ps_agent.PS_SCRIPT
    assert "$s -match 'Attivo|Disabilit" not in ps_agent.PS_SCRIPT
