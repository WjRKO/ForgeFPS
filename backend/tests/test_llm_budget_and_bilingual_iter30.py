"""Iteration 30 - Verify:
- FIX-1: /api/fps/estimate and /api/startup/analyze return HTTP 402 with friendly
  message when LLM budget exceeded (instead of 502 with raw error).
- FIX-2: ai_engine.stream_advisor builds bilingual prompt: when lang='en' uses
  '[USER PC CONTEXT' / 'User:' / '[New message]'; when lang='it' uses
  '[CONTESTO PC DELL' / 'Utente:' / '[Nuovo messaggio]'.
- SANITY: /api/auth/login, /api/auth/me still work.
"""
import os
import sys
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASS = "4zWK4o_xSw5prU-2b7w9dQ"


# --- sanity/auth ---
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def test_sanity_login_and_me(session):
    r = session.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("email") == ADMIN_EMAIL


# --- FIX-1: budget exhausted -> 402 friendly ---
def test_fps_estimate_budget_exhausted_returns_402(session):
    r = session.post(f"{BASE_URL}/api/fps/estimate",
                     json={"game": "Cyberpunk 2077", "resolution": "1440p"},
                     timeout=30)
    # Expected: 402 with friendly detail (budget exhausted case)
    # If budget actually recharged, we'd get 200; accept both but check message on 402/502.
    print(f"fps/estimate status={r.status_code} body={r.text[:300]}")
    if r.status_code == 200:
        pytest.skip("LLM budget seems available now; skip friendly-msg check")
    assert r.status_code == 402, (
        f"Expected 402 for budget exhausted, got {r.status_code}: {r.text}")
    detail = r.json().get("detail", "")
    assert "Credito LLM esaurito" in detail
    assert "Universal Key" in detail


def test_startup_analyze_budget_exhausted_returns_402(session):
    # need startup data present in pc_specs. Seed via agent token endpoint.
    tok_resp = session.get(f"{BASE_URL}/api/agent/token", timeout=10)
    assert tok_resp.status_code == 200
    agent_token = tok_resp.json()["token"]

    seed = requests.post(
        f"{BASE_URL}/api/agent/report-specs",
        headers={"X-Agent-Token": agent_token, "Content-Type": "application/json"},
        json={"startup": [{"name": "Steam", "path": "C:\\Steam.exe"},
                          {"name": "Discord", "path": "C:\\Discord.exe"},
                          {"name": "OneDrive", "path": "C:\\OneDrive.exe"}]},
        timeout=15,
    )
    assert seed.status_code == 200, seed.text

    r = session.post(f"{BASE_URL}/api/startup/analyze", timeout=30)
    print(f"startup/analyze status={r.status_code} body={r.text[:300]}")
    if r.status_code == 200:
        pytest.skip("LLM budget seems available; skip friendly-msg check")
    assert r.status_code == 402, (
        f"Expected 402, got {r.status_code}: {r.text}")
    detail = r.json().get("detail", "")
    assert "Credito LLM esaurito" in detail
    assert "Universal Key" in detail


# --- FIX-2: bilingual prompt build via monkeypatching build_chat ---
class _FakeChat:
    def __init__(self):
        self.system = None

    def stream_message(self, um):
        async def _gen():
            if False:
                yield None
        return _gen()


def test_stream_advisor_prompt_english_when_lang_en(monkeypatch):
    sys.path.insert(0, "/app/backend")
    import ai_engine

    captured = {}

    def fake_build_chat(session_id, system=ai_engine.ADVISOR_SYSTEM):
        captured["system"] = system
        return _FakeChat()

    monkeypatch.setattr(ai_engine, "build_chat", fake_build_chat)

    async def run():
        gen = ai_engine.stream_advisor(
            session_id="t-en",
            history=[{"role": "user", "content": "hi"},
                     {"role": "assistant", "content": "hello"}],
            message="what next?",
            specs_text="CPU: Ryzen 5600\nGPU: RTX 3060",
            lang="en",
        )
        async for _ in gen:
            pass

    asyncio.get_event_loop().run_until_complete(run())
    sys_msg = captured.get("system", "")
    print(f"[EN system snippet] ...{sys_msg[-500:]}")
    assert "[USER PC CONTEXT" in sys_msg, "English PC context header missing"
    assert "[CONTESTO PC DELL'UTENTE" not in sys_msg, "Italian header should NOT appear when lang=en"
    assert "Reply ENTIRELY in English" in sys_msg


def test_stream_advisor_prompt_italian_when_lang_it(monkeypatch):
    sys.path.insert(0, "/app/backend")
    import ai_engine

    captured = {}

    def fake_build_chat(session_id, system=ai_engine.ADVISOR_SYSTEM):
        captured["system"] = system
        return _FakeChat()

    monkeypatch.setattr(ai_engine, "build_chat", fake_build_chat)

    async def run():
        gen = ai_engine.stream_advisor(
            session_id="t-it",
            history=[{"role": "user", "content": "ciao"}],
            message="che faccio?",
            specs_text="CPU: Ryzen 5600\nGPU: RTX 3060",
            lang="it",
        )
        async for _ in gen:
            pass

    asyncio.get_event_loop().run_until_complete(run())
    sys_msg = captured.get("system", "")
    print(f"[IT system snippet] ...{sys_msg[-500:]}")
    assert "[CONTESTO PC DELL'UTENTE" in sys_msg
    assert "[USER PC CONTEXT" not in sys_msg
    assert "Rispondi INTERAMENTE in italiano" in sys_msg


# --- REGRESSIONS ---
def test_agent_download_zip_regression(session):
    r = session.get(f"{BASE_URL}/api/agent/download-zip", timeout=60)
    assert r.status_code == 200
    cl = r.headers.get("Content-Length")
    assert cl is not None, "Content-Length header missing"
    assert int(cl) == len(r.content), f"Content-Length {cl} != body {len(r.content)}"
    assert r.content[:2] == b"PK", "Not a zip"


def test_magic_link_endpoints_regression(session):
    r = session.post(f"{BASE_URL}/api/auth/magic-link", timeout=10)
    assert r.status_code in (200, 429), r.text
    if r.status_code == 200:
        tok = r.json().get("token")
        assert tok
        # status should return pending
        s = session.get(f"{BASE_URL}/api/auth/magic-status/{tok}", timeout=10)
        assert s.status_code == 200, s.text
