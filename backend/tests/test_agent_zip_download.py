"""Test the ZIP download fix - Content-Length header + testzip() validation"""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stream-gear-monitor.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    # verify /me
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me.status_code == 200, f"/me failed: {me.status_code}"
    return s


def test_download_zip_content_length_and_integrity(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/agent/download-zip", timeout=120, stream=False)
    assert r.status_code == 200, f"download-zip status {r.status_code}: {r.text[:500]}"

    cl_header = r.headers.get('Content-Length') or r.headers.get('content-length')
    assert cl_header is not None, "Content-Length header MISSING"
    cl = int(cl_header)

    body = r.content
    body_size = len(body)
    print(f"Content-Length header: {cl}, actual body size: {body_size}")

    # Must match exactly - the whole point of the fix
    assert body_size == cl, f"Body size {body_size} != Content-Length {cl} (truncation!)"

    # Must be roughly ~9.1 MB (not 2.7 MB truncated)
    assert body_size > 8_000_000, f"Body too small: {body_size} bytes (expected ~9.1MB)"

    # Content-Disposition
    cd = r.headers.get('Content-Disposition') or r.headers.get('content-disposition') or ''
    assert 'forgefps-agent.zip' in cd, f"Bad Content-Disposition: {cd}"
    assert 'attachment' in cd.lower()

    # ZIP integrity
    z = zipfile.ZipFile(io.BytesIO(body))
    bad = z.testzip()
    assert bad is None, f"ZIP corrupted at entry: {bad}"

    names = z.namelist()
    print(f"ZIP entries: {len(names)}")
    assert len(names) >= 60, f"Only {len(names)} entries (expected >=60)"

    # Launcher bat must be present with token
    assert 'forgefps-agent/Avvia-FrameForge.bat' in names, "Avvia-FrameForge.bat missing"

    # _ssl.pyd must be readable (the file 7-Zip complained about)
    assert 'forgefps-agent/_internal/_ssl.pyd' in names, "_ssl.pyd missing"
    ssl_bytes = z.read('forgefps-agent/_internal/_ssl.pyd')
    assert len(ssl_bytes) > 0, "_ssl.pyd empty"
    print(f"_ssl.pyd size: {len(ssl_bytes)}")

    # bat contains token line
    bat = z.read('forgefps-agent/Avvia-FrameForge.bat').decode('utf-8', errors='replace')
    assert 'FORGEFPS_TOKEN' in bat or 'TOKEN' in bat.upper(), f"bat missing token: {bat[:300]}"


def test_download_zip_second_request_same_size(auth_session):
    """Cache regression: second request must return identical Content-Length"""
    r1 = auth_session.get(f"{BASE_URL}/api/agent/download-zip", timeout=120)
    r2 = auth_session.get(f"{BASE_URL}/api/agent/download-zip", timeout=120)
    assert r1.status_code == 200 and r2.status_code == 200
    cl1 = int(r1.headers.get('Content-Length'))
    cl2 = int(r2.headers.get('Content-Length'))
    assert cl1 == cl2, f"Content-Length mismatch between requests: {cl1} vs {cl2}"
    assert len(r1.content) == cl1 and len(r2.content) == cl2


def test_launcher_bat_endpoint(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/agent/launcher-bat", timeout=30)
    assert r.status_code == 200, f"launcher-bat status {r.status_code}"
    body = r.text
    assert '.bat' in (r.headers.get('Content-Disposition') or '').lower() or len(body) > 0
    assert 'TOKEN' in body.upper() or 'FORGEFPS' in body.upper(), f"bat unexpected: {body[:200]}"


def test_auth_regression(auth_session):
    me = auth_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me.status_code == 200
    data = me.json()
    assert data.get('email') == ADMIN_EMAIL
