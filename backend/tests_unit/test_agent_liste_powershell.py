"""Gli array di un elemento che PowerShell trasforma in oggetti.

`ConvertTo-Json` (PS 5.1) serializza un array di UN solo elemento come scalare:
`@('x') | ConvertTo-Json` da' `"x"`, non `["x"]`. Ogni lista che l'agent manda
alla GUI puo' quindi presentarsi come oggetto singolo, e succede proprio nei casi
piu' comuni — il primo giro di ottimizzazione (una sessione sola nel journal), un
tweak che tocca una chiave sola, un passo fallito solo.

Chi ci chiama sopra `.map`/`.filter`/`.some` esplode. Chi ci chiama `.length`
non esplode e conta zero, che e' peggio: "1 passo non riuscito" diventa "nessun
problema". La GUI si e' rotta cosi' al primo avvio su una macchina vera:

    [GUI-ERROR] renderTabs: TypeError: (t.plan || []).some is not a function

La difesa e' `lista()` applicata alle PORTE d'ingresso — cinque punti, non
quaranta — piu' il divieto del modo di scrivere che ha causato il guasto.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ps_agent

GUI = ps_agent.GUI_HTML
HARNESS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "tests", "build_gui_harness.py"), encoding="utf-8").read()

# `actions` e' un parametro locale di bigToast, non arriva dall'agent.
CONSENTITI = {("actions", "forEach")}


def test_esiste_una_sola_funzione_che_normalizza():
    assert "function lista(x)" in GUI
    assert "if (Array.isArray(x)) return x;" in GUI


def test_ogni_porta_normalizza_quello_che_entra():
    """Cinque ingressi: lo stato, il risultato di un lavoro, il job in corso, il
    journal e i profili cloud. Normalizzare li' invece che ai punti d'uso vuol
    dire che chi aggiunge una schermata non deve saperne niente."""
    assert "state.tweaks = normalizzaTweaks(d.tweaks);" in GUI
    assert "state.tweaks = normalizzaTweaks(d.tweaks);" in GUI
    assert 'j = normalizzaJob(await api("/api/job"))' in GUI
    assert 'normalizzaJournal(await api("/api/journal"))' in GUI
    assert "normalizzaProfili(d)" in GUI


def test_il_piano_di_un_tweak_e_sempre_una_lista():
    """E' il caso che ha rotto la GUI: un tweak che tocca una chiave sola."""
    assert "t.plan = lista(t.plan).filter(r => r && typeof r === \"object\");" in GUI
    assert "(t.plan || []).some" not in GUI


def test_il_journal_normalizza_anche_dentro_le_sessioni():
    """Una sessione con una voce sola, una voce con una chiave sola: sono i due
    casi del primo giro di ottimizzazione, cioe' quelli che vede per primi
    chiunque installi l'agent."""
    i = GUI.index("function normalizzaJournal")
    corpo = GUI[i:GUI.index("function esc(s)")]
    for campo in ("j.sessions = lista(", "s.revertable = lista(", "s.entries = lista(",
                  "e.changes = lista(", "e.partial = lista("):
        assert campo in corpo, campo


def test_il_job_normalizza_passi_errori_e_risultato():
    i = GUI.index("function normalizzaJob")
    corpo = GUI[i:GUI.index("function normalizzaProfili")]
    for campo in ("j.steps = lista(", "j.errors = lista(",
                  "j.result.backup_ids = lista(", "j.result.revertable = lista("):
        assert campo in corpo, campo


def test_nessuno_scrive_piu_nel_modo_che_ha_causato_il_guasto():
    """`(x || []).map` non protegge da niente: se `x` e' l'oggetto in cui
    PowerShell ha trasformato la lista, il `||` non scatta e il metodo non
    esiste. E' il modo di scrivere da vietare, non la singola riga da correggere."""
    trovati = set(re.findall(
        r"\(([A-Za-z_$][\w.$]*) \|\| \[\]\)\.(map|filter|some|slice|join|forEach|reduce|length)", GUI))
    assert not (trovati - CONSENTITI), (
        "usa lista(x) al posto di (x || []): %s" % sorted(trovati - CONSENTITI))


def test_l_harness_riproduce_il_difetto():
    """Un mock che manda sempre array veri non avrebbe mai visto questo bug: la
    GUI passava tutte le prove e si rompeva sul primo PC. Ora l'harness collassa
    gli array di un elemento esattamente come ConvertTo-Json."""
    assert "function comePowerShell(v)" in HARNESS
    assert "v.length === 1 ? comePowerShell(v[0])" in HARNESS
    assert "const servito = comePowerShell(body);" in HARNESS
