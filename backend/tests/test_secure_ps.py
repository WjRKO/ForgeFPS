"""Security refactor tests: PS script + SHA parity + agent argparse + regression."""
import os
import re
import hashlib
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200
    return r.json()["token"]


# --- PS script security surface ---
class TestPSScriptSecurity:
    def test_script_starts_with_param(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token})
        assert r.status_code == 200
        # First non-empty line should be Param(...)
        first = r.text.lstrip().splitlines()[0]
        assert first.startswith("Param("), f"Script should start with 'Param(', got: {first[:80]}"

    def test_token_is_runtime_param_not_embedded(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token})
        # Token should NOT be baked as a literal $TOKEN='<token>' assignment
        assert f"'{agent_token}'" not in r.text, "Token must NOT be embedded as literal in script"
        # It should read from Param $Token
        assert "$TOKEN" in r.text and "$Token" in r.text

    def test_no_irm_pipe_iex(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token})
        # No 'irm ... | iex' or 'iwr ... | iex' in-memory execution
        assert not re.search(r"irm\b[^\n]*\|\s*iex", r.text, re.IGNORECASE), "Script must not contain 'irm | iex'"
        assert not re.search(r"iwr\b[^\n]*\|\s*iex", r.text, re.IGNORECASE), "Script must not contain 'iwr | iex'"
        assert "Invoke-Expression" not in r.text or "| Invoke-Expression" not in r.text

    def test_invalid_token_friendly_plaintext(self):
        r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": "invalid_bogus"})
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "").lower()
        assert "Token non valido" in r.text or "invalid" in r.text.lower()

    def test_missing_token_friendly_plaintext(self):
        r = requests.get(f"{BASE_URL}/api/agent/script")
        assert r.status_code == 200
        # Empty token -> not found in db -> friendly error
        assert "Token" in r.text


# --- SHA256 parity between script and script-info ---
class TestShaParity:
    def test_sha256_matches_script_bytes(self, session, agent_token):
        r_script = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token})
        assert r_script.status_code == 200
        computed = hashlib.sha256(r_script.content).hexdigest()

        r_info = session.get(f"{BASE_URL}/api/agent/script-info", params={"t": agent_token})
        assert r_info.status_code == 200
        info = r_info.json()
        assert info["sha256"] == computed, f"SHA mismatch: info={info['sha256']} vs computed={computed}"
        assert info["size"] == len(r_script.content)
        assert info["filename"] == "forgefps.ps1"

    def test_script_info_requires_auth(self, agent_token):
        r = requests.get(f"{BASE_URL}/api/agent/script-info", params={"t": agent_token})
        assert r.status_code in (401, 403)


# --- Desktop agent Python download ---
class TestDesktopAgentDownload:
    def test_download_agent_argparse_and_defaults(self, session, agent_token):
        r = session.get(f"{BASE_URL}/api/desktop-agent/download")
        assert r.status_code == 200
        body = r.text
        assert "argparse" in body
        assert "--token" in body and "--backend" in body
        # Token default must be substituted with the user's actual token (not placeholder)
        assert "__AGENT_TOKEN__" not in body
        assert "__BACKEND_URL__" not in body
        assert agent_token in body, "Agent script should embed the user's token as default"
        # Content-Disposition filename
        cd = r.headers.get("content-disposition", "")
        assert "forgefps_agent.py" in cd


# --- Regression ---
class TestRegression:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/health")
        assert r.status_code == 200

    def test_admin_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        # Cookie-based auth: returns user object directly, token in httpOnly cookie
        data = r.json()
        assert data.get("email") == ADMIN_EMAIL
        assert data.get("role") == "admin"

    def test_telemetry_post(self, agent_token):
        r = requests.post(
            f"{BASE_URL}/api/agent/telemetry",
            json={"sample": {"cpu_util": 42, "ram_used_pct": 55}},
            headers={"X-Agent-Token": agent_token},
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_security_headers_present(self):
        r = requests.get(f"{BASE_URL}/api/health")
        headers = {k.lower(): v for k, v in r.headers.items()}
        # At least a few of the classic security headers should be there
        found = sum(1 for h in ("x-content-type-options", "x-frame-options",
                                "referrer-policy", "content-security-policy",
                                "strict-transport-security") if h in headers)
        assert found >= 2, f"Expected security headers, got: {list(headers.keys())}"
