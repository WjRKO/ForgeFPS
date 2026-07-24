"""Regression: nuovi tweak (memcomp, hpet_off, spectre_off ecc.) presenti nel PS agent script."""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stream-gear-monitor.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "admin@boostpc.io"
ADMIN_PASSWORD = "4zWK4o_xSw5prU-2b7w9dQ"

NEW_TWEAK_IDS = [
    "memcomp",
    "auto_maint_night",
    "notif_fullscreen",
    "hpet_off",
    "bcd_dynamic_tick",
    "spectre_off",
]

NEW_DO_FUNCTIONS = [
    "function Do-MemComp",
    "function Do-AutoMaintNight",
    "function Do-NotifFullscreen",
    "function Do-HpetOff",
    "function Do-BcdDynamicTick",
    "function Do-SpectreOff",
    "function Backup-Bcd",
]


@pytest.fixture(scope="module")
def agent_token():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    r2 = s.get(f"{BASE_URL}/api/agent/token")
    assert r2.status_code == 200
    return r2.json()["token"]


def _fetch_script(agent_token):
    r = requests.get(f"{BASE_URL}/api/agent/script", params={"t": agent_token, "mode": "optimize"})
    assert r.status_code == 200
    return r.text


class TestNewTweaksPresent:
    @pytest.mark.parametrize("tid", NEW_TWEAK_IDS)
    def test_tweak_id_present(self, agent_token, tid):
        script = _fetch_script(agent_token)
        assert f"id='{tid}'" in script, f"Tweak id='{tid}' missing from PS script"

    @pytest.mark.parametrize("fn", NEW_DO_FUNCTIONS)
    def test_do_function_present(self, agent_token, fn):
        script = _fetch_script(agent_token)
        assert fn in script, f"{fn} missing from PS script"

    def test_restore_handles_bcd(self, agent_token):
        script = _fetch_script(agent_token)
        assert "bcd::" in script, "Invoke-Restore must handle bcd:: keys"
        assert "mmagent::mc" in script, "Invoke-Restore must handle mmagent::mc"

    def test_memcomp_gated_by_ram(self, agent_token):
        script = _fetch_script(agent_token)
        # fit gate su $script:HW.ram >= 32
        assert "$script:HW.ram -ge 32" in script

    def test_spectre_risk_labeled_extreme(self, agent_token):
        script = _fetch_script(agent_token)
        # Il nome deve contenere '[EXTREME]' per essere ben identificato in UI
        assert "[EXTREME] Spectre/Meltdown OFF" in script

    def test_new_tweaks_in_presets(self, agent_token):
        script = _fetch_script(agent_token)
        # Preset competitivo deve includere i nuovi safe tweaks
        assert "'memcomp'" in script
        assert "'notif_fullscreen'" in script
        assert "'auto_maint_night'" in script
