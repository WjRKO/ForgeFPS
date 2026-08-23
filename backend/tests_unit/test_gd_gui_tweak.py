"""Il bottone del Gameplay Doctor deve nominare un tweak che esiste.

`gui_tweak` e' l'unico campo del referto scelto dal modello che poi diventa un
comando nell'interfaccia. Nessuno lo verificava: un id inventato, o rimasto
indietro dopo una rinomina, veniva salvato e mostrato all'utente com'era.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tweak_catalog
from routers import advisor


def _referto(primario, alternative=None):
    return {"issues": [{"id": "x", "fix": {"primary": primario, "alternatives": alternative or []}}]}


def _primo_fix(rep):
    return rep["issues"][0]["fix"]["primary"]


def test_un_id_del_catalogo_porta_con_se_il_nome():
    """Il bottone diceva 'power'. Ora dice come si chiama il tweak."""
    rep = advisor._gd_normalizza(_referto({"text": "attiva il piano", "gui_tweak": "power"}))
    assert _primo_fix(rep)["gui_tweak"] == "power"
    assert _primo_fix(rep)["gui_tweak_name"] == tweak_catalog.by_id("power")["name"]


def test_un_id_inventato_non_diventa_un_bottone():
    """Un id che il catalogo non conosce vale quanto nessun id: senza nome il
    frontend non disegna il bottone, e il consiglio testuale resta."""
    rep = advisor._gd_normalizza(_referto({"text": "fai questo", "gui_tweak": "turbo_boost_9000"}))
    assert _primo_fix(rep)["gui_tweak"] is None
    assert _primo_fix(rep)["gui_tweak_name"] is None
    assert _primo_fix(rep)["text"] == "fai questo"


def test_la_chiave_resta_anche_quando_e_vuota():
    """La forma del referto non cambia: il campo c'e' sempre, come prima."""
    for valore in (None, "", "  ", "inesistente", 42):
        rep = advisor._gd_normalizza(_referto({"gui_tweak": valore}))
        assert "gui_tweak" in _primo_fix(rep)
        assert _primo_fix(rep)["gui_tweak"] is None


def test_anche_le_alternative_passano_dal_catalogo():
    """Le alternative finiscono nella lista espansa con l'id fra parentesi: se
    non si validano anche quelle, la sigla senza senso ricompare li'."""
    rep = advisor._gd_normalizza(_referto(
        {"gui_tweak": "gpu_msi"},
        [{"text": "a", "gui_tweak": "timer"}, {"text": "b", "gui_tweak": "non_esiste"}],
    ))
    alt = rep["issues"][0]["fix"]["alternatives"]
    assert alt[0]["gui_tweak_name"] == tweak_catalog.by_id("timer")["name"]
    assert alt[1]["gui_tweak"] is None and alt[1]["gui_tweak_name"] is None


def test_un_referto_malformato_non_fa_esplodere_niente():
    """Il JSON arriva da un modello: `issues` puo' essere un oggetto invece di
    una lista, un fix puo' mancare, `primary` puo' essere una stringa. La
    normalizzazione non e' il posto dove il referto si rompe."""
    for rotto in (None, [], "boh", {}, {"issues": {"non": "una lista"}},
                  {"issues": [None, 3, {"fix": None}, {"fix": {"primary": "stringa"}},
                              {"fix": {"primary": {"gui_tweak": "power"}, "alternatives": "no"}}]}):
        advisor._gd_normalizza(rotto)


def test_ogni_tweak_del_catalogo_e_risolvibile():
    """Il ponte fra il prompt e il bottone: il modello sceglie fra gli id che il
    prompt gli mostra, quindi ognuno di quelli deve superare la validazione."""
    for tid in tweak_catalog.IDS:
        rep = advisor._gd_normalizza(_referto({"gui_tweak": tid}))
        assert _primo_fix(rep)["gui_tweak"] == tid, tid
        assert _primo_fix(rep)["gui_tweak_name"], tid
