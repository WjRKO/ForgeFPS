"""Laboratorio Automatico delle Prestazioni - Fase 1.

Backend orchestrator: il PS agent (mode=lab) fa polling di /api/agent/lab/next
ed esegue le azioni; il backend persiste lo stato, calcola CV/delta/statistica e
decide kept/rolled_back, auto-stop e report finale.
Pipeline: SNAPSHOT -> BASELINE (3 run, CV check) -> TEST_LOOP -> REPORT.

Schema di misura (v2). Il test di un tweak e' APPAIATO: invece di confrontare
tre run col tweak attivo contro un blocco di baseline misurato minuti prima, si
alternano coppie ON/OFF in sequenza ABBA e si analizzano le differenze interne
a ogni coppia. Cosi' la deriva comune (temperatura, scena, shader cache) si
cancella invece di finire nel confronto. Lo schema a blocchi resta per i tweak
che richiedono un riavvio, dove alternare non e' possibile, e per le sessioni
avviate con `paired=false`.
"""
import logging
import math
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header

from database import db, now_iso
from models import LabStartInput, LabRunInput, LabEventInput, LabCheckInput
from lab_registry import REGISTRY_VERSION, TWEAKS, select_candidates, bios_suggestions
from lab_stats import (mean, cv, sample_var, significance, welch_ci, cohens_d, holm_adjust,
                       wilson_ci, paired_significance, paired_ci, hist_add, hist_total,
                       hist_fps_metrics, frame_cap_signature, HIST_BUCKETS)
import hardware

logger = logging.getLogger("boostpc.lab")

FLEET_MIN_SAMPLES = 3
# Un solo utente che lancia dieci sessioni non e' una flotta: oltre questa
# soglia i suoi test non entrano piu' nell'aggregato anonimo per quel tweak.
FLEET_MAX_PER_USER = 3

BASELINE_RUNS = 3
TEST_RUNS = 3
PAIR_RUNS = 3
CV_MAX = 0.05
MIN_EFFECT_PCT = 1.0
# Versione dello schema di metriche: dalla 2 `fps_p1` e' la media dell'1%
# peggiore dei frame (non il p99 puntuale) e arriva dall'istogramma sommato dei
# run. Confrontare un riferimento v1 con una misura v2 sul solo 1% low darebbe
# una differenza che non e' un cambiamento del PC ma della definizione.
METRICS_VERSION = 2
MIN_RUN_FRAMES = 300
HOLM_ALPHA = 0.10
MAX_RUN_REJECTS = 3
AUTO_STOP_WINDOW = 3
MARGINAL_GAIN_RATIO = 0.03
SYNERGY_RUNS = 2
SYNERGY_MAX_PAIRS = 2
SYNERGY_FACTOR = 1.15
VALIDATION_SECONDS = 300
VALIDATION_MIN_RATIO = 0.5
WARMUP_SECONDS = 45
CHECK_RUNS = 2
REGRESSION_PCT = -5.0
STUTTER_KEEP_PCT = 3.0
STUTTER_GUARD_PCT = -5.0
FPS_NEUTRAL_PCT = -0.5

ACTIVE_STATUSES = ("waiting_agent", "snapshot", "baseline", "testing", "awaiting_reboot",
                   "rollback", "synergy", "validation", "aborting")


def _pair_stages(n_pairs=PAIR_RUNS):
    """Sequenza ABBA delle coppie: on/off, off/on, on/off...

    L'ordine alternato cancella anche la deriva lineare dentro il blocco (se il
    PC si scalda progressivamente, mettere sempre ON per primo regalerebbe al
    tweak il vantaggio del PC piu' freddo). In piu' le coppie contigue
    condividono lo stato: servono 3 commutazioni invece di 6.
    """
    out = []
    for k in range(n_pairs):
        out.extend(("on", "off") if k % 2 == 0 else ("off", "on"))
    return out


def _is_paired(sess, tweak):
    """Un tweak si testa appaiato solo se lo si puo' spegnere e riaccendere.

    Quelli che richiedono un riavvio no: alternare costerebbe un reboot per run.
    """
    return bool(sess.get("paired", True)) and not (tweak or {}).get("requires_reboot")


# Definizione unica in hardware.py: la usa anche l'Advisor per leggere lo stesso
# aggregato di flotta con le stesse chiavi.
_hw_class = hardware.vendor_class


async def _fleet_blend(candidates, hw, hw_family=None):
    """Fase 3: fonde il prior statico con lo storico aggregato anonimo della fleet.

    Due livelli di granularita': `hw_family` ('ryzen-7|rtx-30') e' piu' predittivo
    ma si popola lentamente; `hw` e' il raggruppamento per vendor ('nvidia_amd'),
    grossolano ma con molti piu' campioni. Si preferisce la famiglia quando ha
    abbastanza test, altrimenti si ricade sul vendor.
    """
    fleet = {}
    async for d in db.lab_fleet_stats.find({"hw_class": hw, "scope": {"$ne": "family"}}):
        fleet[d["tweak_id"]] = d
    if hw_family:
        async for d in db.lab_fleet_stats.find({"hw_class": hw_family, "scope": "family"}):
            if int(d.get("tested") or 0) >= FLEET_MIN_SAMPLES:
                fleet[d["tweak_id"]] = d
    used = 0
    for c in candidates:
        f = fleet.get(c["tweak_id"])
        if f and f.get("tested", 0) >= FLEET_MIN_SAMPLES:
            rate = max(0.05, min(0.9, f["kept"] / f["tested"]))
            w = min(0.7, f["tested"] / (f["tested"] + 10))
            c["prior"] = round((1 - w) * c["prior"] + w * rate, 3)
            c["fleet"] = {"tested": f["tested"], "kept": f["kept"],
                          "avg_delta_pct": round((f.get("delta_sum") or 0) / f["tested"], 2),
                          "scope": f.get("scope") or "vendor"}
            used += 1
    candidates.sort(key=lambda c: (bool(c.get("requires_reboot")), -c["prior"]))
    return used


async def _fleet_quota_ok(sess, tweak_id):
    """Quante volte questo utente ha gia' contribuito all'aggregato per il tweak.

    Senza questo contatore un solo utente che rilancia il Lab dieci volte pesa
    dieci volte nella statistica 'misurato su hardware simile': pseudo-
    replicazione, cioe' un campione che sembra grande e non lo e'.
    """
    uid = sess.get("user_id")
    if not uid:
        return True
    try:
        doc = await db.lab_fleet_seen.find_one_and_update(
            {"user_id": uid, "tweak_id": tweak_id},
            {"$inc": {"n": 1}, "$set": {"last_at": now_iso()}},
            upsert=True, return_document=True)
    except Exception as exc:  # find_one_and_update non disponibile: non bloccare il Lab
        logger.debug("quota fleet non verificabile: %s", exc)
        return True
    n = int((doc or {}).get("n") or 1)
    return n <= FLEET_MAX_PER_USER


async def _fleet_update(sess, tweak_id, kept, delta_pct, game):
    """Accumula il risultato nell'aggregato anonimo, con i contrappesi che servono.

    - niente contributo dalle sessioni marcate di bassa qualita' (frame cap
      attivo: li' ogni tweak risulta ininfluente per costruzione);
    - `delta_sq_sum` accanto a `delta_sum`, cosi' chi legge puo' calcolare una
      varianza invece di fidarsi di una media nuda;
    - breakdown per gioco: un tweak puo' aiutare in un titolo CPU-bound e non
      fare nulla in uno GPU-bound, e la media dei due non descrive nessuno.
    """
    if (sess.get("quality") or {}).get("capped"):
        return False
    if not await _fleet_quota_ok(sess, tweak_id):
        _log(sess, f"{tweak_id}: risultato non aggiunto alla statistica di flotta "
                   f"(gia' {FLEET_MAX_PER_USER} test tuoi su questo tweak)")
        return False
    d = float(delta_pct or 0.0)
    inc = {"tested": 1, "kept": 1 if kept else 0, "delta_sum": d, "delta_sq_sum": d * d}
    gk = _slug(game)
    if gk:
        inc[f"games.{gk}.tested"] = 1
        inc[f"games.{gk}.kept"] = 1 if kept else 0
        inc[f"games.{gk}.delta_sum"] = d
    await db.lab_fleet_stats.update_one(
        {"tweak_id": tweak_id, "hw_class": sess.get("hw_class", "other_other"),
         "scope": {"$ne": "family"}},
        {"$inc": inc, "$setOnInsert": {"scope": "vendor"}}, upsert=True)
    if sess.get("hw_family"):
        await db.lab_fleet_stats.update_one(
            {"tweak_id": tweak_id, "hw_class": sess["hw_family"], "scope": "family"},
            {"$inc": inc}, upsert=True)
    # Traccia di chi e' finito davvero nell'aggregato: senza, una demozione
    # potrebbe sottrarre un 'kept' che questa sessione non aveva mai aggiunto.
    sess.setdefault("fleet_counted", []).append(tweak_id)
    return True


def _log(sess, msg, level="info"):
    sess.setdefault("logs", []).append({"ts": now_iso(), "msg": msg, "level": level})
    sess["logs"] = sess["logs"][-120:]


def _fps_list(runs, key="fps_avg"):
    return [r.get(key) for r in runs if isinstance(r.get(key), (int, float))]


# Contesto del run che l'agent puo' allegare. Whitelist esplicita: quello che
# arriva dall'agent finisce nel documento di sessione e nel report, non si
# accetta un dict libero.
_CTX_KEYS = ("res_w", "res_h", "refresh_hz", "on_battery", "power_plan", "obs_running",
             "gpu_driver", "cpu_pct_avg", "cpu_pct_max", "gpu_pct_avg", "gpu_pct_max",
             "temp_cpu_avg", "temp_cpu_max", "temp_gpu_avg", "temp_gpu_max",
             "gpu_clock_avg", "gpu_power_avg", "telemetry_samples", "process_id")


def _ingest_run(raw):
    """Normalizza il run inviato dall'agent.

    Prima qui passavano solo i valori scalari: l'istogramma dei frametime e il
    contesto (risoluzione, alimentazione, telemetria media) venivano scartati in
    silenzio dal filtro. Ora entrambi hanno una forma dichiarata e validata.
    """
    run = {k: v for k, v in (raw or {}).items()
           if isinstance(v, (int, float, str, bool)) and k not in ("hist", "ctx")}
    hist = (raw or {}).get("hist")
    if isinstance(hist, list) and 0 < len(hist) <= HIST_BUCKETS:
        try:
            run["hist"] = [max(0, int(x or 0)) for x in hist]
        except (TypeError, ValueError):
            pass
    ctx = (raw or {}).get("ctx")
    if isinstance(ctx, dict):
        clean = {k: v for k, v in ctx.items()
                 if k in _CTX_KEYS and isinstance(v, (int, float, str, bool))}
        if clean:
            run["ctx"] = clean
    # Con l'istogramma i percentili li calcola il backend: quelli mandati
    # dall'agent restano solo come valore per-run diagnostico.
    if run.get("hist"):
        m = hist_fps_metrics(run["hist"])
        for k in ("fps_p1", "fps_p01", "ft_median_ms"):
            if m.get(k) is not None:
                run[k] = m[k]
        run["frames"] = m.get("frames", run.get("frames"))
        run["metrics_version"] = METRICS_VERSION
    run["at"] = now_iso()
    return run


def _pooled_hist(runs):
    acc = None
    for r in runs:
        acc = hist_add(acc, r.get("hist"))
    return acc


def _run_stats(runs):
    """Statistiche di un blocco di run.

    `fps_avg` resta la media delle medie dei run: l'unita' di indipendenza e' il
    run, non il singolo frame (i frame dentro un run sono fortemente
    autocorrelati e trattarli come indipendenti gonfierebbe n di tre ordini di
    grandezza). I percentili invece vengono dall'istogramma sommato di tutti i
    run del blocco: la media dei percentili dei singoli run non e' il percentile
    del blocco.
    """
    fps = _fps_list(runs)
    lat = _fps_list(runs, "latency_ms")
    out = {
        "fps_avg": round(mean(fps), 2) if fps else None,
        "fps_p1": None,
        "latency_ms": round(mean(lat), 2) if lat else None,
        "cv_pct": round(cv(fps) * 100, 2) if fps else None,
        "runs": len(runs),
        "game": (runs[-1].get("game") if runs else None),
    }
    pooled = _pooled_hist(runs)
    if pooled and hist_total(pooled) > 0:
        m = hist_fps_metrics(pooled)
        out["fps_p1"] = m.get("fps_p1")
        out["fps_p01"] = m.get("fps_p01")
        out["ft_median_ms"] = m.get("ft_median_ms")
        out["frames"] = m.get("frames")
        out["metrics_version"] = METRICS_VERSION
    else:
        # Agent vecchio (nessun istogramma): resta la media dei p1 per-run.
        p1 = _fps_list(runs, "fps_p1")
        out["fps_p1"] = round(mean(p1), 2) if p1 else None
        out["metrics_version"] = 1
    return out


def _block_quality(runs):
    """Cap del framerate e frame totali di un blocco: dice se la misura e' cieca."""
    pooled = _pooled_hist(runs)
    if not pooled:
        return {}
    q = frame_cap_signature(pooled)
    q["frames"] = hist_total(pooled)
    return q


def _run_guard(sess, run, phase):
    """Condizioni sotto cui il run non e' confrontabile con gli altri.

    Ritorna (reject, warnings), dove `reject` e' None oppure
    {"code": ..., "msg": ...}. Il codice serve a contare i rifiuti per causa
    senza usare il messaggio come chiave: contiene il nome del gioco, e i punti
    di 'cs2.exe' non sono ammessi in una chiave Mongo.

    Un run rifiutato viene ripetuto: dopo MAX_RUN_REJECTS rifiuti per la stessa
    causa si accetta comunque, marcandolo, per non intrappolare l'utente in un
    ciclo infinito.
    """
    warns = []
    ctx = run.get("ctx") or {}
    frames = run.get("frames") or 0
    if frames and frames < MIN_RUN_FRAMES:
        return {"code": "few_frames",
                "msg": f"solo {frames} frame raccolti (minimo {MIN_RUN_FRAMES})"}, warns
    if ctx.get("on_battery"):
        return {"code": "on_battery",
                "msg": "PC a batteria: la CPU e la GPU sono limitate, la misura non e' confrontabile"}, warns
    ref = (sess.get("baseline") or {}).get("ref_ctx") or {}
    ref_game = ((sess.get("baseline") or {}).get("stats") or {}).get("game")
    game = run.get("game")
    if phase != "baseline" and ref_game and game and game != ref_game:
        return {"code": "other_game",
                "msg": f"gioco diverso dalla baseline ({game} invece di {ref_game})"}, warns
    for key, label in (("res_w", "risoluzione"), ("res_h", "risoluzione"), ("refresh_hz", "refresh")):
        if ref.get(key) and ctx.get(key) and ref[key] != ctx[key]:
            warns.append(f"{label} cambiata rispetto alla baseline ({ref[key]} -> {ctx[key]})")
            break
    if ctx.get("obs_running") and not ref.get("obs_running"):
        warns.append("OBS in esecuzione durante il run ma non durante la baseline")
    if ctx.get("power_plan") and ref.get("power_plan") and ctx["power_plan"] != ref["power_plan"]:
        warns.append(f"piano energetico cambiato ({ref['power_plan']} -> {ctx['power_plan']})")
    return None, warns


def _slug(s):
    """Chiave di gioco utilizzabile come campo Mongo (niente punti ne' $)."""
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").lower()).strip("_")[:40] or None


def _delta_pct(a, b):
    if not a or not b or b == 0:
        return None
    return round((a - b) / b * 100, 2)


def _pair_lists(cur, key="fps_avg"):
    """Valori ON/OFF allineati per coppia. Ritorna (on, off) o (None, None).

    L'i-esimo elemento di `on_runs` e quello di `off_runs` appartengono alla
    stessa coppia anche con la sequenza ABBA: ogni coppia contribuisce un run
    per lista, nell'ordine in cui e' stata misurata.
    """
    on_runs, off_runs = cur.get("on_runs") or [], cur.get("off_runs") or []
    n = min(len(on_runs), len(off_runs))
    if n < 2:
        return None, None
    on = _fps_list(on_runs[:n], key)
    off = _fps_list(off_runs[:n], key)
    if len(on) != n or len(off) != n:
        return None, None
    return on, off


def _paired_compare(cur):
    """Confronto appaiato ON vs OFF sulle differenze interne a ogni coppia."""
    on, off = _pair_lists(cur)
    if not on:
        return None
    n = len(on)
    diffs = [on[i] - off[i] for i in range(n)]
    ref = mean(off)
    sig = paired_significance(diffs)
    delta = {"fps_avg_pct": round(mean(diffs) / ref * 100, 2) if ref else None}
    ci = paired_ci(diffs)
    if ci and ref:
        delta["fps_ci_pct"] = [round(ci[1] / ref * 100, 2), round(ci[2] / ref * 100, 2)]
    sd = math.sqrt(sample_var(diffs))
    if sd > 0:
        # d_z: effect size della differenza appaiata, non della differenza fra gruppi.
        delta["effect_d"] = round(mean(diffs) / sd, 2)
    sig_p1 = None
    on1, off1 = _pair_lists(cur, "fps_p1")
    if on1:
        d1 = [on1[i] - off1[i] for i in range(len(on1))]
        r1 = mean(off1)
        sig_p1 = paired_significance(d1)
        delta["fps_p1_pct"] = round(mean(d1) / r1 * 100, 2) if r1 else None
    onl, offl = _pair_lists(cur, "latency_ms")
    if onl:
        delta["latency_ms"] = round(mean([onl[i] - offl[i] for i in range(len(onl))]), 2)
    on_stats = _run_stats((cur.get("on_runs") or [])[:n])
    return {"design": "paired_abba", "n_pairs": n, "sig": sig, "sig_p1": sig_p1,
            "delta": delta, "before_fps": round(ref, 2), "after_fps": round(mean(on), 2),
            "after_stats": on_stats, "runs": (cur.get("on_runs") or []) + (cur.get("off_runs") or [])}


def _blocked_compare(sess, cur):
    """Confronto a blocchi contro la baseline corrente (schema legacy).

    La baseline di riferimento e' quella AGGIORNATA dopo ogni tweak mantenuto:
    prima il p-value usava i run della baseline iniziale mentre il delta usava
    le statistiche aggiornate, cioe' due domande diverse nello stesso verdetto.
    """
    base_stats = sess["baseline"]["stats"]
    base_fps = _fps_list(sess["baseline"]["runs"])
    test_fps = _fps_list(cur["runs"])
    test_stats = _run_stats(cur["runs"])
    sig = significance(test_fps, base_fps)
    base_p1 = _fps_list(sess["baseline"]["runs"], "fps_p1")
    test_p1 = _fps_list(cur["runs"], "fps_p1")
    sig_p1 = significance(test_p1, base_p1) if len(base_p1) >= 2 and len(test_p1) >= 2 else None
    delta = {
        "fps_avg_pct": _delta_pct(test_stats["fps_avg"], base_stats["fps_avg"]),
        "fps_p1_pct": _delta_pct(test_stats["fps_p1"], base_stats["fps_p1"]),
    }
    ci = welch_ci(test_fps, base_fps)
    if ci and base_stats.get("fps_avg"):
        bm = base_stats["fps_avg"]
        delta["fps_ci_pct"] = [round(ci[1] / bm * 100, 2), round(ci[2] / bm * 100, 2)]
    eff = cohens_d(test_fps, base_fps)
    if eff is not None:
        delta["effect_d"] = eff
    if test_stats.get("latency_ms") is not None and base_stats.get("latency_ms") is not None:
        delta["latency_ms"] = round(test_stats["latency_ms"] - base_stats["latency_ms"], 2)
    return {"design": "blocked", "n_pairs": None, "sig": sig, "sig_p1": sig_p1,
            "delta": delta, "before_fps": base_stats["fps_avg"], "after_fps": test_stats["fps_avg"],
            "after_stats": test_stats, "runs": cur["runs"]}


def _verdict(comp):
    """Da confronto a decisione. Identica per i due schemi: cambia solo come si
    e' arrivati a `sig` e `delta`."""
    delta, sig, sig_p1 = comp["delta"], comp["sig"], comp.get("sig_p1")
    d = delta.get("fps_avg_pct") or 0
    d1 = delta.get("fps_p1_pct")
    kept = bool(sig["significant"] and d >= MIN_EFFECT_PCT)
    basis = "fps"
    if kept and d1 is not None and d1 <= STUTTER_GUARD_PCT:
        kept, basis = False, "stutter_guard"
        reason = f"FPS +{d}% ma fluidita' peggiorata (1% low {d1}%)"
    elif kept:
        reason = f"significativo (p={sig['p_value']}), +{d}% FPS"
    elif sig_p1 and sig_p1["significant"] and d1 is not None and d1 >= STUTTER_KEEP_PCT and d >= FPS_NEUTRAL_PCT:
        kept, basis = True, "fluidity"
        reason = f"fluidita': 1% low +{d1}% (p={sig_p1['p_value']}), FPS stabili ({d}%)"
    elif not sig["significant"]:
        reason = f"non significativo (p={sig['p_value']})"
    elif d < 0:
        reason = f"peggioramento ({d}%)"
    else:
        reason = f"delta trascurabile (+{d}% < {MIN_EFFECT_PCT}%)"
    if kept and delta.get("latency_ms") is not None and delta["latency_ms"] <= -1:
        reason += f", input lag {delta['latency_ms']}ms"
    ci = delta.get("fps_ci_pct")
    if ci:
        reason += f" [IC 95%: {ci[0]}% .. {ci[1]}%]"
    return kept, basis, reason


def _adapt_priors(sess, family, kept):
    """Se un tweak di una famiglia funziona, alza il prior dei fratelli in coda; se fallisce, abbassalo."""
    bump = 0.08 if kept else -0.05
    queued = set(sess.get("queue", []))
    for c in sess.get("candidates", []):
        if c["tweak_id"] in queued and c.get("family") == family:
            c["prior"] = round(max(0.01, c["prior"] + bump), 3)
    order = {c["tweak_id"]: c["prior"] for c in sess.get("candidates", [])}
    sess["queue"] = sorted(sess.get("queue", []), key=lambda tid: -order.get(tid, 0))


def _auto_stop(sess):
    results = sess.get("results", [])
    if len(results) < AUTO_STOP_WINDOW:
        return None
    recent = results[-AUTO_STOP_WINDOW:]
    if all(not r["significance"]["significant"] for r in recent):
        return f"auto-stop: ultimi {AUTO_STOP_WINDOW} test non significativi"
    total_gain = sum(r["delta"].get("fps_avg_pct") or 0 for r in results if r["decision"] == "kept")
    recent_gain = sum(r["delta"].get("fps_avg_pct") or 0 for r in recent if r["decision"] == "kept")
    if total_gain > 0 and recent_gain / total_gain < MARGINAL_GAIN_RATIO:
        return "auto-stop: rendimenti marginali (<3% del guadagno totale)"
    return None


def _result_delta(sess, tweak_id):
    for r in sess.get("results", []):
        if r["tweak_id"] == tweak_id and r["decision"] == "kept":
            return r["delta"].get("fps_avg_pct") or 0
    return 0


def _step_p(r):
    """Il p-value su cui poggia la decisione di quel test."""
    if r.get("decision_basis") == "fluidity" and r.get("significance_p1"):
        return r["significance_p1"].get("p_value")
    return (r.get("significance") or {}).get("p_value")


async def _apply_holm(sess):
    """Correzione per test multipli APPLICATA, non solo annotata nel report.

    Testare dieci tweak ad alpha 0.10 significa avere piu' del 60% di
    probabilita' di tenerne almeno uno che non fa nulla; e ogni falso positivo
    mantenuto diventa lo stato su cui si misura il successivo, quindi l'errore
    non resta isolato. Qui Holm decide davvero: chi non regge la correzione
    viene tolto dai mantenuti e messo in coda per il rollback.
    """
    results = sess.get("results", [])
    pvals = [(_step_p(r), r) for r in results]
    usable = [(p, r) for p, r in pvals if p is not None]
    if not usable:
        return []
    adj = holm_adjust([p for p, _ in usable])
    demoted = []
    for (p, r), a in zip(usable, adj):
        r["p_adj"] = a
        r["holm_ok"] = bool(a < HOLM_ALPHA)
        if r["decision"] == "kept" and not r["holm_ok"]:
            r["decision"] = "rolled_back"
            r["demoted"] = True
            r["reason"] = (f"{r.get('reason', '')} — annullato dalla correzione per test "
                           f"multipli (p corretto {a} >= {HOLM_ALPHA})").strip(" —")
            demoted.append(r["tweak_id"])
    if not demoted:
        return []
    sess["kept"] = [t for t in sess.get("kept", []) if t not in demoted]
    sess.setdefault("pending_rollback", []).extend(demoted)
    sess["demoted"] = list(demoted)
    # La stima del guadagno finale accumulata tweak dopo tweak non vale piu':
    # il report prendera' il valore misurato dalla run di validazione.
    sess["final_estimate_stale"] = True
    _log(sess, f"Correzione per test multipli (Holm): {len(demoted)} tweak mantenuti non "
               f"reggono la correzione e vengono annullati ({', '.join(demoted)})", "warn")
    for tid in demoted:
        game = ((sess.get("baseline") or {}).get("stats") or {}).get("game")
        try:
            await _fleet_demote(sess, tid, game)
        except Exception as exc:
            logger.debug("correzione fleet per %s non applicata: %s", tid, exc)
    return demoted


async def _fleet_demote(sess, tweak_id, game):
    """Toglie il 'kept' dall'aggregato per un tweak annullato da Holm.

    Solo se questa sessione lo aveva davvero aggiunto: se il contributo era
    stato saltato per quota, sottrarre lascerebbe l'aggregato con piu' successi
    annullati che registrati.
    """
    if tweak_id not in (sess.get("fleet_counted") or []):
        return
    dec = {"kept": -1}
    gk = _slug(game)
    if gk:
        dec[f"games.{gk}.kept"] = -1
    for q in ({"tweak_id": tweak_id, "hw_class": sess.get("hw_class", "other_other"),
               "scope": {"$ne": "family"}},
              {"tweak_id": tweak_id, "hw_class": sess.get("hw_family"), "scope": "family"}):
        if q.get("hw_class"):
            await db.lab_fleet_stats.update_one(q, {"$inc": dec})


async def _advance_after_testing(sess, stop_reason=None):
    """Fine test loop -> Holm -> (rollback dei demoti) -> synergy -> validazione."""
    if stop_reason:
        sess["auto_stop_reason"] = stop_reason
        _log(sess, stop_reason, "warn")
    await _apply_holm(sess)
    if sess.get("pending_rollback"):
        # Prima si torna allo stato che i dati sostengono davvero, poi si misura.
        sess["status"] = "rollback"
        _log(sess, f"Annullo {len(sess['pending_rollback'])} tweak non confermati "
                   f"prima di proseguire", "warn")
        return
    _plan_next_phase(sess)


def _plan_next_phase(sess):
    """Synergy pass (coppie greedy tra i kept no-reboot) -> validazione -> report."""
    kept = sess.get("kept", [])
    meta = {c["tweak_id"]: c for c in sess.get("candidates", [])}
    eligible = [t for t in kept if not meta.get(t, {}).get("requires_reboot")]
    pairs = []
    from itertools import combinations
    for a, b in combinations(eligible, 2):
        ma, mb = meta.get(a, {}), meta.get(b, {})
        if b in (ma.get("conflicts_with") or []) or a in (mb.get("conflicts_with") or []):
            continue
        if ma.get("family") and ma.get("family") == mb.get("family"):
            continue  # coppie complementari: famiglie diverse
        pairs.append({"a": a, "b": b, "sum_delta": round(_result_delta(sess, a) + _result_delta(sess, b), 2)})
    pairs.sort(key=lambda p: -p["sum_delta"])
    pairs = pairs[:SYNERGY_MAX_PAIRS]
    if pairs:
        sess["status"] = "synergy"
        sess["synergy"] = {"pairs": pairs, "idx": 0, "stage": "off", "toggled": False,
                           "off_runs": [], "on_runs": [], "results": []}
        _log(sess, f"SYNERGY PASS: {len(pairs)} coppie di tweak mantenuti da verificare ({SYNERGY_RUNS} run off + {SYNERGY_RUNS} run on per coppia)")
    elif kept:
        sess["status"] = "validation"
        _log(sess, f"VALIDAZIONE: sessione di gioco reale da {VALIDATION_SECONDS // 60} minuti con la configurazione finale")
    else:
        _complete(sess)


def _clamp(v, lo=0.0, hi=10.0):
    return round(max(lo, min(hi, v)), 1)


def _build_report(sess):
    base0 = sess.get("baseline0") or {}
    # Il guadagno finale non e' la somma dei delta misurati tweak per tweak: e'
    # una stima che si accumula, e dopo un rollback da correzione multipla non
    # descrive piu' lo stato reale del PC. Quando c'e' la run di validazione
    # (cinque minuti di gioco vero con la configurazione definitiva) quella e'
    # la misura, non la stima.
    val_run = (sess.get("validation") or {}).get("run") or {}
    final = sess.get("baseline", {}).get("stats") or base0
    final_source = "stima_progressiva"
    if val_run.get("fps_avg"):
        final = {**final, **{k: v for k, v in val_run.items()
                             if k in ("fps_avg", "fps_p1", "fps_p01", "latency_ms", "game")}}
        final_source = "validazione"
    gain = _delta_pct(final.get("fps_avg"), base0.get("fps_avg"))
    gain_p1 = _delta_pct(final.get("fps_p1"), base0.get("fps_p1"))
    steps = []
    names = {t["tweak_id"]: t["name"] for t in TWEAKS}
    for r in sess.get("results", []):
        steps.append({
            "tweak_id": r["tweak_id"],
            "tweak": names.get(r["tweak_id"], r["tweak_id"]),
            "before": r.get("before_fps"),
            "after": r.get("after_fps"),
            "delta_pct": r["delta"].get("fps_avg_pct"),
            "p1_delta_pct": r["delta"].get("fps_p1_pct"),
            "latency_delta_ms": r["delta"].get("latency_ms"),
            "ci_pct": r["delta"].get("fps_ci_pct"),
            "effect_d": r["delta"].get("effect_d"),
            "basis": r.get("decision_basis"),
            "design": r.get("design"),
            "n_pairs": r.get("n_pairs"),
            "decision": r["decision"],
            "demoted": bool(r.get("demoted")),
            "reason": r.get("reason"),
            "p_value": _step_p(r),
            "p_adj": r.get("p_adj"),
            "holm_ok": r.get("holm_ok"),
            "warnings": r.get("warnings") or [],
        })
    kept_steps = [s for s in steps if s["decision"] == "kept"]
    multiple_testing = {"method": "holm_bonferroni", "alpha": HOLM_ALPHA,
                        "applied": True,
                        "hypotheses": len([s for s in steps if s.get("p_value") is not None]),
                        "kept_total": len(kept_steps),
                        "demoted": sess.get("demoted") or [],
                        "kept_confirmed": sum(1 for s in kept_steps if s.get("holm_ok"))}
    meta = {c["tweak_id"]: c for c in sess.get("candidates", [])}
    reboots = sum(1 for r in sess.get("results", []) if meta.get(r["tweak_id"], {}).get("requires_reboot"))
    try:
        from datetime import datetime
        t0 = datetime.fromisoformat(sess["started_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(now_iso().replace("Z", "+00:00"))
        dur = round((t1 - t0).total_seconds() / 60, 1)
    except Exception:
        dur = None
    perf = _clamp(5 + (gain or 0) / 2)
    fluid = _clamp(5 + (gain_p1 or 0) / 2)
    stab = _clamp(10 - (base0.get("cv_pct") or 0))
    lat0, latf = base0.get("latency_ms"), final.get("latency_ms")
    lat_delta = round(latf - lat0, 2) if (lat0 is not None and latf is not None) else None
    return {
        "lab_session_id": sess["session_id"],
        "game": final.get("game") or base0.get("game"),
        "baseline": {"fps_avg": base0.get("fps_avg"), "fps_p1": base0.get("fps_p1"),
                     "fps_p01": base0.get("fps_p01"), "frames": base0.get("frames")},
        "final": {"fps_avg": final.get("fps_avg"), "fps_p1": final.get("fps_p1"),
                  "fps_p01": final.get("fps_p01"), "source": final_source},
        "total_gain_pct": gain,
        "total_p1_gain_pct": gain_p1,
        "total_latency_delta_ms": lat_delta,
        "metrics_version": base0.get("metrics_version") or METRICS_VERSION,
        "design": "paired_abba" if sess.get("paired", True) else "blocked",
        "quality": sess.get("quality") or {},
        "multiple_testing": multiple_testing,
        "drift_events": sess.get("drift_events") or [],
        "steps": steps,
        "kept": sess.get("kept", []),
        "synergies_found": (sess.get("synergy") or {}).get("results", []),
        "validation": sess.get("validation"),
        "bios_suggestions": sess.get("bios_suggestions") or [],
        "hw_class": sess.get("hw_class"),
        "reboots_required": reboots,
        "manual_steps_required": [],
        "total_duration_min": dur,
        "performance_index": {
            "prestazioni": perf, "fluidita": fluid, "stabilita": stab,
            "voto_finale": _clamp((perf + fluid + stab) / 3),
        },
        "tweaks_tested": len(steps),
        "auto_stop_reason": sess.get("auto_stop_reason"),
    }


def _complete(sess, reason=None):
    if reason:
        sess["auto_stop_reason"] = reason
        _log(sess, reason, "warn")
    sess["status"] = "completed"
    sess["finished_at"] = now_iso()
    sess["report"] = _build_report(sess)
    sess["_bump_lab_milestone"] = True
    _log(sess, "Laboratorio completato: report generato", "ok")


async def _save(sess):
    sess["updated_at"] = now_iso()
    if sess.pop("_bump_lab_milestone", None):
        try:
            from milestones import bump_counter
            await bump_counter(db, sess.get("user_id"), "lab_experiments", 1)
        except Exception as exc:
            logger.debug("contatore lab_experiments non aggiornato: %s", exc)
    await db.lab_sessions.replace_one({"session_id": sess["session_id"]}, sess, upsert=True)


def _strip_hist(node):
    """Toglie gli istogrammi dalla copia destinata al client.

    Servono al backend per i percentili, ma sono 306 interi per run: rispedirli
    al browser a ogni poll della pagina Laboratorio e' un centinaio di KB di
    banda che nessuno legge.
    """
    if isinstance(node, dict):
        return {k: _strip_hist(v) for k, v in node.items() if k != "hist"}
    if isinstance(node, list):
        return [_strip_hist(v) for v in node]
    return node


def _public(sess):
    if not sess:
        return None
    return _strip_hist({k: v for k, v in sess.items() if k != "_id"})


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["lab"])

    async def _agent_uid(x_agent_token: str) -> str:
        rec = await db.agent_tokens.find_one({"token": x_agent_token})
        if not rec:
            raise HTTPException(status_code=401, detail="token agent non valido")
        return rec["user_id"]

    async def _active(uid: str):
        return await db.lab_sessions.find_one(
            {"user_id": uid, "status": {"$in": list(ACTIVE_STATUSES)}}, sort=[("started_at", -1)])

    # ---------- user endpoints ----------
    @r.post("/lab/start")
    async def lab_start(payload: LabStartInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        if await _active(uid):
            raise HTTPException(status_code=409, detail="Hai gia' una sessione Lab attiva. Interrompila prima di avviarne una nuova.")
        specs = await db.pc_specs.find_one({"user_id": uid}) or {}
        candidates, skipped = select_candidates(specs.get("data") or {}, payload.risk_level, payload.include_reboot)
        if not candidates:
            raise HTTPException(status_code=400, detail="Nessun tweak candidato per questo livello di rischio/hardware.")
        hw = _hw_class(specs.get("data") or {})
        hw_family = hardware.fleet_key(specs.get("data") or {})
        fleet_used = await _fleet_blend(candidates, hw, hw_family)
        sd = specs.get("data") or {}
        sess = {
            "session_id": str(uuid.uuid4()),
            "user_id": uid,
            "kind": "full",
            "risk_level": payload.risk_level,
            "run_seconds": payload.run_seconds,
            "include_reboot": payload.include_reboot,
            "paired": bool(payload.paired),
            "metrics_version": METRICS_VERSION,
            "quality": {},
            "hw_class": hw,
            "hw_family": hw_family,
            "specs_at": {"ram_speed_mhz": sd.get("ram_speed_mhz"), "ram_modules": sd.get("ram_modules"),
                         "gpu_driver": sd.get("gpu_driver_version") or sd.get("gpu_driver")},
            "bios_suggestions": bios_suggestions(specs.get("data") or {}),
            "registry_version": REGISTRY_VERSION,
            "status": "waiting_agent",
            "candidates": candidates,
            "queue": [c["tweak_id"] for c in candidates],
            "skipped": skipped,
            "current": None,
            "baseline": {"runs": [], "stats": None},
            "baseline0": None,
            "results": [],
            "kept": [],
            "snapshot": None,
            "logs": [],
            "report": None,
            "started_at": now_iso(),
            "finished_at": None,
        }
        schema = (f"schema appaiato ON/OFF, {PAIR_RUNS} coppie per tweak"
                  if payload.paired else "schema a blocchi (piu' veloce, meno sensibile)")
        _log(sess, f"Sessione creata: {len(candidates)} tweak candidati (rischio {payload.risk_level}, "
                   f"finestre {payload.run_seconds}s, {schema})")
        if fleet_used:
            _log(sess, f"Prior arricchiti con i dati fleet: {fleet_used} tweak hanno statistiche da PC simili ({hw.replace('_', ' GPU + ')} CPU)")
        _log(sess, "In attesa dell'agent: esegui il comando Lab in PowerShell come Amministratore")
        await _save(sess)
        return {"session": _public(sess)}

    @r.get("/lab/session")
    async def lab_session(user: dict = Depends(get_current_user)):
        sess = await db.lab_sessions.find_one({"user_id": str(user["_id"])}, sort=[("started_at", -1)])
        return {"session": _public(sess)}

    @r.post("/lab/abort")
    async def lab_abort(user: dict = Depends(get_current_user)):
        sess = await _active(str(user["_id"]))
        if not sess:
            raise HTTPException(status_code=404, detail="Nessuna sessione Lab attiva")
        if sess["status"] == "waiting_agent":
            sess["status"] = "aborted"
            sess["finished_at"] = now_iso()
            _log(sess, "Sessione annullata (agent mai collegato)", "warn")
        else:
            sess["status"] = "aborting"
            _log(sess, "Interruzione richiesta: l'agent annullera' tutti i tweak applicati", "warn")
        await _save(sess)
        return {"session": _public(sess)}

    @r.get("/lab/registry")
    async def lab_registry(risk_level: str = "medium", include_reboot: bool = True, user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}) or {}
        candidates, skipped = select_candidates(specs.get("data") or {}, risk_level, include_reboot)
        hw = _hw_class(specs.get("data") or {})
        hw_family = hardware.fleet_key(specs.get("data") or {})
        await _fleet_blend(candidates, hw, hw_family)
        return {"registry_version": REGISTRY_VERSION, "candidates": candidates, "skipped": skipped,
                "hw_class": hw, "hw_family": hw_family, "bios_suggestions": bios_suggestions(specs.get("data") or {})}

    @r.post("/lab/check")
    async def lab_check(payload: LabCheckInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        if await _active(uid):
            raise HTTPException(status_code=409, detail="Hai gia' una sessione Lab attiva.")
        last = await db.lab_sessions.find_one(
            {"user_id": uid, "status": "completed", "kind": {"$ne": "check"}, "report": {"$ne": None}},
            sort=[("started_at", -1)])
        if not last or not ((last.get("report") or {}).get("final") or {}).get("fps_avg"):
            raise HTTPException(status_code=400, detail="Serve prima un Lab completo come riferimento.")
        rep = last["report"]
        ref = {"fps_avg": rep["final"]["fps_avg"], "fps_p1": rep["final"].get("fps_p1"),
               "game": rep.get("game"), "session_id": last["session_id"], "at": last.get("finished_at")}
        sess = {
            "session_id": str(uuid.uuid4()), "user_id": uid, "kind": "check",
            "check_reason": payload.reason, "check_ref": ref,
            "run_seconds": last.get("run_seconds", 90), "status": "waiting_agent",
            "candidates": [], "queue": [], "baseline": {"runs": [], "stats": None},
            "results": [], "kept": [], "logs": [], "report": None,
            "started_at": now_iso(), "finished_at": None,
        }
        _log(sess, f"Mini-lab di verifica ({payload.reason}): {CHECK_RUNS} run vs riferimento {ref['fps_avg']} FPS ({ref.get('game') or 'n/d'})")
        if int(rep.get("metrics_version") or 1) < METRICS_VERSION:
            # Il riferimento e' stato misurato quando `fps_p1` era il p99 puntuale.
            # Gli FPS medi restano confrontabili, l'1% low no: cambiando la
            # definizione la differenza non direbbe nulla sul PC.
            sess["p1_not_comparable"] = True
            _log(sess, "Il riferimento usa il vecchio calcolo dell'1% low: il confronto "
                       "sulla fluidita' non e' valido, guardo solo gli FPS medi", "warn")
        _log(sess, "In attesa dell'agent: esegui il comando Lab in PowerShell come Amministratore")
        await _save(sess)
        return {"session": _public(sess)}

    @r.get("/lab/fleet-validation")
    async def lab_fleet_validation(user: dict = Depends(get_current_user)):
        """Tweak validati dalla flotta: aggregato anonimo globale + fascia hardware dell'utente."""
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"data": 1})
        hw = _hw_class((specs or {}).get("data") or {})
        hw_family = hardware.fleet_key((specs or {}).get("data") or {})
        names = {t["tweak_id"]: {"name": t.get("name"), "family": t.get("family")} for t in TWEAKS}

        def _spread(tested, dsum, dsq):
            """Deviazione standard dei delta misurati. Con la sola somma non si
            poteva dire quanto fosse incerta la media: +3% su misure tra -1% e
            +7% non e' lo stesso dato di +3% su misure tutte tra +2% e +4%."""
            if tested < 2 or dsq is None:
                return None
            var = (dsq - dsum * dsum / tested) / (tested - 1)
            return round(math.sqrt(var), 1) if var > 0 else 0.0

        def _hw_block(d, scope):
            tested = int(d.get("tested") or 0)
            kept = int(d.get("kept") or 0)
            lo, hi = wilson_ci(kept, tested)
            dsum = float(d.get("delta_sum") or 0.0)
            return {"tested": tested, "kept": kept,
                    "success_pct": round(100 * kept / tested),
                    "success_ci_pct": [round(100 * lo), round(100 * hi)],
                    "avg_delta_pct": round(dsum / tested, 1),
                    "delta_sd_pct": _spread(tested, dsum, d.get("delta_sq_sum")),
                    "scope": scope}

        agg = {}
        # Il totale globale somma SOLO i documenti vendor: quelli di famiglia
        # contano gli stessi test una seconda volta.
        async for d in db.lab_fleet_stats.find({"scope": {"$ne": "family"}}):
            a = agg.setdefault(d["tweak_id"], {"tested": 0, "kept": 0, "delta_sum": 0.0,
                                               "delta_sq_sum": 0.0, "hw": None})
            a["tested"] += int(d.get("tested") or 0)
            a["kept"] += int(d.get("kept") or 0)
            a["delta_sum"] += float(d.get("delta_sum") or 0.0)
            a["delta_sq_sum"] += float(d.get("delta_sq_sum") or 0.0)
            if d.get("hw_class") == hw and int(d.get("tested") or 0) > 0:
                a["hw"] = _hw_block(d, "vendor")
        # La fascia hardware dell'utente usa la granularita' fine quando c'e'.
        if hw_family:
            async for d in db.lab_fleet_stats.find({"hw_class": hw_family, "scope": "family"}):
                a = agg.get(d["tweak_id"])
                if a and int(d.get("tested") or 0) >= FLEET_MIN_SAMPLES:
                    a["hw"] = _hw_block(d, "family")
        items = []
        for tid, a in agg.items():
            if a["tested"] <= 0:
                continue
            meta = names.get(tid) or {}
            lo, hi = wilson_ci(a["kept"], a["tested"])
            items.append({
                "tweak_id": tid, "name": meta.get("name") or tid,
                "tested": a["tested"], "kept": a["kept"],
                "success_pct": round(100 * a["kept"] / a["tested"]),
                "success_ci_pct": [round(100 * lo), round(100 * hi)],
                "avg_delta_pct": round(a["delta_sum"] / a["tested"], 1),
                "delta_sd_pct": _spread(a["tested"], a["delta_sum"], a["delta_sq_sum"]),
                "thin": a["tested"] < FLEET_MIN_SAMPLES * 3,
                "hw": a["hw"],
            })
        items.sort(key=lambda x: (-(x["hw"] is not None), -x["success_pct"], -x["tested"]))
        return {"hw_class": hw, "hw_family": hw_family, "items": items,
                "total_tests": sum(i["tested"] for i in items)}

    @r.get("/lab/history")
    async def lab_history(user: dict = Depends(get_current_user)):
        out = []
        cur = db.lab_sessions.find({"user_id": str(user["_id"]), "status": "completed"},
                                   sort=[("started_at", -1)]).limit(15)
        async for s in cur:
            rep = s.get("report") or {}
            out.append({
                "session_id": s["session_id"], "kind": s.get("kind", "full"),
                "started_at": s.get("started_at"), "game": rep.get("game"),
                "total_gain_pct": rep.get("total_gain_pct"),
                "kept": len(rep.get("kept") or []), "tweaks_tested": rep.get("tweaks_tested"),
                "baseline_fps": (rep.get("baseline") or {}).get("fps_avg"),
                "final_fps": (rep.get("final") or {}).get("fps_avg"),
                "check_reason": s.get("check_reason"), "regression": rep.get("regression"),
            })
        return {"sessions": out}

    @r.get("/lab/insights")
    async def lab_insights(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        last = await db.lab_sessions.find_one(
            {"user_id": uid, "status": "completed", "kind": {"$ne": "check"}, "report": {"$ne": None}},
            sort=[("started_at", -1)])
        if not last:
            return {"items": [], "has_ref": False}

        def _num(v):
            try:
                return float(str(v).strip())
            except Exception:
                return None

        specs = await db.pc_specs.find_one({"user_id": uid}) or {}
        data = specs.get("data") or {}
        at = last.get("specs_at") or {}
        bios_ids = {b["id"] for b in (last.get("bios_suggestions") or [])}
        items = []
        cur_speed, at_speed = _num(data.get("ram_speed_mhz")), _num(at.get("ram_speed_mhz"))
        if "xmp" in bios_ids and cur_speed and at_speed and cur_speed > at_speed * 1.1:
            items.append({"id": "bios_xmp", "kind": "confirm", "detail": f"RAM: {int(at_speed)} -> {int(cur_speed)} MHz"})
        if "dual_channel" in bios_ids and (_num(data.get("ram_modules")) or 0) >= 2:
            items.append({"id": "bios_dual", "kind": "confirm", "detail": "dual channel rilevato"})
        if "rebar" in bios_ids:
            if str(data.get("rebar_status") or "").lower() == "on":
                items.append({"id": "bios_rebar", "kind": "confirm", "detail": "ReBAR attivo rilevato"})
            else:
                items.append({"id": "bios_rebar", "kind": "manual", "detail": None})
        cur_drv = data.get("gpu_driver_version") or data.get("gpu_driver")
        at_drv = at.get("gpu_driver")
        if cur_drv and at_drv and str(cur_drv) != str(at_drv):
            items.append({"id": "driver_update", "kind": "check", "detail": f"{at_drv} -> {cur_drv}"})
        rep = last.get("report") or {}
        return {"items": items, "has_ref": bool((rep.get("final") or {}).get("fps_avg")),
                "ref": {"fps_avg": (rep.get("final") or {}).get("fps_avg"), "game": rep.get("game"),
                        "at": last.get("finished_at")}}

    # ---------- agent endpoints ----------
    @r.get("/agent/lab/next")
    async def lab_next(x_agent_token: str = Header(default="")):
        uid = await _agent_uid(x_agent_token)
        sess = await _active(uid)
        if not sess:
            # sessione appena completata: consegna il report all'agent una sola volta
            last = await db.lab_sessions.find_one({"user_id": uid, "status": "completed"}, sort=[("started_at", -1)])
            if last and not last.get("agent_ack"):
                await db.lab_sessions.update_one({"session_id": last["session_id"]}, {"$set": {"agent_ack": True}})
                return {"action": "complete", "report": last.get("report")}
            return {"action": "wait"}
        st = sess["status"]
        rs = sess["run_seconds"]
        if st == "waiting_agent":
            if sess.get("kind") == "check":
                sess["status"] = "baseline"
                _log(sess, f"Agent collegato: mini-lab di verifica, {CHECK_RUNS} run")
                await _save(sess)
                st = "baseline"
            else:
                sess["status"] = "snapshot"
                _log(sess, "Agent collegato: avvio fase SNAPSHOT")
                await _save(sess)
                st = "snapshot"
        if st == "snapshot":
            return {"action": "snapshot", "session_id": sess["session_id"],
                    "candidate_ids": [c["tweak_id"] for c in sess["candidates"]]}
        if st == "baseline":
            done = len(sess["baseline"]["runs"])
            if sess.get("kind") == "check":
                target = CHECK_RUNS
            else:
                target = BASELINE_RUNS if done < BASELINE_RUNS else BASELINE_RUNS + 1
            return {"action": "run_baseline", "run_seconds": rs, "runs_done": done, "runs_target": target}
        if st == "aborting":
            ids = list(sess.get("kept", []))
            cur = sess.get("current")
            if cur and cur.get("applied") and cur["tweak_id"] not in ids:
                ids.append(cur["tweak_id"])
            return {"action": "abort", "rollback_ids": ids}
        if st == "awaiting_reboot":
            cur = sess.get("current") or {}
            return {"action": "reboot_required", "tweak_id": cur.get("tweak_id"),
                    "applied_at": cur.get("applied_at"), "session_id": sess["session_id"]}
        if st == "rollback":
            return {"action": "rollback_tweaks",
                    "tweak_ids": list(sess.get("pending_rollback") or []),
                    "reason": "correzione per test multipli (Holm)"}
        if st == "synergy":
            syn = sess.get("synergy") or {}
            pairs = syn.get("pairs", [])
            idx = syn.get("idx", 0)
            if idx >= len(pairs):
                sess["status"] = "validation"
                _log(sess, f"VALIDAZIONE: sessione di gioco reale da {VALIDATION_SECONDS // 60} minuti")
                await _save(sess)
                return {"action": "run_validation", "run_seconds": VALIDATION_SECONDS}
            pair = pairs[idx]
            stage = syn.get("stage", "off")
            if not syn.get("toggled"):
                return {"action": "synergy_toggle", "stage": stage, "pair": [pair["a"], pair["b"]],
                        "pair_num": idx + 1, "pairs_total": len(pairs)}
            runs_done = len(syn.get("off_runs" if stage == "off" else "on_runs", []))
            return {"action": "run_synergy", "stage": stage, "pair": [pair["a"], pair["b"]],
                    "runs_done": runs_done, "runs_target": SYNERGY_RUNS, "run_seconds": rs,
                    "pair_num": idx + 1, "pairs_total": len(pairs)}
        if st == "validation":
            return {"action": "run_validation", "run_seconds": VALIDATION_SECONDS}
        if st == "testing":
            cur = sess.get("current")
            rc = sess.get("recheck")
            if rc:
                return {"action": "run_recheck", "run_seconds": rs,
                        "runs_done": len(rc["runs"]), "runs_target": rc["target"]}
            total = len(sess["candidates"])
            step = len(sess.get("results", [])) + len(sess.get("skipped_runtime", [])) + 1
            if not cur:
                # Chiusura dello schema appaiato: l'ultima misura della sequenza
                # ABBA e' con il tweak spento, quindi un tweak promosso va
                # riacceso prima di passare al successivo.
                ft = sess.get("final_toggle")
                if ft:
                    return {"action": "pair_toggle", "tweak_id": ft["tweak_id"],
                            "stage": ft["stage"], "final": True}
                queue = sess.get("queue", [])
                if queue and len(sess.get("results", [])) >= sess.get("recheck_after", 0) + 3:
                    sess["recheck"] = {"runs": [], "target": 1}
                    sess["recheck_after"] = len(sess.get("results", []))
                    _log(sess, "Controllo drift baseline (schema A/B/A): 1 run di verifica")
                    await _save(sess)
                    return {"action": "run_recheck", "run_seconds": rs, "runs_done": 0, "runs_target": 1}
                if not queue:
                    await _advance_after_testing(sess)
                    await _save(sess)
                    if sess["status"] == "completed":
                        sess["agent_ack"] = True
                        await _save(sess)
                        return {"action": "complete", "report": sess["report"]}
                    return {"action": "transition", "status": sess["status"]}
                tid = queue.pop(0)
                sess["queue"] = queue
                sess["current"] = {"tweak_id": tid, "applied": False, "runs": [],
                                   "on_runs": [], "off_runs": [], "stage_state": None}
                await _save(sess)
                cur = sess["current"]
            tweak = next((c for c in sess["candidates"] if c["tweak_id"] == cur["tweak_id"]), {"tweak_id": cur["tweak_id"]})
            if not cur.get("applied"):
                return {"action": "apply_tweak", "tweak_id": cur["tweak_id"], "tweak": tweak,
                        "requires_reboot": bool(tweak.get("requires_reboot")),
                        "paired": _is_paired(sess, tweak),
                        "step": step, "total": total}
            if cur.get("warmup_needed"):
                return {"action": "run_warmup", "tweak_id": cur["tweak_id"], "run_seconds": WARMUP_SECONDS}
            if _is_paired(sess, tweak):
                stages = _pair_stages()
                done = len(cur.get("on_runs", [])) + len(cur.get("off_runs", []))
                if done < len(stages):
                    stage = stages[done]
                    if cur.get("stage_state") != stage:
                        return {"action": "pair_toggle", "tweak_id": cur["tweak_id"], "stage": stage,
                                "pair_num": done // 2 + 1, "pairs_total": PAIR_RUNS,
                                "step": step, "total": total}
                    return {"action": "run_pair", "tweak_id": cur["tweak_id"], "stage": stage,
                            "run_seconds": rs, "runs_done": done, "runs_target": len(stages),
                            "pair_num": done // 2 + 1, "pairs_total": PAIR_RUNS,
                            "step": step, "total": total}
            return {"action": "run_test", "tweak_id": cur["tweak_id"], "run_seconds": rs,
                    "runs_done": len(cur["runs"]), "runs_target": TEST_RUNS, "step": step, "total": total}
        return {"action": "wait"}

    @r.post("/agent/lab/event")
    async def lab_event(payload: LabEventInput, x_agent_token: str = Header(default="")):
        uid = await _agent_uid(x_agent_token)
        sess = await _active(uid)
        if not sess:
            return {"ok": False}
        data = payload.data or {}
        t = payload.type
        if t == "snapshot_done":
            sess["snapshot"] = {"restore_point": bool(data.get("restore_point")),
                                "states": data.get("states") or {}, "created_at": now_iso()}
            sess["status"] = "baseline"
            rp = "creato" if data.get("restore_point") else "NON creato (limite Windows 24h) - backup mirato comunque attivo"
            _log(sess, f"Snapshot completato. Punto di ripristino: {rp}", "ok")
            _log(sess, f"Fase BASELINE: {BASELINE_RUNS} run da {sess['run_seconds']}s. Avvia il gioco!")
        elif t == "tweak_applied":
            cur = sess.get("current")
            if cur and cur["tweak_id"] == data.get("tweak_id"):
                cur["applied"] = True
                cur["applied_at"] = now_iso()
                cur["stage_state"] = "on"
                if data.get("requires_reboot"):
                    sess["status"] = "awaiting_reboot"
                    _log(sess, f"Tweak applicato: {data.get('tweak_id')} — RIAVVIO RICHIESTO. Il Lab riprende automaticamente dopo il riavvio.", "warn")
                else:
                    _log(sess, f"Tweak applicato: {data.get('tweak_id')} (backup creato)")
            else:
                _log(sess, f"Tweak applicato: {data.get('tweak_id')} (backup creato)")
        elif t == "reboot_done":
            cur = sess.get("current")
            if sess["status"] == "awaiting_reboot" and cur:
                sess["status"] = "testing"
                cur["warmup_needed"] = True
                _log(sess, f"Riavvio completato: riprendo il test di {cur['tweak_id']} (1 run di warm-up + {TEST_RUNS} run misurati)", "ok")
        elif t == "pair_toggled":
            stage = data.get("stage")
            if data.get("final"):
                ft = sess.get("final_toggle") or {}
                sess["final_toggle"] = None
                _log(sess, f"{ft.get('tweak_id', 'tweak')} riattivato dopo la sequenza appaiata")
            else:
                cur = sess.get("current")
                if cur and cur["tweak_id"] == data.get("tweak_id") and stage in ("on", "off"):
                    cur["stage_state"] = stage
                    _log(sess, f"{cur['tweak_id']}: passo alla misura {stage.upper()}")
        elif t == "tweaks_rolled_back":
            done = [str(x) for x in (data.get("tweak_ids") or [])]
            sess["pending_rollback"] = [tid for tid in (sess.get("pending_rollback") or []) if tid not in done]
            _log(sess, f"Tweak non confermati annullati: {', '.join(done) or 'nessuno'}", "ok")
            if not sess.get("pending_rollback") and sess["status"] == "rollback":
                _plan_next_phase(sess)
        elif t == "synergy_toggled":
            syn = sess.get("synergy")
            if syn:
                syn["toggled"] = True
                stage = data.get("stage", syn.get("stage"))
                _log(sess, f"Synergy: coppia {'disattivata' if stage == 'off' else 'riattivata'} per la misura {stage.upper()}")
        elif t == "tweak_skip":
            sess.setdefault("skipped_runtime", []).append(
                {"tweak_id": data.get("tweak_id"), "reason": data.get("reason", "n/d")})
            sess["current"] = None
            _log(sess, f"Tweak saltato: {data.get('tweak_id')} ({data.get('reason', 'n/d')})", "warn")
        elif t == "rolled_back":
            _log(sess, f"Rollback eseguito: {data.get('tweak_id')}", "warn")
        elif t == "aborted":
            sess["status"] = "aborted"
            sess["finished_at"] = now_iso()
            _log(sess, "Sessione interrotta: tutti i tweak del Lab sono stati annullati", "warn")
        elif t == "waiting_game":
            _log(sess, "Agent in attesa del gioco: avvia il gioco e resta in partita")
        elif t == "game_detected":
            _log(sess, f"Gioco rilevato: {data.get('game', 'n/d')}", "ok")
        elif t == "log":
            _log(sess, str(data.get("message", ""))[:300])
        await _save(sess)
        return {"ok": True, "status": sess["status"]}

    @r.post("/agent/lab/run")
    async def lab_run(payload: LabRunInput, x_agent_token: str = Header(default="")):
        uid = await _agent_uid(x_agent_token)
        sess = await _active(uid)
        if not sess:
            raise HTTPException(status_code=404, detail="nessuna sessione attiva")
        run = _ingest_run(payload.run)

        # Una misura presa in condizioni diverse dalle altre non e' un dato
        # rumoroso: e' un dato di un altro esperimento. Meglio ripeterla.
        if payload.phase not in ("warmup",):
            reject, warns = _run_guard(sess, run, payload.phase)
            # Il tetto e' per causa, non per sessione: un problema che non si
            # risolve (il PC resta a batteria) non deve far ripetere all'infinito,
            # ma non deve nemmeno spegnere la guardia per tutto il resto.
            counts = sess.setdefault("rejects", {})
            nrej = int(counts.get(reject["code"]) or 0) if reject else 0
            if reject and nrej < MAX_RUN_REJECTS:
                counts[reject["code"]] = nrej + 1
                _log(sess, f"Run scartato e da ripetere: {reject['msg']}", "warn")
                await _save(sess)
                return {"ok": True, "rejected": True, "reason": reject["msg"],
                        "reason_code": reject["code"]}
            if reject:
                run["suspect"] = reject["msg"]
                warns = list(warns) + [reject["msg"]]
                _log(sess, f"Run accettato nonostante: {reject['msg']} "
                           f"(gia' ripetuto {nrej} volte per la stessa causa)", "warn")
            if warns:
                run["warnings"] = warns
                for w in warns:
                    _log(sess, f"Attenzione sul run: {w}", "warn")

        if payload.phase == "warmup":
            cur = sess.get("current")
            if cur:
                cur["warmup_needed"] = False
            _log(sess, f"Warm-up post-riavvio completato ({run.get('fps_avg')} FPS, scartato dalle statistiche)")
            await _save(sess)
            return {"ok": True, "warmup_done": True}

        if payload.phase in ("synergy_off", "synergy_on"):
            syn = sess.get("synergy")
            if sess["status"] != "synergy" or not syn:
                return {"ok": False, "reason": "nessun synergy pass attivo"}
            stage = "off" if payload.phase == "synergy_off" else "on"
            key = f"{stage}_runs"
            syn[key].append(run)
            pair = syn["pairs"][syn["idx"]]
            _log(sess, f"Synergy {pair['a']}+{pair['b']} [{stage.upper()}] run {len(syn[key])}: {run.get('fps_avg')} FPS avg")
            if len(syn[key]) < SYNERGY_RUNS:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(syn[key])}
            if stage == "off":
                syn["stage"] = "on"
                syn["toggled"] = False
                await _save(sess)
                return {"ok": True, "stage_done": "off"}
            # coppia completata: calcola la sinergia
            off_fps = _fps_list(syn["off_runs"])
            on_fps = _fps_list(syn["on_runs"])
            combined = _delta_pct(mean(on_fps), mean(off_fps)) if off_fps and on_fps else None
            is_syn = bool(combined is not None and pair["sum_delta"] > 0 and combined > pair["sum_delta"] * SYNERGY_FACTOR)
            res = {"pair": [pair["a"], pair["b"]], "combined_delta_pct": combined,
                   "individual_sum_pct": pair["sum_delta"], "is_synergy": is_syn,
                   "off_fps_avg": round(mean(off_fps), 2) if off_fps else None,
                   "on_fps_avg": round(mean(on_fps), 2) if on_fps else None}
            syn["results"].append(res)
            if is_syn:
                _log(sess, f"SINERGIA trovata: {pair['a']}+{pair['b']} insieme valgono {combined}% (somma singoli {pair['sum_delta']}%)", "ok")
            else:
                _log(sess, f"Nessuna sinergia extra: {pair['a']}+{pair['b']} = {combined}% (somma singoli {pair['sum_delta']}%)")
            syn["idx"] += 1
            syn["stage"] = "off"
            syn["toggled"] = False
            syn["off_runs"], syn["on_runs"] = [], []
            if syn["idx"] >= len(syn["pairs"]):
                sess["status"] = "validation"
                _log(sess, f"VALIDAZIONE: sessione di gioco reale da {VALIDATION_SECONDS // 60} minuti con la configurazione finale")
            await _save(sess)
            return {"ok": True, "pair_done": True, "synergy": res, "next_status": sess["status"]}

        if payload.phase == "validation":
            if sess["status"] != "validation":
                return {"ok": False, "reason": f"stato {sess['status']}"}
            base0 = sess.get("baseline0") or {}
            predicted = _delta_pct(sess["baseline"]["stats"].get("fps_avg") if sess["baseline"].get("stats") else None,
                                   base0.get("fps_avg")) or 0
            real = _delta_pct(run.get("fps_avg"), base0.get("fps_avg"))
            discrepancy = bool(predicted >= 2.0 and real is not None and real < predicted * VALIDATION_MIN_RATIO)
            sess["validation"] = {"run": run, "real_gain_pct": real, "predicted_gain_pct": round(predicted, 2),
                                  "duration_s": run.get("duration_s"), "discrepancy": discrepancy}
            if discrepancy:
                _log(sess, f"DISCREPANZA: guadagno reale {real}% < 50% del previsto ({round(predicted, 2)}%) — segnalato nel report", "warn")
            else:
                _log(sess, f"Validazione in gioco reale: {run.get('fps_avg')} FPS avg ({'+' if (real or 0) >= 0 else ''}{real}% vs baseline)", "ok")
            _complete(sess)
            sess["agent_ack"] = True
            await _save(sess)
            return {"ok": True, "validation": sess["validation"], "completed": True, "report": sess["report"]}

        if payload.phase == "recheck":
            rc = sess.get("recheck")
            if sess["status"] != "testing" or not rc:
                return {"ok": False, "reason": "nessun recheck attivo"}
            rc["runs"].append(run)
            base = sess["baseline"]["stats"] or {}
            drift = _delta_pct(run.get("fps_avg"), base.get("fps_avg")) or 0
            if rc["target"] == 1 and len(rc["runs"]) == 1:
                if abs(drift) <= 3.0:
                    sess["recheck"] = None
                    _log(sess, f"Baseline stabile: drift {drift}% (entro +/-3%)", "ok")
                    await _save(sess)
                    return {"ok": True, "drift_pct": drift, "stable": True}
                rc["target"] = 3
                sess.setdefault("drift_events", []).append({"at": now_iso(), "drift_pct": drift})
                _log(sess, f"DRIFT rilevato: {drift}% — ri-misuro la baseline (3 run)", "warn")
                await _save(sess)
                return {"ok": True, "drift_pct": drift, "stable": False, "need_more": True}
            if len(rc["runs"]) < rc["target"]:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(rc["runs"])}
            stats = _run_stats(rc["runs"])
            sess["baseline"]["runs"] = rc["runs"]
            sess["baseline"]["stats"] = stats
            sess["recheck"] = None
            _log(sess, f"RE-BASELINE: nuova baseline {stats['fps_avg']} FPS (drift compensato)", "warn")
            await _save(sess)
            return {"ok": True, "rebaselined": True, "stats": stats}

        if payload.phase == "baseline":
            if sess["status"] != "baseline":
                return {"ok": False, "reason": f"stato {sess['status']}"}
            if sess.get("kind") == "check":
                sess["baseline"]["runs"].append(run)
                runs = sess["baseline"]["runs"]
                _log(sess, f"Verifica run {len(runs)}: {run.get('fps_avg')} FPS avg")
                if len(runs) < CHECK_RUNS:
                    await _save(sess)
                    return {"ok": True, "need_more": True, "runs_done": len(runs)}
                stats = _run_stats(runs)
                ref = sess.get("check_ref") or {}
                delta = _delta_pct(stats.get("fps_avg"), ref.get("fps_avg"))
                d1 = None if sess.get("p1_not_comparable") else _delta_pct(stats.get("fps_p1"), ref.get("fps_p1"))
                regression = bool(delta is not None and delta <= REGRESSION_PCT)
                if stats.get("game") and ref.get("game") and stats["game"] != ref["game"]:
                    _log(sess, f"ATTENZIONE: gioco diverso dal riferimento ({stats['game']} vs {ref['game']}), confronto indicativo", "warn")
                sess["report"] = {
                    "kind": "check", "check_reason": sess.get("check_reason"),
                    "game": stats.get("game") or ref.get("game"),
                    "baseline": {"fps_avg": ref.get("fps_avg"), "fps_p1": ref.get("fps_p1")},
                    "final": {"fps_avg": stats.get("fps_avg"), "fps_p1": stats.get("fps_p1")},
                    "total_gain_pct": delta, "total_p1_gain_pct": d1,
                    "regression": regression, "ref_at": ref.get("at"),
                    "kept": [], "tweaks_tested": 0, "steps": [],
                }
                sess["baseline"]["stats"] = stats
                sess["status"] = "completed"
                sess["finished_at"] = now_iso()
                if regression:
                    _log(sess, f"REGRESSIONE: {delta}% vs riferimento ({ref.get('fps_avg')} FPS) — consigliato un nuovo Lab completo", "warn")
                else:
                    _log(sess, f"Verifica completata: {stats.get('fps_avg')} FPS ({'+' if (delta or 0) >= 0 else ''}{delta}% vs riferimento)", "ok")
                await _save(sess)
                return {"ok": True, "baseline_ok": True, "stats": stats, "completed": True, "check": sess["report"]}
            sess["baseline"]["runs"].append(run)
            runs = sess["baseline"]["runs"]
            _log(sess, f"Baseline run {len(runs)}: {run.get('fps_avg')} FPS avg | 1% low {run.get('fps_p1')}")
            if len(runs) < BASELINE_RUNS:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(runs)}
            fps = _fps_list(runs)
            c = cv(fps)
            if c > CV_MAX and len(runs) == BASELINE_RUNS:
                _log(sess, f"CV baseline {c*100:.1f}% > 5%: richiedo un 4o run e scarto l'outlier", "warn")
                await _save(sess)
                return {"ok": True, "need_more": True, "extra_run": True, "runs_done": len(runs)}
            if len(runs) > BASELINE_RUNS:
                med = sorted(fps)[len(fps) // 2]
                out_i = max(range(len(runs)), key=lambda i: abs((runs[i].get("fps_avg") or med) - med))
                dropped = runs.pop(out_i)
                _log(sess, f"Outlier scartato: run da {dropped.get('fps_avg')} FPS", "warn")
            stats = _run_stats(sess["baseline"]["runs"])
            sess["baseline"]["stats"] = stats
            sess["baseline"]["ref_ctx"] = (sess["baseline"]["runs"][-1].get("ctx") or {})
            sess["baseline0"] = dict(stats)
            sess["status"] = "testing"
            quality = _block_quality(sess["baseline"]["runs"])
            sess["quality"] = quality
            _log(sess, f"BASELINE stabile: {stats['fps_avg']} FPS avg | 1% low {stats['fps_p1']} | CV {stats['cv_pct']}%", "ok")
            if quality.get("capped"):
                # Con un cap attivo la distribuzione dei frametime e' piatta: il
                # Lab misurerebbe soltanto il cap, e ogni tweak risulterebbe
                # ininfluente per un motivo che non ha nulla a che vedere col PC.
                _log(sess, f"FRAME CAP rilevato a ~{quality.get('cap_fps')} FPS "
                           f"({round(100 * (quality.get('peak_share') or 0))}% dei frame sullo stesso valore): "
                           f"con V-Sync o un limitatore attivo nessun tweak puo' mostrare un effetto. "
                           f"Togli il limite e rilancia il Lab per una misura utile.", "warn")
            _log(sess, f"Fase TEST: {len(sess['queue'])} tweak in coda, uno alla volta")
            await _save(sess)
            return {"ok": True, "baseline_ok": True, "stats": stats, "quality": quality}

        # phase == test | pair_on | pair_off
        cur = sess.get("current")
        if sess["status"] != "testing" or not cur or cur["tweak_id"] != payload.tweak_id:
            return {"ok": False, "reason": "nessun test attivo per questo tweak"}

        paired = payload.phase in ("pair_on", "pair_off")
        if paired:
            key = "on_runs" if payload.phase == "pair_on" else "off_runs"
            cur.setdefault(key, []).append(run)
            done = len(cur.get("on_runs") or []) + len(cur.get("off_runs") or [])
            target = len(_pair_stages())
            _log(sess, f"Test {cur['tweak_id']} [{key[:-5].upper()}] misura {done}/{target}: "
                       f"{run.get('fps_avg')} FPS avg")
            if done < target:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": done, "runs_target": target,
                        "next_stage": _pair_stages()[done]}
            comp = _paired_compare(cur)
        else:
            cur["runs"].append(run)
            _log(sess, f"Test {cur['tweak_id']} run {len(cur['runs'])}: {run.get('fps_avg')} FPS avg")
            if len(cur["runs"]) < TEST_RUNS:
                await _save(sess)
                return {"ok": True, "need_more": True, "runs_done": len(cur["runs"])}
            comp = _blocked_compare(sess, cur)
        if not comp:
            return {"ok": False, "reason": "misure insufficienti per decidere"}

        delta, sig, sig_p1 = comp["delta"], comp["sig"], comp.get("sig_p1")
        kept, basis, reason = _verdict(comp)
        d = delta.get("fps_avg_pct") or 0
        tweak_meta = next((c for c in sess["candidates"] if c["tweak_id"] == cur["tweak_id"]), {})
        warnings = sorted({w for r_ in comp["runs"] for w in (r_.get("warnings") or [])})
        result = {
            "test_id": str(uuid.uuid4()),
            "tweak_id": cur["tweak_id"],
            "family": tweak_meta.get("family"),
            "runs": comp["runs"],
            "design": comp["design"],
            "n_pairs": comp.get("n_pairs"),
            "before_fps": comp["before_fps"],
            "after_fps": comp["after_fps"],
            "delta": delta,
            "warnings": warnings,
            "significance": {"method": sig["method"], "p_value": sig["p_value"],
                             "alpha": sig["alpha"], "significant": sig["significant"]},
            "significance_p1": ({"p_value": sig_p1["p_value"], "significant": sig_p1["significant"]} if sig_p1 else None),
            "decision": "kept" if kept else "rolled_back",
            "decision_basis": basis,
            "reason": reason,
            "at": now_iso(),
        }
        sess["results"].append(result)
        await _fleet_update(sess, cur["tweak_id"], kept, d,
                            comp["after_stats"].get("game") or (sess["baseline"].get("stats") or {}).get("game"))
        if kept:
            sess["kept"].append(cur["tweak_id"])
            # La baseline avanza per intero (statistiche E run): tenere i run
            # vecchi mentre le statistiche avanzano faceva rispondere al test di
            # significativita' una domanda diversa da quella del delta.
            sess["baseline"]["stats"] = comp["after_stats"]
            if paired:
                sess["baseline"]["runs"] = list(cur.get("on_runs") or [])
            else:
                sess["baseline"]["runs"] = list(cur["runs"])
            _log(sess, f"MANTENUTO {cur['tweak_id']}: {reason}. Nuovo riferimento: {comp['after_fps']} FPS", "ok")
        else:
            _log(sess, f"ROLLBACK {cur['tweak_id']}: {reason}", "warn")
        # Nello schema appaiato l'ultima misura e' con il tweak spento: se resta
        # va riacceso, se cade e' gia' nello stato giusto.
        already_off = bool(paired and cur.get("stage_state") == "off")
        if paired and kept and cur.get("stage_state") != "on":
            sess["final_toggle"] = {"tweak_id": cur["tweak_id"], "stage": "on"}
        _adapt_priors(sess, tweak_meta.get("family"), kept)
        sess["current"] = None
        stop_reason = _auto_stop(sess)
        completed = False
        if stop_reason or not sess.get("queue"):
            await _advance_after_testing(sess, stop_reason)
            completed = sess["status"] == "completed"
            if completed:
                sess["agent_ack"] = True
        await _save(sess)
        return {"ok": True, "decision": result["decision"], "reason": reason,
                "delta": delta, "significance": result["significance"],
                "design": comp["design"], "n_pairs": comp.get("n_pairs"),
                "already_off": already_off, "warnings": warnings,
                "completed": completed, "next_status": sess["status"],
                "remaining": len(sess.get("queue", []))}

    return r

