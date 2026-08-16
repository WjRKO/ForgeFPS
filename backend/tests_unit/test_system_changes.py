"""system_changes: diff della configurazione + correlazione con le performance."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import system_changes as sc


# ---------- diff_specs ----------

def test_rileva_aggiornamento_driver_gpu():
    out = sc.diff_specs({"gpu_driver_version": "566.03"}, {"gpu_driver_version": "572.16"})
    assert out == [{"kind": "gpu_driver_version", "label": "Driver GPU", "impact": "high",
                    "from": "566.03", "to": "572.16"}]


def test_primo_sync_non_e_un_cambiamento():
    """Senza snapshot precedente ogni campo risulterebbe 'cambiato'."""
    assert sc.diff_specs(None, {"cpu": "AMD Ryzen 7 5800X3D", "gpu_driver_version": "572.16"}) == []
    assert sc.diff_specs({}, {"cpu": "AMD Ryzen 7 5800X3D"}) == []


def test_campo_sparito_non_e_un_cambiamento():
    """Uno scan degradato (agent senza admin) perde campi: non e' una modifica al PC."""
    assert sc.diff_specs({"gpu_driver_version": "566.03"}, {"gpu_driver_version": None}) == []
    assert sc.diff_specs({"gpu_driver_version": "566.03"}, {}) == []


def test_differenze_di_soli_spazi_ignorate():
    assert sc.diff_specs({"cpu": "AMD Ryzen 7 "}, {"cpu": " AMD Ryzen 7"}) == []


def test_campi_non_sorvegliati_ignorati():
    """running_apps, temperature e simili cambiano di continuo: fuori dal diff."""
    assert sc.diff_specs({"cpu_temp": "55"}, {"cpu_temp": "72"}) == []


def test_xmp_attivato_rilevato_come_cambio_velocita_ram():
    out = sc.diff_specs({"ram_speed_mhz": "2133"}, {"ram_speed_mhz": "3600"})
    assert out[0]["kind"] == "ram_speed_mhz"
    assert out[0]["impact"] == "high"


def test_piu_cambiamenti_insieme():
    out = sc.diff_specs(
        {"gpu_driver_version": "566.03", "os_build": "22631", "cpu": "Ryzen 7 5800X3D"},
        {"gpu_driver_version": "572.16", "os_build": "26100", "cpu": "Ryzen 7 5800X3D"})
    assert {c["kind"] for c in out} == {"gpu_driver_version", "os_build"}


# ---------- diff_startup ----------

def test_nuovo_programma_all_avvio():
    out = sc.diff_startup([{"name": "Steam"}], [{"name": "Steam"}, {"name": "Epic Games Launcher"}])
    assert len(out) == 1
    assert out[0]["kind"] == "startup_added"
    assert out[0]["count"] == 1
    assert "Epic Games Launcher" in out[0]["to"]


def test_programma_disabilitato_conta_come_rimosso():
    out = sc.diff_startup([{"name": "Steam", "enabled": True}], [{"name": "Steam", "enabled": False}])
    assert out[0]["kind"] == "startup_removed"


def test_formato_legacy_list_di_stringhe():
    """Gli agent .exe v0.7.x mandano list[str]: devono restare confrontabili."""
    out = sc.diff_startup(["Steam"], ["Steam", "Discord"])
    assert out[0]["kind"] == "startup_added"
    assert out[0]["to"] == "Discord"


def test_sezione_startup_non_inviata_non_produce_eventi():
    """None = l'agent non ha mandato la sezione, diverso da 'lista vuota'."""
    assert sc.diff_startup(None, [{"name": "Steam"}]) == []
    assert sc.diff_startup([{"name": "Steam"}], None) == []


def test_startup_invariato_non_produce_eventi():
    assert sc.diff_startup([{"name": "Steam"}, {"name": "Discord"}],
                           [{"name": "Discord"}, {"name": "Steam"}]) == []


def test_elenco_nomi_troncato_ma_conteggio_intero():
    prev = []
    new = [{"name": f"App{i}"} for i in range(9)]
    out = sc.diff_startup(prev, new)
    assert out[0]["count"] == 9
    assert out[0]["to"].count(",") == sc.MAX_STARTUP_NAMES - 1


# ---------- build_change_events ----------

def test_build_change_events_unisce_specs_e_startup():
    prev = {"data": {"gpu_driver_version": "566.03"}, "startup": [{"name": "Steam"}]}
    events = sc.build_change_events(prev, {"gpu_driver_version": "572.16"},
                                    [{"name": "Steam"}, {"name": "OneDrive"}])
    assert {e["kind"] for e in events} == {"gpu_driver_version", "startup_added"}


# ---------- analyze_trend ----------

def _serie(*coppie):
    return [{"at": f"2026-08-{d:02d}T10:00:00+00:00", "value": v} for d, v in coppie]


def test_regressione_rilevata():
    t = sc.analyze_trend(_serie((1, 100), (3, 102), (5, 98), (10, 82)))
    assert t["direction"] == "down"
    assert t["delta_pct"] < -5
    assert t["samples"] == 4


def test_miglioramento_rilevato():
    t = sc.analyze_trend(_serie((1, 80), (3, 82), (5, 78), (10, 95)))
    assert t["direction"] == "up"


def test_oscillazione_piccola_resta_stabile():
    t = sc.analyze_trend(_serie((1, 100), (3, 102), (5, 99), (10, 101)))
    assert t["direction"] == "stable"


def test_un_outlier_isolato_non_sposta_la_baseline():
    """La mediana protegge dal benchmark fatto mentre girava un download."""
    t = sc.analyze_trend(_serie((1, 100), (2, 40), (3, 101), (4, 99), (10, 100)))
    # mediana di [40, 99, 100, 101] = 99.5 -> l'outlier non sposta nulla.
    # Con la media sarebbe 85, e l'ultimo punto (100) risulterebbe un +17%: falso allarme.
    assert t["baseline"] == 99.5
    assert t["direction"] == "stable"


def test_meno_di_tre_punti_nessun_trend():
    assert sc.analyze_trend(_serie((1, 100), (10, 60))) is None
    assert sc.analyze_trend([]) is None
    assert sc.analyze_trend(None) is None


def test_punti_malformati_scartati():
    serie = _serie((1, 100), (3, 102), (5, 98), (10, 82))
    serie += [{"at": "non-una-data", "value": 5}, {"at": "2026-08-11T10:00:00+00:00", "value": None},
              {"at": "2026-08-12T10:00:00+00:00", "value": 0}]
    t = sc.analyze_trend(serie)
    assert t["samples"] == 4


def test_serie_disordinata_viene_riordinata():
    t = sc.analyze_trend(_serie((10, 82), (1, 100), (5, 98), (3, 102)))
    assert t["current"] == 82
    assert t["current_at"].startswith("2026-08-10")


# ---------- correlate ----------

def _cambio(giorno, kind, impact):
    return {"kind": kind, "impact": impact, "created_at": f"2026-08-{giorno:02d}T12:00:00+00:00"}


def test_correlate_tiene_solo_la_finestra_del_trend():
    trend = sc.analyze_trend(_serie((5, 100), (7, 101), (9, 99), (15, 80)))
    changes = [
        _cambio(2, "os_build", "medium"),           # prima della finestra
        _cambio(12, "gpu_driver_version", "high"),  # dentro
        _cambio(20, "bios", "medium"),              # dopo
    ]
    out = sc.correlate(trend, changes)
    assert [c["kind"] for c in out] == ["gpu_driver_version"]


def test_correlate_ordina_per_impatto_poi_per_data():
    trend = sc.analyze_trend(_serie((1, 100), (3, 101), (5, 99), (20, 80)))
    changes = [
        _cambio(6, "startup_added", "medium"),
        _cambio(8, "gpu_driver_version", "high"),
        _cambio(10, "os_build", "medium"),
        _cambio(12, "cpu_socket", "low"),
    ]
    out = sc.correlate(trend, changes)
    assert [c["kind"] for c in out] == [
        "gpu_driver_version",  # high
        "os_build",            # medium, piu' recente
        "startup_added",       # medium, meno recente
        "cpu_socket",          # low
    ]


def test_cambiamento_dello_stesso_sync_resta_correlato():
    """Un sync scrive prima l'health record e poi gli eventi: il cambiamento e'
    posteriore alla misura di pochi millisecondi e non va scartato."""
    trend = sc.analyze_trend([
        {"at": "2026-08-01T10:00:00+00:00", "value": 90},
        {"at": "2026-08-05T10:00:00+00:00", "value": 89},
        {"at": "2026-08-10T10:00:00+00:00", "value": 62},
    ])
    changes = [{"kind": "gpu_driver_version", "impact": "high",
                "created_at": "2026-08-10T10:00:00.412000+00:00"}]
    assert [c["kind"] for c in sc.correlate(trend, changes)] == ["gpu_driver_version"]


def test_cambiamento_molto_dopo_la_misura_e_scartato():
    """Oltre la tolleranza non puo' spiegare una misura gia' presa."""
    trend = sc.analyze_trend([
        {"at": "2026-08-01T10:00:00+00:00", "value": 90},
        {"at": "2026-08-05T10:00:00+00:00", "value": 89},
        {"at": "2026-08-10T10:00:00+00:00", "value": 62},
    ])
    changes = [{"kind": "gpu_driver_version", "impact": "high",
                "created_at": "2026-08-10T12:00:00+00:00"}]
    assert sc.correlate(trend, changes) == []


def test_correlate_senza_trend_non_accusa_nessuno():
    assert sc.correlate(None, [_cambio(5, "gpu_driver_version", "high")]) == []
