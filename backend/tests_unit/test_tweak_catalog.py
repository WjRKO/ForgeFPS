"""Il catalogo e' uno: questi test sono la ragione per cui resta uno.

Un elenco duplicato non si rompe il giorno in cui lo duplichi, si rompe sei mesi
dopo quando qualcuno aggiunge un tweak in tre posti su quattro. Prima di questo
modulo le quattro copie erano gia' divergenti e nessun test poteva accorgersene,
perche' non esisteva niente da confrontare: ora esiste, e il confronto e' qui.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lab_registry
import ps_agent
import tweak_catalog
from routers import profiles

PS = ps_agent.PS_SCRIPT


def _voci_ps():
    """Gli id dichiarati nel catalogo PowerShell, nell'ordine dell'array."""
    i = PS.index("$script:TWEAKS = @(")
    fine = PS.index("\n)\n", i)
    return re.findall(r"\n  @\{ id='([^']+)'", PS[i:fine])


def test_gli_id_dell_agent_sono_quelli_del_catalogo():
    """Il vincolo centrale: un tweak esiste se e' in tutti e due i posti. Solo
    nel catalogo = una promessa che nessuno mantiene; solo nell'agent = una card
    senza nome, e l'agent la scarta a runtime."""
    assert _voci_ps() == tweak_catalog.IDS


def test_l_agent_non_tiene_piu_testi_suoi():
    """La regressione da impedire e' il ritorno del copia-incolla: un `name=` o
    un `risk=` rimesso a mano nell'array PowerShell ricrea in silenzio la
    seconda copia che questo lavoro ha tolto."""
    i = PS.index("$script:TWEAKS = @(")
    corpo = PS[i:PS.index("\n)\n", i)]
    ricomparsi = sorted({m for m in re.findall(r"\b(cat|name|risk|problem|reason|desc|impact)=", corpo)})
    assert not ricomparsi, "campi di nuovo scritti a mano nell'agent: %s" % ricomparsi


def test_ogni_voce_ps_ha_solo_codice():
    """Quello che resta in PowerShell deve essere eseguibile: se una voce non ha
    ne' apply ne' state, non e' un tweak, e' un residuo."""
    i = PS.index("$script:TWEAKS = @(")
    corpo = PS[i:PS.index("\n)\n", i)]
    for pezzo in corpo.split("\n  @{ id=")[1:]:
        tid = pezzo.split("'")[1]
        assert "apply={" in pezzo, "%s senza apply" % tid
        assert "state={" in pezzo, "%s senza state" % tid


def test_i_metadati_iniettati_coprono_ogni_tweak():
    """L'iniezione e' il ponte fra i due mondi: se il JSON non arriva, l'agent
    resta con 35 id e nessun nome."""
    assert "__TWEAK_META__" not in PS
    blob = ps_agent._tweak_meta_json()
    for t in tweak_catalog.TWEAKS:
        assert '"id": "%s"' % t["id"] in blob


def test_i_metadati_iniettati_sono_ascii():
    """Lo script viene letto da powershell.exe senza BOM: un solo carattere
    fuori dall'ASCII e la console mostra mojibake al posto di un nome."""
    blob = ps_agent._tweak_meta_json()
    fuori = sorted({c for c in blob if ord(c) > 126})
    assert not fuori, "caratteri non ASCII nei metadati: %r" % fuori
    i = PS.index("$__TWMETA_JSON = @'")
    fine = PS.index("\n'@", i)
    for riga in PS[i:fine].split("\n"):
        assert not riga.lstrip().startswith("'@"), "riga che chiude la here-string: %r" % riga


def test_il_catalogo_web_e_quello_dell_agent():
    """profiles.py serve gli id su cui gli utenti costruiscono i profili di
    gioco: uno che l'agent non conosce e' un tweak che non viene mai applicato."""
    assert [t["id"] for t in profiles.TWEAK_CATALOG] == tweak_catalog.IDS
    assert profiles._VALID_IDS == tweak_catalog.ID_SET


def test_i_profili_e_i_preset_citano_solo_tweak_esistenti():
    """I template lato backend e i preset dentro l'agent sono elenchi di id
    scritti a mano: e' l'altro modo in cui un id puo' restare indietro."""
    for tpl in profiles.TEMPLATES:
        ignoti = [i for i in tpl["tweak_ids"] if i not in tweak_catalog.ID_SET]
        assert not ignoti, "template %s cita tweak inesistenti: %s" % (tpl["id"], ignoti)
    i = PS.index("$script:PRESETS = @{")
    corpo = PS[i:PS.index("\n}", i)]
    for preset, elenco in re.findall(r"'(\w+)'\s*=\s*@\(([^)]*)\)", corpo):
        ignoti = [x for x in re.findall(r"'([^']+)'", elenco) if x not in tweak_catalog.ID_SET]
        assert not ignoti, "preset %s cita tweak inesistenti: %s" % (preset, ignoti)


def test_il_lab_misura_un_sottoinsieme_del_catalogo():
    """Il Laboratorio non ha piu' un elenco suo: sono i tweak con un prior."""
    attesi = [t["id"] for t in tweak_catalog.TWEAKS if t["lab_prior"] is not None]
    assert [t["tweak_id"] for t in lab_registry.TWEAKS] == attesi
    assert len(attesi) == 15, "cambiare quali tweak misura il Lab e' una scelta di prodotto"


def test_l_advisor_puo_consigliare_tutto_il_catalogo():
    """Il prompt del Gameplay Doctor conteneva 15 tweak su 35, e i 20 assenti lo
    erano per dimenticanza: il modello non poteva proporre `gpu_msi` nemmeno
    davanti a una diagnosi di latenza DPC."""
    riga = tweak_catalog.advisor_catalog_line()
    citati = {p.split("=", 1)[0] for p in riga.split("; ")}
    assert citati == tweak_catalog.ID_SET
    for atteso in ("gpu_msi", "standby_clear", "power_throttling", "nic_power"):
        assert atteso in citati


def test_il_rischio_e_la_spunta_iniziale_sono_due_cose_diverse():
    """L'agent usava 'caution' per dire tre cose insieme: colore, spunta
    predefinita e ammissione all'Auto-Pilot. Il rischio ora sta sulla scala del
    Lab e la spunta ha un campo suo; `agent_risk()` ricostruisce la stringa che
    la GUI si aspetta, cosi' la scala a quattro livelli non le arriva addosso."""
    for t in tweak_catalog.TWEAKS:
        assert t["risk"] in ("safe", "medium", "expert", "hardware")
        assert tweak_catalog.agent_risk(t) in ("safe", "caution")
    # un tweak da riavvio non e' 'safe' per il Lab, ma resta spuntato di default
    mpo = tweak_catalog.by_id("mpo")
    assert mpo["risk"] == "medium" and mpo["default_on"] is True


def test_un_livello_di_rischio_ignoto_non_diventa_il_piu_sicuro():
    """`_RISK_ORDER.get(x, 0)` trattava un livello sconosciuto come 'safe': un
    errore di battitura promuoveva il tweak invece di fermarlo."""
    try:
        lab_registry.select_candidates({}, "sicurissimo", True)
    except ValueError:
        return
    raise AssertionError("un livello inventato e' stato accettato")
