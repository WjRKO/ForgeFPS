"""La Diagnosi: il risultato prima del catalogo.

La prima schermata era un catalogo con le checkbox — un pannello da power user
servito al 90% di gente che vuole un bottone. Ora la prima cosa e' cosa c'e' da
sistemare, e il catalogo sta dietro "Personalizza".

Il punto delicato non e' il layout: e' il numero. Un punteggio inventato in cima
alla schermata sarebbe la stessa promessa dei "booster" da cui questo prodotto
vuole distinguersi, e renderebbe rumore anche tutto il resto — journal, diff,
esiti per riga — che serve a dire il vero. Quasi tutti i test qui sotto tengono
ferma quella riga.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

PS = ps_agent.PS_SCRIPT
GUI = ps_agent.GUI_HTML

BLOCCO = GUI[GUI.index("// ===== Diagnosi: il risultato prima del catalogo ====="):
             GUI.index("// ===== Il piano: cosa cambia, non cosa fa =====")]


# ---------- il numero ----------

def test_il_punteggio_misura_la_copertura_non_la_macchina():
    """E' la percentuale (pesata per impatto dichiarato) di quello che
    FrameForge sa fare ed e' gia' attivo qui. Non e' un voto al PC: nessun dato
    in questo prodotto autorizza un voto al PC."""
    assert "const tot = conta.reduce((s, t) => s + peso(t), 0);" in BLOCCO
    assert 'const fatto = conta.filter(t => t.state_code === "ok").reduce((s, t) => s + peso(t), 0);' in BLOCCO
    assert "score: tot ? Math.round(100 * fatto / tot) : null," in BLOCCO


def test_il_punteggio_esclude_quello_che_non_si_applica_qui():
    """Un tweak che su questa macchina non ha senso (GPU sbagliata, niente SSD)
    non deve pesare ne' come merito ne' come colpa."""
    assert 'const conta = state.tweaks.filter(t => !t.fit.skip && (t.state_code === "ok" || t.state_code === "todo"));' in BLOCCO
    assert "non applicabili a questo PC, fuori dal conto" in BLOCCO


def test_la_schermata_dice_cosa_significa_il_numero():
    """Un numero senza la sua definizione viene letto come la definizione piu'
    generosa possibile: 78 diventa 'il mio PC va al 78%'."""
    assert "COPERTURA DELLE OTTIMIZZAZIONI" in BLOCCO
    assert "Non &egrave; un voto alla macchina." in BLOCCO
    assert 'data-testid="diag-legend"' in BLOCCO


def test_niente_stime_aggregate_in_cima():
    """La stima la dichiara ogni tweak accanto a se stesso, dove si puo'
    valutare. Sommare le percentuali dichiarate di dodici tweak e stampare
    '+11% FPS' in cima e' precisione finta: gli effetti non si sommano, e quel
    numero non lo puo' controllare nessuno."""
    for inventato in ("FPS stimati", "stimati max", "% stimato"):
        assert inventato not in BLOCCO, inventato


def test_il_solo_numero_grande_e_quello_misurato():
    """Il benchmark prima/dopo e' l'unica misura vera che questo prodotto abbia,
    e viene dal PC dell'utente, non da una tabella."""
    assert "MISURATO L'ULTIMA VOLTA" in BLOCCO
    assert "state.journal && state.journal.bench" in BLOCCO
    assert "NESSUNA MISURA ANCORA SU QUESTO PC" in BLOCCO


def test_la_misura_viene_scritta_nel_journal():
    """Finora usciva solo verso il cloud: sul PC non ne restava traccia, quindi
    la schermata non poteva mostrarla."""
    assert "Write-Journal 'bench' @{ id = '__bench__'" in PS
    assert "delta_pct = [int]$pct" in PS
    assert '"$($r.event)" -eq \'bench\'' in PS


# ---------- cosa propone di fare ----------

def test_il_bottone_non_decide_sui_tweak_in_cautela():
    """Un click solo puo' fare le cose sicure. Quelle marcate 'cautela' restano
    una scelta, e la schermata dice quali sono invece di nasconderle."""
    assert 'consigliati: daFare.filter(t => t.risk !== "caution"),' in BLOCCO
    assert 'cautela: daFare.filter(t => t.risk === "caution"),' in BLOCCO
    assert "rest${d.cautela.length === 1 ? \"a\" : \"ano\"} fuori dal" in BLOCCO


def test_chi_serve_amministratore_si_deduce_dalle_chiavi():
    """Una lista scritta a mano si sarebbe disallineata al primo tweak nuovo: le
    chiavi del piano dicono gia' chi scrive in HKLM o sui servizi."""
    assert 'admin: daFare.filter(t => planOf(t).some(r => /^(HKLM:|svc::)/.test(String(r.key || "")))),' in BLOCCO
    assert 'data-testid="diag-admin"' in BLOCCO


def test_ogni_riga_mostra_il_problema_e_il_suo_diff():
    """Il nome di un tweak dice cosa fa il programma; il problema dice cosa non
    va sul PC di chi legge. In cima va il secondo."""
    assert "esc(t.problem || t.name)" in BLOCCO
    assert "const p = planChanging(planOf(t));" in BLOCCO


def test_niente_da_fare_e_uno_stato_dichiarato():
    """Zero risultati non deve sembrare una schermata rotta."""
    assert "Non ho trovato niente da sistemare" in BLOCCO
    assert '"Niente da fare"' in BLOCCO


# ---------- dove sta ----------

def test_la_diagnosi_e_la_schermata_di_partenza():
    assert '{ key: "diagnosi", label: "Diagnosi" },' in GUI
    assert 'let activeCat = "diagnosi";' in GUI
    # ...ed e' la prima voce, prima delle categorie di tweak
    assert GUI.index('{ key: "diagnosi"') < GUI.index('{ key: "gaming"')


def test_il_catalogo_resta_a_un_click():
    assert 'data-testid="diag-custom"' in BLOCCO
    assert 'cust.onclick = () => { activeCat = "gaming"; renderTabs(); renderCards(); };' in BLOCCO


def test_la_barra_in_fondo_non_raddoppia_l_azione():
    """Due bottoni primari che dicono cose diverse sulla stessa schermata."""
    assert 'if (barra) barra.hidden = (activeCat === "diagnosi");' in GUI
