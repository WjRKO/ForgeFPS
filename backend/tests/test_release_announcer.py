"""Tests for release_announcer: manifest content, announce_new_releases idempotence,
and manual re-announce via announce_release_by_version.

Discord post_release is monkeypatched to avoid real HTTP calls.

NOTE: all async logic is run inside a single asyncio.run() to keep motor's client
bound to one event loop (avoids 'Event loop is closed' / 'different loop' issues
with pytest-asyncio + pytest-xdist).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app/backend")

os.environ["RELEASE_ANNOUNCER_ENABLED"] = "true"

MANIFEST_PATH = Path("/app/data/releases.json")
NEW_VERSIONS = ["0.6.14", "0.6.13", "0.6.10", "0.6.8", "0.6.7", "0.6.6"]
OLD_VERSIONS = ["0.6.5", "0.6.4", "0.6.3", "0.6.2", "0.6.1", "0.6.0"]


# ---- Manifest tests (sync) ----
def test_manifest_exists_and_has_12_versions():
    assert MANIFEST_PATH.exists()
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    versions = [r.get("version") for r in data]
    assert len(versions) == 12, f"Expected 12 versions, got {len(versions)}: {versions}"
    for v in NEW_VERSIONS + OLD_VERSIONS:
        assert v in versions, f"Missing version {v}"


def test_new_entries_have_required_fields():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_v = {r["version"]: r for r in data}
    for v in NEW_VERSIONS:
        r = by_v[v]
        assert r.get("version") == v
        assert r.get("date"), f"{v}: missing date"
        assert r.get("title"), f"{v}: missing title"
        assert r.get("notes_md"), f"{v}: empty notes_md"
        assert r.get("url"), f"{v}: missing url"


# ---- Announcer combined async test (single event loop) ----
def test_announcer_flow_end_to_end():
    """Runs the full announcer flow in a single asyncio loop:
    1) reset new_versions in db.announced_releases
    2) announce_new_releases() -> posts >=6, calls fake post_release for each new version
    3) idempotent: second run -> 0
    4) announce_release_by_version('0.6.14', force=True) -> ok
    5) announce_release_by_version('9.9.9') -> not found
    """
    import services.release_announcer as ra
    from database import db

    calls = []

    async def fake_post(version, notes_md, url):
        calls.append({"version": version, "url": url, "notes_len": len(notes_md)})
        return True

    original_post = ra.post_release
    ra.post_release = fake_post

    async def flow():
        results = {}
        # Cleanup: only new versions
        await db.announced_releases.delete_many({"_id": {"$in": NEW_VERSIONS}})

        # 1st run
        posted1 = await ra.announce_new_releases()
        results["posted1"] = posted1
        results["calls1_versions"] = [c["version"] for c in calls]

        # Verify DB entries for new versions
        missing_db = []
        for v in NEW_VERSIONS:
            doc = await db.announced_releases.find_one({"_id": v})
            if not doc or not doc.get("title") or not doc.get("announced_at"):
                missing_db.append(v)
        results["missing_db_new"] = missing_db

        # 2nd run (idempotent)
        calls.clear()
        posted2 = await ra.announce_new_releases()
        results["posted2"] = posted2
        results["calls2_count"] = len(calls)

        # Manual re-announce with force
        calls.clear()
        ok, msg = await ra.announce_release_by_version("0.6.14", force=True)
        results["force_ok"] = ok
        results["force_msg"] = msg
        results["force_calls"] = [c["version"] for c in calls]

        # Unknown version
        ok2, msg2 = await ra.announce_release_by_version("9.9.9", force=True)
        results["unknown_ok"] = ok2
        results["unknown_msg"] = msg2

        # Old versions still in manifest
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest_versions = [r.get("version") for r in data]
        results["old_present"] = all(v in manifest_versions for v in OLD_VERSIONS)

        return results

    try:
        r = asyncio.run(flow())
    finally:
        ra.post_release = original_post

    print("RESULTS:", json.dumps(r, indent=2, default=str))

    # Assertions
    assert r["posted1"] >= 6, f"1st run posted {r['posted1']}, expected >=6"
    for v in NEW_VERSIONS:
        assert v in r["calls1_versions"], f"post_release not called for {v}"
    assert r["missing_db_new"] == [], f"DB missing entries: {r['missing_db_new']}"

    assert r["posted2"] == 0, f"2nd run should be idempotent, got {r['posted2']}"
    assert r["calls2_count"] == 0

    assert r["force_ok"] is True, f"force re-announce failed: {r['force_msg']}"
    assert r["force_calls"].count("0.6.14") == 1

    assert r["unknown_ok"] is False
    assert "9.9.9" in r["unknown_msg"]

    assert r["old_present"] is True
