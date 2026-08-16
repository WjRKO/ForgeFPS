"""watchdog: quando un intervento va verificato e cosa conta come regressione."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import watchdog as wd


# ---------- scadenze ----------

def test_verifica_pianificata_a_48_ore():
    assert wd.due_at("2026-08-01T10:00:00+00:00") == "2026-08-03T10:00:00+00:00"


def test_scadenza_finale_a_14_giorni():
    assert wd.expired_at("2026-08-01T10:00:00+00:00") == "2026-08-15T10:00:00+00:00"


def test_timestamp_illeggibile_non_produce_scadenze():
    assert wd.due_at("boh") is None
    assert wd.expired_at("") is None


# ---------- verdetto ----------

def test_regressione_rilevata():
    v = wd.evaluate(90, [70, 72, 71])
    assert v["status"] == "regressed"
    assert v["delta_pct"] < -8
    assert v["observed"] == 71


def test_boost_che_ha_tenuto():
    v = wd.evaluate(90, [89, 91, 90])
    assert v["status"] == "held"


def test_miglioramento_ulteriore():
    v = wd.evaluate(80, [88, 90])
    assert v["status"] == "improved"


def test_calo_sotto_soglia_non_e_regressione():
    """L'health score oscilla da solo con file temporanei e spazio disco."""
    v = wd.evaluate(90, [86, 85])   # -5% circa
    assert v["status"] == "held"


def test_un_solo_campione_non_basta():
    """Puo' essere un sync fatto a PC carico: si aspetta."""
    v = wd.evaluate(90, [60])
    assert v["status"] == "waiting"
    assert v["delta_pct"] is None


def test_nessun_campione_resta_in_attesa():
    assert wd.evaluate(90, [])["status"] == "waiting"
    assert wd.evaluate(90, None)["status"] == "waiting"


def test_senza_baseline_non_si_giudica():
    assert wd.evaluate(None, [70, 71])["status"] == "waiting"
    assert wd.evaluate(0, [70, 71])["status"] == "waiting"


def test_campioni_sporchi_scartati():
    v = wd.evaluate(90, [None, 0, "abc", True, 70, 72])
    assert v["samples"] == 2
    assert v["status"] == "regressed"


def test_mediana_ignora_il_campione_anomalo():
    """Un sync a PC carico non deve da solo far scattare l'allarme."""
    v = wd.evaluate(90, [88, 30, 91])
    assert v["observed"] == 88
    assert v["status"] == "held"


# ---------- notifica ----------

def test_solo_le_regressioni_notificano():
    base = 90
    assert wd.notification_for(wd.evaluate(base, [70, 71]), "autopilot", base) is not None
    assert wd.notification_for(wd.evaluate(base, [89, 90]), "autopilot", base) is None
    assert wd.notification_for(wd.evaluate(base, [98, 99]), "lab", base) is None
    assert wd.notification_for(wd.evaluate(base, []), "lab", base) is None


def test_testo_notifica_cita_i_numeri_e_la_fonte():
    base = 90
    note = wd.notification_for(wd.evaluate(base, [70, 72, 71]), "autopilot", base)
    assert "90" in note["body"] and "71" in note["body"]
    assert "Auto-Pilot" in note["body"]
    assert note["link"] == "/app/pc"


def test_fonte_lab_nel_testo():
    base = 90
    note = wd.notification_for(wd.evaluate(base, [70, 71]), "lab", base)
    assert "Laboratorio" in note["body"]
