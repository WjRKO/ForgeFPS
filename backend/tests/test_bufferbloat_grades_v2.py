"""Regression: grade_bufferbloat v2 con 3 sub-grade (Idle/Loaded/Consistency) + p99."""
import pytest
from helpers import grade_bufferbloat


class TestIdleGrade:
    @pytest.mark.parametrize("idle,expected", [
        (5, "A+"), (15, "A+"), (20, "A"), (25, "A"),
        (35, "B"), (45, "B"), (60, "C"), (80, "C"),
        (100, "D"), (150, "D"), (200, "F"), (400, "F"),
    ])
    def test_idle_thresholds(self, idle, expected):
        r = grade_bufferbloat({"idle_ms": idle, "down_ms": idle, "up_ms": idle})
        assert r["idle_grade"] == expected


class TestLoadedGrade:
    def test_no_bloat_gets_aplus(self):
        r = grade_bufferbloat({"idle_ms": 10, "down_ms": 12, "up_ms": 13})
        assert r["loaded_grade"] == "A+"
        assert r["grade"] == "A+"  # legacy retro-compat

    def test_severe_bloat_gets_f(self):
        r = grade_bufferbloat({"idle_ms": 20, "down_ms": 500, "up_ms": 100})
        assert r["loaded_grade"] == "F"

    def test_moderate_bloat_gets_c(self):
        # inc = max(180-20, 30-20) = 160 -> C
        r = grade_bufferbloat({"idle_ms": 20, "down_ms": 180, "up_ms": 30})
        assert r["loaded_grade"] == "C"


class TestConsistencyGrade:
    def test_clean_line_gets_aplus(self):
        r = grade_bufferbloat({
            "idle_ms": 10, "down_ms": 12, "up_ms": 13,
            "down_p99": 15, "up_p99": 15,
            "jitter_ms": 1, "loss_pct": 0,
        })
        assert r["consistency_grade"] == "A+"
        assert r["consistency_score"] == 100

    def test_high_loss_kills_consistency(self):
        r = grade_bufferbloat({
            "idle_ms": 10, "down_ms": 12, "up_ms": 13,
            "jitter_ms": 0, "loss_pct": 6,  # -60
        })
        assert r["consistency_grade"] in ("D", "F")

    def test_moderate_jitter_and_tail_spike(self):
        # jitter 20 -> -25, tail spike 250 -> -20 = 55 -> C
        r = grade_bufferbloat({
            "idle_ms": 10, "down_ms": 30, "up_ms": 30,
            "down_p99": 260, "up_p99": 40,  # tail spike max = 250
            "jitter_ms": 20, "loss_pct": 0,
        })
        assert r["consistency_score"] == 55
        assert r["consistency_grade"] == "C"


class TestP99Passthrough:
    def test_p99_fields_preserved_in_output(self):
        r = grade_bufferbloat({
            "idle_ms": 10, "down_ms": 15, "up_ms": 15,
            "down_p99": 80, "up_p99": 60,
        })
        assert r["down_p99"] == 80
        assert r["up_p99"] == 60
        assert r["tail_spike_ms"] == 70  # 80 - 10

    def test_no_p99_no_crash(self):
        r = grade_bufferbloat({"idle_ms": 10, "down_ms": 15, "up_ms": 15})
        assert r["tail_spike_ms"] is None
        # Still gets consistency grade (fallback su jitter/loss only)
        assert r["consistency_grade"] in ("A+", "A", "B", "C", "D", "F")


class TestRetroCompat:
    def test_legacy_grade_field_still_present(self):
        r = grade_bufferbloat({"idle_ms": 10, "down_ms": 20, "up_ms": 20})
        assert "grade" in r
        assert "down_grade" in r
        assert "up_grade" in r
        assert "base_quality" in r
        assert "loss_pct" in r

    def test_new_grades_added(self):
        r = grade_bufferbloat({"idle_ms": 10, "down_ms": 20, "up_ms": 20})
        assert "idle_grade" in r
        assert "loaded_grade" in r
        assert "consistency_grade" in r
        assert "consistency_score" in r
        assert "tail_spike_ms" in r
