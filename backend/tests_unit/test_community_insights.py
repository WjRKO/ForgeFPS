"""_community_insights: deve pescare SOLO utenti con hardware simile.

Regressione storica: la funzione calcolava cpu_prefix/gpu_prefix e poi non li usava
nella query, aggregando i tweak di *tutti* gli utenti. Il prompt diceva comunque
"utenti con hardware simile" -> l'AI costruiva consigli su una premessa falsa.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from fake_db import FakeDb

from routers import advisor

ME = "user-me"
MY_SPECS = {"data": {"cpu": "AMD Ryzen 7 5800X3D", "gpu": "NVIDIA GeForce RTX 3070"}}


def _run(specs, pc_specs, applied_tweaks, monkeypatch):
    monkeypatch.setattr(advisor, "db", FakeDb(pc_specs=pc_specs, applied_tweaks=applied_tweaks))
    return asyncio.run(advisor._community_insights(ME, specs))


def _specs_doc(uid, cpu, gpu):
    return {"user_id": uid, "data": {"cpu": cpu, "gpu": gpu}}


def _tweak(uid, title, active=True):
    return {"user_id": uid, "title": title, "active": active}


def test_ignora_gli_utenti_con_hardware_diverso(monkeypatch):
    pc_specs = [
        _specs_doc("peer-1", "AMD Ryzen 5 3600", "NVIDIA GeForce RTX 3060"),   # GPU simile
        _specs_doc("peer-2", "AMD Ryzen 7 7700X", "AMD Radeon RX 7800 XT"),    # CPU simile
        _specs_doc("peer-3", "AMD Ryzen 9 5900X", "NVIDIA GeForce RTX 3080"),  # entrambe
        _specs_doc("altro-1", "Intel Core i5-12400", "Intel Arc A770"),        # nessuna
        _specs_doc("altro-2", "Intel Core i3-10100", "NVIDIA GeForce GTX 1650"),
    ]
    applied = [
        _tweak("peer-1", "Timer resolution stabile"),
        _tweak("peer-2", "Timer resolution stabile"),
        _tweak("peer-3", "Timer resolution stabile"),
        _tweak("altro-1", "Disattiva Xbox Game Bar"),
        _tweak("altro-2", "Disattiva Xbox Game Bar"),
    ]
    out = _run(MY_SPECS, pc_specs, applied, monkeypatch)
    joined = "\n".join(out)
    assert "Timer resolution stabile" in joined
    assert "Xbox Game Bar" not in joined, "tweak di utenti con hardware diverso non devono comparire"
    assert "3 dei 3 utenti" in joined


def test_conta_utenti_distinti_non_documenti(monkeypatch):
    pc_specs = [_specs_doc(f"peer-{i}", "AMD Ryzen 7 5700X", "NVIDIA GeForce RTX 3060") for i in range(3)]
    applied = [
        _tweak("peer-0", "Piano energetico prestazioni massime"),
        _tweak("peer-0", "Piano energetico prestazioni massime"),  # doppione stesso utente
        _tweak("peer-1", "Piano energetico prestazioni massime"),
    ]
    out = _run(MY_SPECS, pc_specs, applied, monkeypatch)
    assert "applicato da 2 dei 3 utenti" in out[0]


def test_campione_troppo_piccolo_non_produce_contesto(monkeypatch):
    pc_specs = [_specs_doc("peer-1", "AMD Ryzen 7 5700X", "NVIDIA GeForce RTX 3060")]
    applied = [_tweak("peer-1", "Timer resolution stabile")]
    assert _run(MY_SPECS, pc_specs, applied, monkeypatch) == []


def test_tweak_applicato_da_un_solo_utente_e_scartato(monkeypatch):
    pc_specs = [_specs_doc(f"peer-{i}", "AMD Ryzen 7 5700X", "NVIDIA GeForce RTX 3060") for i in range(3)]
    applied = [_tweak("peer-0", "Overclock manuale della VRAM")]
    assert _run(MY_SPECS, pc_specs, applied, monkeypatch) == []


def test_hardware_non_classificabile_non_produce_contesto(monkeypatch):
    ignoto = {"data": {"cpu": "CPU sconosciuta", "gpu": "Display generico"}}
    pc_specs = [_specs_doc(f"peer-{i}", "CPU sconosciuta", "Display generico") for i in range(5)]
    applied = [_tweak(f"peer-{i}", "Un tweak") for i in range(5)]
    assert _run(ignoto, pc_specs, applied, monkeypatch) == []


def test_ignora_i_tweak_disattivati(monkeypatch):
    pc_specs = [_specs_doc(f"peer-{i}", "AMD Ryzen 7 5700X", "NVIDIA GeForce RTX 3060") for i in range(3)]
    applied = [
        _tweak("peer-0", "Debloat servizi", active=False),
        _tweak("peer-1", "Debloat servizi", active=False),
        _tweak("peer-2", "Debloat servizi", active=True),
    ]
    assert _run(MY_SPECS, pc_specs, applied, monkeypatch) == []


def test_l_utente_corrente_non_conta_come_peer(monkeypatch):
    pc_specs = [
        _specs_doc(ME, "AMD Ryzen 7 5800X3D", "NVIDIA GeForce RTX 3070"),
        _specs_doc("peer-1", "AMD Ryzen 7 5700X", "NVIDIA GeForce RTX 3060"),
        _specs_doc("peer-2", "AMD Ryzen 5 5600", "NVIDIA GeForce RTX 3050"),
        _specs_doc("peer-3", "AMD Ryzen 9 5950X", "NVIDIA GeForce RTX 3090"),
    ]
    applied = [_tweak(ME, "Tweak mio"), _tweak("peer-1", "Tweak mio"), _tweak("peer-2", "Tweak mio")]
    out = _run(MY_SPECS, pc_specs, applied, monkeypatch)
    # 3 peer trovati (io escluso), 2 dei quali hanno applicato il tweak
    assert "applicato da 2 dei 3 utenti" in out[0]
