"""Tests for AI Advisor endpoints: /suggestions, /chat, /sessions."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-gear-monitor.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---- /api/advisor/suggestions ----
def test_suggestions_shape_and_personalized(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/advisor/suggestions", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "suggestions" in d and "personalized" in d
    assert isinstance(d["suggestions"], list)
    assert 1 <= len(d["suggestions"]) <= 4
    assert all(isinstance(x, str) and x for x in d["suggestions"])
    # Admin should have specs/health -> personalized
    assert d["personalized"] is True, f"expected personalized=True, got: {d}"
    joined = " | ".join(d["suggestions"]).lower()
    # Should contain NVIDIA panel recommendation (admin has NVIDIA GPU per prev iterations)
    # or at least one hardware-personalized topic (temp/driver/etc).
    hints = ["nvidia", "amd adrenalin", "driver", "temperature", "avvio", "energetico", "game mode", "hags", "disco", "ram", "temporanei"]
    assert any(h in joined for h in hints), f"no personalized hint in suggestions: {d['suggestions']}"


def test_suggestions_requires_auth():
    r = requests.get(f"{BASE_URL}/api/advisor/suggestions", timeout=10)
    assert r.status_code in (401, 403)


# ---- /api/advisor/chat streaming ----
def test_chat_streaming_session_prefix_and_powershell(auth_session):
    payload = {"message": "Elencami 2 comandi PowerShell per pulire i file temporanei e mostrarmi lo spazio disco.", "session_id": None}
    with auth_session.post(f"{BASE_URL}/api/advisor/chat", json=payload, stream=True, timeout=60) as r:
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
        # collect body
        body = b""
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                body += chunk
        text = body.decode("utf-8", errors="replace")
    # first line must contain __SESSION__<id>__
    first_line = text.split("\n", 1)[0]
    assert first_line.startswith("__SESSION__") and first_line.endswith("__"), f"missing session marker: {first_line!r}"
    session_id = first_line.replace("__SESSION__", "").rstrip("_")
    assert len(session_id) >= 8
    # should contain powershell fenced block
    assert "```powershell" in text.lower() or "```" in text, f"no code block in response: {text[:400]}"
    # Return session for regression
    pytest.chat_session_id = session_id
    pytest.chat_full_text = text


def test_chat_context_aware(auth_session):
    payload = {"message": "Quale è il problema principale del mio PC secondo l'health score?", "session_id": None}
    with auth_session.post(f"{BASE_URL}/api/advisor/chat", json=payload, stream=True, timeout=60) as r:
        assert r.status_code == 200
        text = b"".join(r.iter_content(chunk_size=None)).decode("utf-8", errors="replace")
    lower = text.lower()
    # Should reference at least one context signal
    signals = ["health", "punteggio", "driver", "avvio", "temperatura", "cpu", "gpu", "ram", "disco", "°c", "giorni", "startup"]
    found = [s for s in signals if s in lower]
    assert len(found) >= 2, f"response not context-aware enough. signals: {found}. body: {text[:500]}"


# ---- sessions regression ----
def test_sessions_created_and_listed(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/advisor/sessions", timeout=15)
    assert r.status_code == 200
    sessions = r.json()
    assert isinstance(sessions, list)
    sid = getattr(pytest, "chat_session_id", None)
    assert sid, "chat test did not run first"
    ids = [s["id"] for s in sessions]
    assert sid in ids, f"chat session {sid} not in list {ids[:5]}"


def test_session_messages_saved(auth_session):
    sid = getattr(pytest, "chat_session_id", None)
    r = auth_session.get(f"{BASE_URL}/api/advisor/sessions/{sid}", timeout=15)
    assert r.status_code == 200
    msgs = r.json()
    assert isinstance(msgs, list) and len(msgs) >= 2
    roles = [m["role"] for m in msgs]
    assert "user" in roles and "assistant" in roles
    # assistant content should be non-empty
    assistants = [m for m in msgs if m["role"] == "assistant"]
    assert any(len(m.get("content", "")) > 20 for m in assistants)


def test_delete_session(auth_session):
    sid = getattr(pytest, "chat_session_id", None)
    r = auth_session.delete(f"{BASE_URL}/api/advisor/sessions/{sid}", timeout=15)
    assert r.status_code == 200
    # verify gone
    r2 = auth_session.get(f"{BASE_URL}/api/advisor/sessions", timeout=15)
    ids = [s["id"] for s in r2.json()]
    assert sid not in ids
