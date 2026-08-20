"""routers/lab: ingestione dei run, guardie, confronto appaiato e correzione Holm.

Solo funzioni pure del modulo: nessun database, nessun backend vivo. La
simulazione end-to-end del protocollo sta in tests/test_lab_phase1_sim.py.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lab_stats
from routers import lab as L


def _run(fps, p1=None, frames=12000, game="cs2.exe", ctx=None, hist=True):
    """Un run come lo manda l'agent, istogramma incluso."""
    ft = 1000.0 / fps
    out = {"fps_avg": fps, "ft_avg_ms": round(ft, 3), "frames": frames,
           "duration_s": 90, "game": game}
    if p1:
        out["fps_p1"] = p1
    if hist:
        n_slow = max(1, frames // 100)
        out["hist"] = lab_stats.build_hist([ft] * (frames - n_slow) +
                                           [1000.0 / (p1 or fps * 0.8)] * n_slow)
    if ctx:
        out["ctx"] = ctx
    return out


# ---------- ingestione ----------

def test_istogramma_e_contesto_sopravvivono_all_ingestione():
    """Prima il filtro teneva solo gli scalari: istogramma e contesto venivano
    buttati in silenzio."""
    run = L._ingest_run(_run(120, 90, ctx={"res_w": 2560, "on_battery": False}))
    assert len(run["hist"]) == lab_stats.HIST_BUCKETS
    assert run["ctx"]["res_w"] == 2560
    assert run["metrics_version"] == L.METRICS_VERSION


def test_contesto_accetta_solo_le_chiavi_dichiarate():
    run = L._ingest_run(_run(120, ctx={"res_w": 1920, "hack": "x", "nested": {"a": 1}}))
    assert set(run["ctx"]) == {"res_w"}


def test_istogramma_malformato_ignorato_senza_rompere():
    raw = _run(120, hist=False)
    raw["hist"] = ["non", "numeri"]
    run = L._ingest_run(raw)
    assert "hist" not in run


def test_percentili_ricalcolati_dal_backend():
    """L'1% low che conta e' quello calcolato sull'istogramma, non quello che
    l'agent ha messo nel campo."""
    raw = _run(120, 90)
    raw["fps_p1"] = 999.0            # valore assurdo mandato dall'agent
    run = L._ingest_run(raw)
    assert run["fps_p1"] < 200


# ---------- statistiche di blocco ----------

def test_percentili_di_blocco_dalla_somma_degli_istogrammi():
    runs = [L._ingest_run(_run(120, 90)), L._ingest_run(_run(121, 60))]
    stats = L._run_stats(runs)
    assert stats["metrics_version"] == 2
    assert stats["frames"] == 24000
    # L'1% peggiore del blocco sono 240 frame: i 120 lenti di un run piu' i 120
    # dell'altro. Il valore giusto e' 1000 / media dei loro frametime, non la
    # media dei due 1% low per-run.
    atteso = 1000.0 / ((1000.0 / 90 + 1000.0 / 60) / 2)
    assert abs(stats["fps_p1"] - atteso) < 1.0
    assert abs(stats["fps_p1"] - (90 + 60) / 2) > 2.0


def test_agent_vecchio_senza_istogramma_resta_supportato():
    runs = [L._ingest_run(_run(120, 90, hist=False)),
            L._ingest_run(_run(122, 94, hist=False))]
    stats = L._run_stats(runs)
    assert stats["metrics_version"] == 1
    assert stats["fps_p1"] == 92.0


# ---------- guardie sui run ----------

def _sess(**kw):
    s = {"user_id": "u1", "paired": True, "quality": {}, "results": [], "kept": [],
         "logs": [], "candidates": [], "queue": [],
         "baseline": {"runs": [], "stats": {"fps_avg": 120.0, "game": "cs2.exe"},
                      "ref_ctx": {"res_w": 2560, "res_h": 1440, "refresh_hz": 165}}}
    s.update(kw)
    return s


def test_run_a_batteria_rifiutato():
    """Su batteria CPU e GPU sono limitate: non e' un dato rumoroso, e' un dato
    di un'altra macchina."""
    run = L._ingest_run(_run(90, ctx={"on_battery": True}))
    reject, _ = L._run_guard(_sess(), run, "test")
    assert reject["code"] == "on_battery" and "batteria" in reject["msg"]


def test_gioco_diverso_dalla_baseline_rifiutato():
    run = L._ingest_run(_run(120, game="valorant.exe"))
    reject, _ = L._run_guard(_sess(), run, "test")
    assert reject["code"] == "other_game" and "valorant.exe" in reject["msg"]


def test_pochi_frame_rifiutati():
    run = L._ingest_run(_run(120, frames=120))
    reject, _ = L._run_guard(_sess(), run, "test")
    assert reject["code"] == "few_frames" and "frame" in reject["msg"]


def test_risoluzione_cambiata_e_solo_un_avviso():
    """Rifiutare bloccherebbe l'utente; segnalarlo lascia la traccia nel report."""
    run = L._ingest_run(_run(120, ctx={"res_w": 1920, "res_h": 1080, "refresh_hz": 165}))
    reject, warns = L._run_guard(_sess(), run, "test")
    assert reject is None
    assert any("risoluzione" in w for w in warns)


def test_baseline_non_confrontata_con_se_stessa():
    """Durante la baseline non esiste ancora un riferimento da rispettare."""
    run = L._ingest_run(_run(120, game="valorant.exe"))
    reject, _ = L._run_guard(_sess(), run, "baseline")
    assert reject is None


# ---------- schema appaiato ----------

def test_sequenza_abba():
    """Ordine alternato: la deriva lineare non regala il vantaggio sempre allo
    stesso lato, e le coppie contigue condividono lo stato (meno commutazioni)."""
    assert L._pair_stages(3) == ["on", "off", "off", "on", "on", "off"]
    cambi = sum(1 for a, b in zip(L._pair_stages(3), L._pair_stages(3)[1:]) if a != b)
    assert cambi == 3


def test_tweak_con_riavvio_non_e_appaiabile():
    assert L._is_paired(_sess(), {"requires_reboot": False}) is True
    assert L._is_paired(_sess(), {"requires_reboot": True}) is False
    assert L._is_paired(_sess(paired=False), {"requires_reboot": False}) is False


def _cur_paired(on, off):
    return {"tweak_id": "power", "applied": True, "runs": [], "stage_state": "off",
            "on_runs": [L._ingest_run(_run(f, f * 0.8)) for f in on],
            "off_runs": [L._ingest_run(_run(f, f * 0.8)) for f in off]}


def test_confronto_appaiato_su_una_deriva_comune():
    """+2 FPS reali mentre il PC si scalda di 6 FPS: lo schema appaiato lo vede."""
    comp = L._paired_compare(_cur_paired(on=[102.1, 99.0, 95.9], off=[100, 97, 94]))
    assert comp["design"] == "paired_abba"
    assert comp["n_pairs"] == 3
    assert comp["sig"]["significant"] is True
    assert 1.5 < comp["delta"]["fps_avg_pct"] < 2.5
    lo, hi = comp["delta"]["fps_ci_pct"]
    assert lo > 0                      # l'intervallo esclude lo zero


def test_confronto_appaiato_senza_effetto():
    comp = L._paired_compare(_cur_paired(on=[100.4, 99.6, 100.1], off=[100.0, 100.2, 99.8]))
    assert comp["sig"]["significant"] is False


def test_coppie_incomplete_non_producono_un_verdetto():
    assert L._paired_compare(_cur_paired(on=[100], off=[99])) is None


# ---------- verdetto ----------

def _comp(delta_pct, p, p1_pct=None, p1_sig=False):
    return {"design": "paired_abba", "n_pairs": 3,
            "delta": {"fps_avg_pct": delta_pct, "fps_p1_pct": p1_pct},
            "sig": {"p_value": p, "alpha": 0.10, "significant": p < 0.10},
            "sig_p1": {"p_value": 0.01 if p1_sig else 0.9, "alpha": 0.10,
                       "significant": p1_sig}}


def test_effetto_significativo_e_sopra_soglia_viene_mantenuto():
    kept, basis, _ = L._verdict(_comp(3.0, 0.01))
    assert kept and basis == "fps"


def test_effetto_significativo_ma_sotto_soglia_no():
    kept, _, reason = L._verdict(_comp(0.4, 0.01))
    assert not kept and "trascurabile" in reason


def test_piu_fps_ma_meno_fluidita_viene_scartato():
    kept, basis, _ = L._verdict(_comp(4.0, 0.01, p1_pct=-8.0))
    assert not kept and basis == "stutter_guard"


def test_fluidita_da_sola_puo_bastare():
    kept, basis, _ = L._verdict(_comp(0.1, 0.9, p1_pct=6.0, p1_sig=True))
    assert kept and basis == "fluidity"


def test_il_verdetto_riporta_l_intervallo():
    comp = _comp(3.0, 0.01)
    comp["delta"]["fps_ci_pct"] = [1.2, 4.8]
    _, _, reason = L._verdict(comp)
    assert "IC 95%" in reason


# ---------- correzione per test multipli ----------

def _result(tid, p, decision="kept"):
    return {"tweak_id": tid, "decision": decision, "reason": "significativo",
            "significance": {"p_value": p, "significant": p < 0.10}, "delta": {"fps_avg_pct": 2.0}}


def test_holm_annulla_i_mantenuti_che_non_reggono(monkeypatch):
    """Con dieci test ad alpha 0.10 qualche falso positivo esce per forza, e
    ognuno diventa lo stato su cui si misura il successivo."""
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(L, "_fleet_demote", _noop)
    sess = _sess(results=[_result("power", 0.001), _result("timer", 0.08)] +
                         [_result(f"x{i}", 0.5, "rolled_back") for i in range(8)],
                 kept=["power", "timer"])
    demoted = asyncio.run(L._apply_holm(sess))
    assert demoted == ["timer"]          # 0.08 x 10 ipotesi non regge
    assert sess["kept"] == ["power"]
    assert sess["pending_rollback"] == ["timer"]
    assert sess["results"][1]["decision"] == "rolled_back"
    assert sess["results"][1]["demoted"] is True
    assert sess["final_estimate_stale"] is True


def test_holm_lascia_stare_chi_regge(monkeypatch):
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(L, "_fleet_demote", _noop)
    sess = _sess(results=[_result("power", 0.001), _result("gaming", 0.002)],
                 kept=["power", "gaming"])
    assert asyncio.run(L._apply_holm(sess)) == []
    assert sess["kept"] == ["power", "gaming"]
    assert not sess.get("pending_rollback")


# ---------- chiave di gioco ----------

def test_slug_utilizzabile_come_campo_mongo():
    assert L._slug("Counter-Strike 2.exe") == "counter_strike_2_exe"
    assert L._slug("") is None
    assert "." not in (L._slug("a.b.c") or "")


def test_il_codice_di_rifiuto_e_usabile_come_chiave_mongo():
    """Il messaggio contiene il nome del gioco, e 'cs2.exe' ha un punto: come
    chiave di un contatore Mongo farebbe fallire la scrittura della sessione."""
    run = L._ingest_run(_run(120, game="valorant.exe"))
    reject, _ = L._run_guard(_sess(), run, "test")
    assert "." not in reject["code"] and "$" not in reject["code"]


def test_la_demozione_non_sottrae_un_contributo_mai_dato(monkeypatch):
    """Se il risultato non era entrato nell'aggregato (quota utente esaurita),
    toglierlo lascerebbe piu' successi annullati che registrati."""
    calls = []

    async def _spy(query, update):
        calls.append((query, update))

    class _FakeStats:
        update_one = staticmethod(_spy)

    monkeypatch.setattr(L.db, "lab_fleet_stats", _FakeStats, raising=False)
    sess = _sess(hw_class="nvidia_amd", hw_family="ryzen-7|rtx-30")
    asyncio.run(L._fleet_demote(sess, "power", "cs2.exe"))
    assert calls == []

    sess["fleet_counted"] = ["power"]
    asyncio.run(L._fleet_demote(sess, "power", "cs2.exe"))
    assert len(calls) == 2                       # vendor + famiglia
    assert calls[0][1]["$inc"]["kept"] == -1
    assert calls[0][1]["$inc"]["games.cs2_exe.kept"] == -1
