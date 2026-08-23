"""Un campo assente non cancella un campo presente.

Il percorso dell'agent sostituiva `pc_specs.data` in blocco, quello del form
manuale fondeva campo per campo: due semantiche opposte sullo stesso documento.
La sostituzione perdeva dati in silenzio, perche' una scansione degradata - agent
senza privilegi, nvidia-smi assente, WMI che singhiozza - produce meno campi, e
quei campi non diventavano vecchi, diventavano vuoti.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import specs_merge as sm

ORA = "2026-08-23T10:00:00+00:00"
PRIMA = "2026-08-20T09:00:00+00:00"


def test_una_scansione_degradata_non_svuota_il_pc():
    prev = {"cpu": "Ryzen 7 5800X3D", "gpu": "RTX 3070 Ti", "gpu_vram_gb": "8"}
    data, _ = sm.merge_specs(prev, {}, {"cpu": "Ryzen 7 5800X3D"}, source="agent", at=ORA)
    assert data["gpu"] == "RTX 3070 Ti", "la GPU e' sparita per una scansione senza nvidia-smi"
    assert data["gpu_vram_gb"] == "8"


def test_un_campo_vuoto_vale_come_assente():
    """L'agent manda "" quando una sonda non risponde: non e' un valore nuovo."""
    prev = {"gpu": "RTX 3070 Ti"}
    for vuoto in ("", "   ", None, [], {}):
        data, _ = sm.merge_specs(prev, {}, {"gpu": vuoto}, source="agent", at=ORA)
        assert data["gpu"] == "RTX 3070 Ti", "%r ha cancellato il valore" % (vuoto,)


def test_falso_e_zero_sono_valori_non_assenze():
    """`hvci_on = False` e `scan_context.admin = False` sono i casi in cui il
    dato conta di piu': un controllo di verita' li avrebbe scartati."""
    assert not sm.is_empty(False)
    assert not sm.is_empty(0)
    data, meta = sm.merge_specs({"hvci_on": True}, {}, {"hvci_on": False}, source="agent", at=ORA)
    assert data["hvci_on"] is False
    assert meta["hvci_on"]["at"] == ORA


def test_un_valore_nuovo_sostituisce_quello_vecchio():
    data, meta = sm.merge_specs({"gpu_driver_version": "566.36"}, {}, {"gpu_driver_version": "572.16"},
                                source="agent", at=ORA)
    assert data["gpu_driver_version"] == "572.16"
    assert meta["gpu_driver_version"] == {"src": "agent", "at": ORA}


def test_la_data_di_un_campo_non_confermato_resta_indietro():
    """E' quello che rende leggibile la differenza fra "vecchio" e "sparito"."""
    prev = {"cpu": "Ryzen", "gpu": "RTX 3070 Ti"}
    meta0 = {"cpu": {"src": "agent", "at": PRIMA}, "gpu": {"src": "agent", "at": PRIMA}}
    _, meta = sm.merge_specs(prev, meta0, {"cpu": "Ryzen"}, source="agent", at=ORA)
    assert meta["cpu"]["at"] == ORA
    assert meta["gpu"]["at"] == PRIMA
    assert sm.stale_fields(meta, ORA) == ["gpu"]


def test_i_campi_piu_vecchi_del_registro_non_sono_mai_visti():
    """Un documento scritto prima che data_meta esistesse ha campi senza voce:
    "visto prima che ne tenessimo traccia" non e' "mai visto"."""
    data, meta = sm.merge_specs({"bios": "AMI 5031"}, None, {}, source="agent", at=ORA)
    assert data["bios"] == "AMI 5031"
    assert meta["bios"] == {"src": None, "at": None}


def test_il_manuale_non_viene_cancellato_da_una_scansione_che_non_lo_vede():
    """Chi scrive a mano un campo che l'agent non sa rilevare deve ritrovarlo."""
    prev = {"resolution": "3440x1440"}
    meta0 = {"resolution": {"src": "manual", "at": PRIMA}}
    data, meta = sm.merge_specs(prev, meta0, {"cpu": "Ryzen"}, source="agent", at=ORA)
    assert data["resolution"] == "3440x1440"
    assert sm.field_source(meta, "resolution") == "manual"


def test_l_agent_ha_ragione_sui_campi_che_misura():
    """Se l'agent lo rileva, la misura batte quello che l'utente aveva scritto."""
    prev = {"gpu": "GTX 1060"}
    meta0 = {"gpu": {"src": "manual", "at": PRIMA}}
    data, meta = sm.merge_specs(prev, meta0, {"gpu": "RTX 3070 Ti"}, source="agent", at=ORA)
    assert data["gpu"] == "RTX 3070 Ti"
    assert sm.field_source(meta, "gpu") == "agent"


def test_entrambi_i_percorsi_di_scrittura_usano_questa_politica():
    """Il valore del modulo e' che sia uno: due semantiche sullo stesso documento
    erano il difetto di partenza."""
    percorso = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routers", "pc.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()
    assert src.count("specs_merge.merge_specs(") == 2
    assert "fields[\"data\"] = data.data" not in src, "il percorso agent e' tornato a sostituire"
