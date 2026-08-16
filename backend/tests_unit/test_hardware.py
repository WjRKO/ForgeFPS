"""Classificazione hardware (backend/hardware.py) — logica pura."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import hardware


@pytest.mark.parametrize("cpu,expected", [
    ("AMD Ryzen 7 5800X3D", "ryzen-7"),
    ("AMD Ryzen5 3600", "ryzen-5"),
    ("Intel(R) Core(TM) i5-12400F", "intel-i5"),
    ("Intel Core Ultra 7 155H", "intel-ultra-7"),
    ("Apple M3", None),
    ("", None),
    (None, None),
])
def test_cpu_family(cpu, expected):
    assert hardware.cpu_family(cpu) == expected


@pytest.mark.parametrize("gpu,expected", [
    ("NVIDIA GeForce RTX 3070", "rtx-30"),
    ("NVIDIA GeForce RTX4060 Laptop GPU", "rtx-40"),
    ("NVIDIA GeForce RTX 5090", "rtx-50"),
    ("NVIDIA GeForce GTX 1660 SUPER", "gtx"),
    ("AMD Radeon RX 7800 XT", "radeon-rx-7000"),
    ("Intel Arc A770", "intel-arc"),
    ("Microsoft Basic Display Adapter", None),
    (None, None),
])
def test_gpu_family(gpu, expected):
    assert hardware.gpu_family(gpu) == expected


def test_is_similar_matches_on_either_family():
    ryzen_3070 = {"cpu": "AMD Ryzen 7 5800X3D", "gpu": "NVIDIA GeForce RTX 3070"}
    intel_3060 = {"cpu": "Intel Core i5-12400", "gpu": "NVIDIA GeForce RTX 3060"}
    ryzen_6700 = {"cpu": "AMD Ryzen 7 7700X", "gpu": "AMD Radeon RX 6700 XT"}
    assert hardware.is_similar(ryzen_3070, intel_3060)   # stessa famiglia GPU
    assert hardware.is_similar(ryzen_3070, ryzen_6700)   # stessa famiglia CPU
    assert not hardware.is_similar(intel_3060, ryzen_6700)


def test_unknown_hardware_is_never_similar():
    """Due PC non classificabili non devono finire nello stesso gruppo:
    altrimenti 'utenti come te' diventerebbe 'utenti di cui non sappiamo nulla'."""
    ignoto_a = {"cpu": "CPU sconosciuta", "gpu": "Display generico"}
    ignoto_b = {"cpu": "Altra CPU ignota", "gpu": "Altro display"}
    assert not hardware.is_similar(ignoto_a, ignoto_b)
    assert not hardware.is_similar(None, None)
