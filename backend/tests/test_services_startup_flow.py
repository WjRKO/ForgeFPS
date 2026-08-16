"""Backend regression tests: Windows Services + Startup analyze flow + agent
script anti-Defender fix (no WScript / no ComObject).
"""
import os
import shutil
import subprocess
import tempfile
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
# Percorso dell'eseguibile PowerShell: "/opt/pwsh/pwsh" era quello del vecchio
# container Linux. Si cerca prima in PATH (pwsh 7, poi Windows PowerShell 5.1).
PWSH = (os.environ.get("PWSH") or shutil.which("pwsh")
        or shutil.which("powershell") or "/opt/pwsh/pwsh")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login {r.status_code}: {r.text}"
    return s


@pytest.fixture(scope="module")
def agent_token(session):
    r = session.get(f"{BASE_URL}/api/agent/token")
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def agent_script_text(agent_token):
    r = requests.get(f"{BASE_URL}/api/agent/script",
                     params={"t": agent_token})
    assert r.status_code == 200
    txt = r.text
    # historical false-positive: without token, endpoint returns single error line.
    line_count = txt.count("\n")
    assert line_count > 5900, f"agent script too short ({line_count} lines) - probably token invalid"
    return txt


# --- Anti-Defender fix ---
class TestAgentScriptAntiDefender:
    def test_no_wscript(self, agent_script_text):
        assert "WScript" not in agent_script_text, "WScript.Shell must not appear (Defender persistence pattern)"

    def test_no_comobject(self, agent_script_text):
        # spec: script must not contain any ComObject reference
        occurrences = [ln for ln in agent_script_text.splitlines()
                       if "ComObject" in ln]
        assert not occurrences, f"ComObject usage still present ({len(occurrences)} line(s)): {occurrences[:3]}"

    def test_has_services_and_startup_functions(self, agent_script_text):
        for needle in ("Get-ServicesAudit", "Get-StartupList",
                       "_lnkTarget", "StartupApproved"):
            assert needle in agent_script_text, f"missing '{needle}' in script"

    def test_size_and_line_count(self, agent_script_text):
        assert len(agent_script_text) > 250_000, f"script size {len(agent_script_text)} < 250KB"
        assert agent_script_text.count("\n") > 5900


# --- PowerShell syntax check ---
class TestPowerShellSyntax:
    def test_parse_no_errors(self, agent_script_text):
        # encoding esplicito: lo script inizia con il BOM UTF-8 e su Windows il
        # default e' cp1252, che su quel carattere solleva UnicodeEncodeError.
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                         encoding="utf-8") as f:
            f.write(agent_script_text)
            path = f.name
        cmd = [
            PWSH, "-NoProfile", "-Command",
            "$err=$null;"
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{path}',[ref]$null,[ref]$err) | Out-Null;"
            "if($err){$err|ForEach-Object{Write-Host $_};exit 1}else{Write-Host 'OK';exit 0}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        os.unlink(path)
        assert proc.returncode == 0, f"PS parse errors:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"


# --- Services analyze flow ---
class TestServicesAnalyzeFlow:
    def test_report_services_audit_and_analyze(self, session, agent_token):
        payload = {
            "services_audit": [
                {"name": "DiagTrack", "display": "Connected User Experiences",
                 "state": "Running", "start_mode": "Auto",
                 "shared": True, "ram_mb": None, "dependents": 0, "ms": True},
                {"name": "Fax", "display": "Fax", "state": "Stopped",
                 "start_mode": "Manual", "shared": False,
                 "ram_mb": None, "dependents": 0, "ms": True},
            ]
        }
        r = requests.post(f"{BASE_URL}/api/agent/report-specs",
                          json=payload,
                          headers={"X-Agent-Token": agent_token})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        g = session.get(f"{BASE_URL}/api/services/analyze")
        assert g.status_code == 200, g.text
        data = g.json()
        assert data.get("available") is True
        items = {i["name"].lower(): i for i in data.get("items", [])}
        assert "diagtrack" in items
        assert items["diagtrack"]["recommendation"] == "disattiva"
        assert "fax" in items
        assert items["fax"]["recommendation"] == "gia_ok"


# --- Startup analyze flow (filters disabled) ---
class TestStartupAnalyzeFlow:
    def test_startup_analyze_only_active(self, session, agent_token):
        payload = {
            "startup": [
                {"name": "Discord", "path": "C:/Discord.exe",
                 "enabled": True, "ram_mb": 480, "source": "Run"},
                {"name": "Steam", "path": "C:/Steam.exe",
                 "enabled": False, "ram_mb": 300, "source": "Run"},
            ]
        }
        r = requests.post(f"{BASE_URL}/api/agent/report-specs",
                          json=payload,
                          headers={"X-Agent-Token": agent_token})
        assert r.status_code == 200, r.text

        a = session.post(f"{BASE_URL}/api/startup/analyze")
        assert a.status_code == 200, a.text
        body = a.json()
        # response can be either {items:[...]} or {items:[], summary}
        items = body.get("items", [])
        names = " ".join(str(it.get("name", "")).lower() for it in items)
        assert "steam" not in names, f"disabled Steam should be excluded, got: {items}"
        # AI may return 0 or 1 items but Discord should not obviously be filtered out
