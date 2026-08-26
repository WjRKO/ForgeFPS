"""/api/dashboard: una richiesta sola al posto di otto, senza cambiare i dati.

La home faceva otto GET in parallelo, e due erano fra gli endpoint piu' cari
dell'API. L'endpoint unico legge lo stesso documento pc_specs una volta e ne
ricava specs, health e benchmark; le trappole sono due, e sono qui sotto:

 - `products` e' la lista corta da mostrare (5), `stats.tracked_products` e' il
   totale: se qualcuno li fa venire dalla stessa query il contatore si tronca a 5;
 - `health.available` deve restare False quando il PC non ha mai sincronizzato,
   perche' e' su quel campo che il frontend decide se disegnare il punteggio.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fake_db import FakeDb

from routers import dashboard

UID = "user-1"
USER = {"_id": UID}


def _chiama(monkeypatch, **collezioni):
    monkeypatch.setattr(dashboard, "db", FakeDb(**collezioni))
    monkeypatch.setattr(dashboard, "device_filter", _filtro)
    monkeypatch.setattr(dashboard, "get_state", _stato)
    endpoint = dashboard.build(lambda: USER).routes[0].endpoint
    return asyncio.run(endpoint(user=USER))


async def _filtro(_db, uid):
    return {"user_id": uid}


async def _stato(_db, _uid):
    return {"active": []}


def _prodotto(i, iniziale, corrente):
    return {"user_id": UID, "id": f"p{i}", "created_at": f"2026-01-{i:02d}",
            "initial_price": iniziale, "current_price": corrente}


def test_il_totale_prodotti_non_si_tronca_alla_lista_corta(monkeypatch):
    out = _chiama(monkeypatch, products=[_prodotto(i, 100, 100) for i in range(1, 13)])
    assert len(out["products"]) == 5, "la lista mostrata resta corta"
    assert out["stats"]["tracked_products"] == 12, "il contatore e' sul totale, non sui 5"


def test_risparmio_solo_sui_cali_veri(monkeypatch):
    out = _chiama(monkeypatch, products=[
        _prodotto(1, 100.0, 80.0),   # -20
        _prodotto(2, 50.0, 65.0),    # rincarato: non e' un risparmio
        _prodotto(3, None, 10.0),    # senza prezzo iniziale: non calcolabile
    ])
    assert out["stats"]["total_saved"] == 20.0


def test_pc_mai_sincronizzato(monkeypatch):
    out = _chiama(monkeypatch)
    assert out["health"] == {"available": False}
    assert out["specs"] == {"data": None, "updated_at": None}
    assert out["benchmark"]["latest"] is None


def test_specs_health_e_benchmark_dallo_stesso_documento(monkeypatch):
    doc = {"user_id": UID, "data": {"cpu": "Ryzen 7 5800X3D"},
           "health": {"dpc_max": 120.0}, "benchmark": {"score": 71},
           "updated_at": "2026-08-26T10:00:00Z"}
    out = _chiama(monkeypatch, pc_specs=[doc])
    assert out["specs"]["data"]["cpu"] == "Ryzen 7 5800X3D"
    assert out["specs"]["updated_at"] == "2026-08-26T10:00:00Z"
    assert out["health"]["available"] is True
    assert out["health"]["score"] is not None
    assert out["benchmark"]["latest"] == {"score": 71}


def test_discord_scollegato(monkeypatch):
    out = _chiama(monkeypatch, users=[{"_id": UID}])
    assert out["discord"]["linked"] is False
