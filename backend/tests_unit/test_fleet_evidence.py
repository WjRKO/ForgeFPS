"""fleet_evidence: dall'aggregato del Laboratorio alle righe di contesto per l'AI."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fleet_evidence as fe
import hardware
from fake_db import FakeDb


def _doc(tweak_id, tested, kept, delta_sum, hw_class="nvidia_amd", scope="vendor"):
    return {"tweak_id": tweak_id, "tested": tested, "kept": kept,
            "delta_sum": delta_sum, "hw_class": hw_class, "scope": scope}


# ---------- pick_evidence ----------

def test_campione_troppo_piccolo_escluso():
    """Con 2 misure il tasso di successo e' aneddoto."""
    assert fe.pick_evidence([_doc("power", 2, 2, 8.0)], []) == []


def test_calcola_tasso_di_successo_ed_effetto_medio():
    out = fe.pick_evidence([_doc("power", 10, 8, 45.0)], [])
    assert out[0]["success_pct"] == 80
    assert out[0]["avg_delta_pct"] == 4.5
    assert out[0]["scope"] == "vendor"


def test_la_famiglia_hardware_sostituisce_il_vendor():
    """Non si sommano: sono gli stessi test contati due volte."""
    out = fe.pick_evidence(
        [_doc("power", 100, 50, 100.0)],
        [_doc("power", 8, 8, 80.0, hw_class="ryzen-7|rtx-30", scope="family")])
    assert len(out) == 1
    assert out[0]["scope"] == "family"
    assert out[0]["tested"] == 8
    assert out[0]["success_pct"] == 100


def test_famiglia_con_pochi_campioni_non_sostituisce():
    out = fe.pick_evidence(
        [_doc("power", 100, 50, 100.0)],
        [_doc("power", 2, 2, 20.0, hw_class="ryzen-7|rtx-30", scope="family")])
    assert out[0]["scope"] == "vendor"
    assert out[0]["tested"] == 100


def test_ordina_famiglia_prima_poi_effetto_maggiore():
    out = fe.pick_evidence(
        [_doc("timer", 20, 18, 60.0), _doc("power", 20, 10, 20.0)],
        [_doc("gaming", 5, 5, 15.0, scope="family")])
    assert [i["tweak_id"] for i in out] == ["gaming", "timer", "power"]


def test_limite_rispettato():
    docs = [_doc(f"tw{i}", 10, 5, 10.0) for i in range(10)]
    assert len(fe.pick_evidence(docs, [], limit=4)) == 4


def test_documenti_senza_tweak_id_ignorati():
    assert fe.pick_evidence([{"tested": 10, "kept": 5, "delta_sum": 1.0}], []) == []


# ---------- format_lines ----------

def test_riga_dichiara_sempre_la_numerosita():
    """Senza il numero di misure l'AI presenta come solido un dato su 3 campioni."""
    items = fe.pick_evidence([_doc("power", 12, 9, 54.0)], [])
    line = fe.format_lines(items, {"power": "Piano energetico prestazioni massime"})[0]
    assert "12 volte" in line
    assert "75%" in line
    assert "+4.5%" in line
    assert "Piano energetico prestazioni massime" in line


def test_tweak_scartato_riporta_il_tasso_di_scarto():
    """20 test, 3 mantenuti -> "scartato 85% delle volte", non 15%."""
    items = fe.pick_evidence([_doc("mpo", 20, 3, -10.0)], [])
    line = fe.format_lines(items, {"mpo": "MPO off"})[0]
    assert "scartato 85% delle volte" in line
    assert "-0.5%" in line


def test_tweak_mantenuto_riporta_il_tasso_di_successo():
    items = fe.pick_evidence([_doc("power", 20, 17, 60.0)], [])
    line = fe.format_lines(items, {"power": "Piano energetico"})[0]
    assert "mantenuto 85% delle volte" in line


def test_nome_sconosciuto_usa_l_id():
    items = fe.pick_evidence([_doc("tweak_ignoto", 5, 3, 5.0)], [])
    assert "tweak_ignoto" in fe.format_lines(items, {})[0]


def test_nessun_item_nessuna_riga():
    assert fe.format_lines([], {}) == []
    assert fe.format_lines(None, None) == []


# ---------- load_for_specs ----------

def test_load_legge_entrambe_le_granularita():
    db = FakeDb(lab_fleet_stats=[
        _doc("power", 30, 20, 90.0, hw_class="nvidia_amd", scope="vendor"),
        _doc("power", 6, 6, 42.0, hw_class="ryzen-7|rtx-30", scope="family"),
        _doc("timer", 30, 15, 30.0, hw_class="nvidia_intel", scope="vendor"),
    ])
    out = asyncio.run(fe.load_for_specs(db, {}, "nvidia_amd", "ryzen-7|rtx-30"))
    assert [i["tweak_id"] for i in out] == ["power"]
    assert out[0]["scope"] == "family"      # la famiglia vince
    assert out[0]["avg_delta_pct"] == 7.0


def test_load_senza_chiave_famiglia_usa_solo_il_vendor():
    db = FakeDb(lab_fleet_stats=[_doc("power", 30, 20, 90.0)])
    out = asyncio.run(fe.load_for_specs(db, {}, "nvidia_amd", None))
    assert out[0]["scope"] == "vendor"


def test_load_senza_dati_ritorna_vuoto():
    assert asyncio.run(fe.load_for_specs(FakeDb(), {}, "nvidia_amd", "ryzen-7|rtx-30")) == []


def test_chiavi_coerenti_con_hardware_module():
    """Le chiavi lette devono essere le stesse che il Lab scrive."""
    data = {"cpu": "AMD Ryzen 7 5800X3D", "gpu": "NVIDIA GeForce RTX 3070"}
    assert hardware.vendor_class(data) == "nvidia_amd"
    assert hardware.fleet_key(data) == "ryzen-7|rtx-30"
