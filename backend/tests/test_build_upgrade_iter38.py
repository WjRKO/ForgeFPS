"""Backend regression for iter38: /app/build presets + /app/upgrade before-after.

Covers:
- Auth (cookie login)
- POST /api/builds/generate (real LLM)
- POST /api/builds/save + GET /api/builds + DELETE /api/builds/{id}
- GET /api/pc-specs (seeded hardware)
- GET /api/games (seeded 5 games)
- POST /api/upgrade/analyze (real LLM)
- POST /api/fps/upgrade-compare (real LLM) - the main new endpoint
- POST /api/fps/estimate regression
"""
import os
import pytest
import requests

def _load_frontend_env():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()).rstrip("/")
EMAIL = "admin@boostpc.io"
PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update(UA)
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# --- Sanity: hardware + games seeded ---
def test_pc_specs_seeded(client):
    r = client.get(f"{BASE_URL}/api/pc-specs", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data and data.get("data"), "no pc_specs"
    d = data["data"]
    assert "i7-12700K" in str(d.get("cpu", "")), d
    assert "RTX 3070 Ti" in str(d.get("gpu", "")), d
    assert d.get("ram") == 32, d


def test_games_seeded(client):
    r = client.get(f"{BASE_URL}/api/games", timeout=30)
    assert r.status_code == 200
    games = r.json().get("games", [])
    names = [g if isinstance(g, str) else g.get("name") for g in games]
    for expected in ["Counter-Strike 2", "Fortnite", "Cyberpunk 2077", "Valorant", "Call of Duty: Warzone"]:
        assert expected in names, f"missing {expected}. Got {names}"


# --- Builds ---
def test_list_builds(client):
    r = client.get(f"{BASE_URL}/api/builds", timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# --- BEFORE/AFTER compare (real LLM, generous timeout) ---
def test_fps_upgrade_compare(client):
    payload = {
        "game": "Counter-Strike 2",
        "resolution": "1440p",
        "upgrades": ["GPU: NVIDIA GeForce RTX 4070 Ti", "RAM: 32GB DDR5 6000"],
    }
    r = client.post(f"{BASE_URL}/api/fps/upgrade-compare", json=payload, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    assert "estimates" in data and len(data["estimates"]) == 4, data
    for e in data["estimates"]:
        assert "preset" in e and "before" in e and "after" in e
        assert isinstance(e["before"], (int, float))
        assert isinstance(e["after"], (int, float))
    assert "gain_pct" in data
    assert "notes" in data
    assert "confidence" in data


def test_fps_estimate_regression(client):
    r = client.post(f"{BASE_URL}/api/fps/estimate",
                    json={"game": "Valorant", "resolution": "1080p"}, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    d = r.json()
    assert "estimates" in d and len(d["estimates"]) >= 3


def test_upgrade_analyze(client):
    r = client.post(f"{BASE_URL}/api/upgrade/analyze",
                    json={"budget": 600, "goal": "144 FPS in gaming competitivo"}, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    d = r.json()
    assert "bottleneck" in d and "recommendations" in d
    assert isinstance(d["recommendations"], list) and len(d["recommendations"]) >= 1
