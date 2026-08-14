"""Gameplay Doctor v2 backend tests - POST + GET latest + regressions"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@boostpc.io"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


# Unit deterministic functions
def test_unit_gd_functions():
    from routers import advisor
    assert advisor._gd_pattern([10, 20, 30, 40]) == "periodic"
    assert advisor._gd_pattern([5]) == "isolated"
    assert advisor._gd_pattern([10, 12, 13, 300]) in ("burst", "sporadic")
    assert advisor._gd_hist_pct([0] * 59 + [1000], 0.99) == 350


def test_agent_latest_version_regression():
    r = requests.get(f"{BASE_URL}/api/agent/latest-version", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("version") == "0.8.0", data


def test_gameplay_doctor_post_v2(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/advisor/gameplay-doctor", json={"lang": "it"}, timeout=180)
    assert r.status_code == 200, r.text
    data = r.json()
    report = data.get("report") or {}
    stats = data.get("stats") or {}

    # executive_summary
    exec_sum = report.get("executive_summary") or {}
    assert exec_sum.get("main_problem"), f"missing main_problem: {report}"
    assert exec_sum.get("main_fix"), f"missing main_fix: {report}"

    # issues[]
    issues = report.get("issues") or []
    assert len(issues) >= 1, f"no issues: {report}"
    for iss in issues:
        for k in ("id", "confidence", "impact_pct", "pattern", "simple_text", "evidence", "diagnosis", "tech_detail", "fix"):
            assert k in iss, f"issue missing key {k}: {iss}"
        assert "primary" in (iss.get("fix") or {}), f"fix.primary missing: {iss}"

    # stats
    assert stats.get("exact_percentiles") is True, stats
    assert isinstance(stats.get("fps_1pct_low"), (int, float)), stats
    assert isinstance(stats.get("fps_01pct_low"), (int, float)), stats
    problems = stats.get("problems") or []
    if len(problems) >= 2:
        scores = [p.get("impact_score", 0) for p in problems]
        assert scores == sorted(scores, reverse=True), scores

    # baseline / resolved / timeline
    assert "baseline" in data, list(data.keys())
    assert "resolved" in data and isinstance(data["resolved"], list)
    tl = data.get("timeline") or {}
    fps_pts = tl.get("fps") or []
    assert len(fps_pts) >= 100, f"timeline.fps len={len(fps_pts)}"
    assert "events" in tl


def test_gameplay_doctor_get_latest(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/advisor/gameplay-doctor/latest", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "report" in data
    doc = data["report"]
    assert doc is not None, "no persisted doc"
    assert "timeline" in doc
    assert "baseline" in doc
    assert "resolved" in doc
    assert (doc.get("timeline") or {}).get("fps"), "timeline.fps missing"
