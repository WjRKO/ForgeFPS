import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import ai_credits
import ai_engine
from database import db, now_iso
from helpers import pc_context_text, compute_health
from models import ChatMessageInput
from plan_gate import require_pro

AI_RATE_LIMIT_PER_HOUR = 100

# ---------------- Gameplay Doctor (strati 1-2: firme frametime + correlatore) ----------------

_GD_GUI_TWEAKS = (
    "power=Piano energetico prestazioni massime; gaming=Boost gaming (Game Mode, HAGS, Game DVR off); "
    "priority=Priorita GPU/CPU ai giochi (MMCSS); timer=Timer resolution stabile; fse=Fullscreen optimizations off; "
    "mpo=MPO off; mouse=Precisione puntatore off; network=Ottimizzazione rete gaming; dns=DNS veloce; "
    "qos=QoS/throttling rete off; sysmain=SysMain off; bgapps=App in background off; debloat=Debloat servizi; "
    "clean=Pulizia file temporanei; visual=Effetti visivi minimi"
)


def _gd_parse_ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def _gd_last_session(samples: list, gap_s: int = 30) -> list:
    """Estrae l'ultima sessione contigua (gap tra campioni <= gap_s)."""
    if not samples:
        return []
    out = [samples[-1]]
    for i in range(len(samples) - 2, -1, -1):
        t1 = _gd_parse_ts(samples[i].get("ts"))
        t2 = _gd_parse_ts(out[0].get("ts"))
        if not t1 or not t2 or (t2 - t1).total_seconds() > gap_s:
            break
        out.insert(0, samples[i])
    return out


def _gd_pct(sorted_vals: list, p: float):
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


# --- Gameplay Doctor v2: correlatore causale con lag, pattern, dedup, baseline ---
_GD_BUCKET_MS = [i + 0.5 for i in range(50)] + [55, 65, 75, 85, 95, 112.5, 137.5, 175, 250, 350]

_GD_RULES = [
    ("gpu_thermal_throttle", "Throttling termico GPU", 0.9,
     lambda w: w.get("gpu_temp", 0) >= 83 and w.get("_gpu_declock")),
    ("vram_overflow", "VRAM satura", 0.85, lambda w: w.get("vram_used_pct", 0) >= 95),
    ("cpu_saturation", "CPU satura", 0.8, lambda w: w.get("cpu_util", 0) >= 90),
    ("cpu_thermal", "Limite termico CPU", 0.75, lambda w: w.get("cpu_temp", 0) >= 92),
    ("ram_pressure", "RAM quasi piena", 0.6, lambda w: w.get("ram_used_pct", 0) >= 90),
    ("vrm_thermal", "VRM caldi", 0.55, lambda w: w.get("vrm_temp", 0) >= 90),
    ("external_io", "Causa esterna (I/O disco o processo in background)", 0.35,
     lambda w: w.get("cpu_util", 100) < 75 and w.get("gpu_util", 100) < 75),
]


def _gd_hist_pct(hist: list, p: float):
    n = sum(hist)
    if n < 500:
        return None
    target = n * p
    c = 0
    for i, cnt in enumerate(hist):
        c += cnt
        if c >= target:
            return _GD_BUCKET_MS[i]
    return _GD_BUCKET_MS[-1]


def _gd_window(sess: list, i: int) -> dict:
    """Finestra causale con lag [campione precedente, corrente]: la causa
    (declock, saturazione) spesso PRECEDE il sintomo visibile."""
    w = {}
    for s in sess[max(0, i - 1):i + 1]:
        for k in ("cpu_util", "cpu_temp", "ram_used_pct", "vram_used_pct", "gpu_temp", "gpu_util", "vrm_temp"):
            v = s.get(k)
            if isinstance(v, (int, float)):
                w[k] = max(w.get(k, 0), v)
    return w


def _gd_pattern(times: list) -> str:
    if len(times) < 3:
        return "isolated"
    gaps = [t2 - t1 for t1, t2 in zip(times, times[1:])]
    m = sum(gaps) / len(gaps)
    if m > 0 and m < 120:
        cvv = (sum((g - m) ** 2 for g in gaps) / len(gaps)) ** 0.5 / m
        if cvv < 0.25:
            return "periodic"
    if sum(1 for g in gaps if g <= 10) >= max(1, int(len(gaps) * 0.6)):
        return "burst"
    return "sporadic"


def _gameplay_stats(sess: list) -> dict:
    """Strato deterministico v2: firme, eventi con finestra causale, dedup per
    causa comune, ordinamento per impatto reale (% sessione x peso causa)."""
    t0, t1 = _gd_parse_ts(sess[0].get("ts")), _gd_parse_ts(sess[-1].get("ts"))
    dur_s = (t1 - t0).total_seconds() if t0 and t1 else len(sess)
    duration_min = round(dur_s / 60.0, 1)
    fps = [s["fps"] for s in sess if isinstance(s.get("fps"), (int, float))]
    fps_sorted = sorted(fps)
    games = {}
    for s in sess:
        g = s.get("game") or s.get("game_name")
        if g:
            games[g] = games.get(g, 0) + 1
    game = max(games, key=games.get) if games else None
    gpu_clocks = sorted(s["gpu_clock"] for s in sess
                        if isinstance(s.get("gpu_clock"), (int, float)) and isinstance(s.get("gpu_util"), (int, float)) and s["gpu_util"] >= 80)
    med_clock = gpu_clocks[len(gpu_clocks) // 2] if gpu_clocks else None

    # percentili ESATTI dall'istogramma cumulativo di sessione (se agent v2)
    hist = next((s["ft_hist"] for s in reversed(sess) if isinstance(s.get("ft_hist"), list)), None)
    ft_p99_s = _gd_hist_pct(hist, 0.99) if hist else None
    ft_p999_s = _gd_hist_pct(hist, 0.999) if hist else None
    fps_1low = round(1000 / ft_p99_s) if ft_p99_s else None
    fps_01low = round(1000 / ft_p999_s) if ft_p999_s else None

    # eventi (hitch adattivi agent-side + fps drop) con cause ranked su finestra lag
    raw_events = []
    for i, s in enumerate(sess):
        sec = round((_gd_parse_ts(s["ts"]) - t0).total_seconds()) if t0 and s.get("ts") else i
        w = _gd_window(sess, i)
        w["_gpu_declock"] = bool(med_clock and isinstance(s.get("gpu_clock"), (int, float)) and s["gpu_clock"] < 0.92 * med_clock)
        if (s.get("hitches") or 0) >= 1 or (isinstance(s.get("ft_worst"), (int, float)) and s["ft_worst"] > 100):
            causes = sorted(({"cause": c, "label": lb, "score": wt} for c, lb, wt, pr in _GD_RULES if pr(w)), key=lambda x: -x["score"])
            raw_events.append({"sec": sec, "type": "hitch", "hitches": s.get("hitches") or 1,
                               "ft_worst_ms": s.get("ft_worst"), "causes": causes, "snap": w})
        elif isinstance(s.get("fps"), (int, float)) and i >= 10:
            prev = [x["fps"] for x in sess[max(0, i - 30):i] if isinstance(x.get("fps"), (int, float))]
            if prev and s["fps"] < 0.65 * (sum(prev) / len(prev)):
                causes = sorted(({"cause": c, "label": lb, "score": wt} for c, lb, wt, pr in _GD_RULES if pr(w)), key=lambda x: -x["score"])
                raw_events.append({"sec": sec, "type": "fps_drop", "fps": s["fps"], "causes": causes, "snap": w})

    # dedup: raggruppa per causa dominante -> 1 problema, N occorrenze
    groups = {}
    for ev in raw_events:
        top = ev["causes"][0] if ev["causes"] else {"cause": "unknown", "label": "Causa non determinata", "score": 0.2}
        g = groups.setdefault(top["cause"], {"cause": top["cause"], "label": top["label"], "weight": top["score"],
                                             "occurrences": 0, "secs": [], "types": {}, "worst_ms": 0,
                                             "ambiguous_with": {}, "snap_max": {}})
        g["occurrences"] += 1
        g["secs"].append(ev["sec"])
        g["types"][ev["type"]] = g["types"].get(ev["type"], 0) + 1
        if isinstance(ev.get("ft_worst_ms"), (int, float)):
            g["worst_ms"] = max(g["worst_ms"], ev["ft_worst_ms"])
        for c in ev["causes"][1:]:
            g["ambiguous_with"][c["label"]] = g["ambiguous_with"].get(c["label"], 0) + 1
        for k, v in ev["snap"].items():
            if not k.startswith("_") and isinstance(v, (int, float)):
                g["snap_max"][k] = max(g["snap_max"].get(k, 0), v)
    problems = []
    for g in groups.values():
        impact_pct = round(min(100.0, len(set(g["secs"])) / max(1.0, dur_s) * 100), 1)
        amb = [k for k, v in g["ambiguous_with"].items() if v >= g["occurrences"] * 0.5]
        problems.append({
            "cause": g["cause"], "label": g["label"], "occurrences": g["occurrences"],
            "pattern": _gd_pattern(sorted(set(g["secs"]))),
            "impact_pct": impact_pct,
            "impact_score": round(impact_pct * g["weight"], 2),
            "first_min": round(min(g["secs"]) / 60, 1), "last_min": round(max(g["secs"]) / 60, 1),
            "worst_frame_ms": g["worst_ms"] or None,
            "signals_max": g["snap_max"],
            "confidence_hint": "high" if g["weight"] >= 0.8 and not amb else ("low" if amb else "medium"),
            "concurrent_signals": amb,
        })
    problems.sort(key=lambda p: -p["impact_score"])

    pace = [s["pace_dev"] for s in sess if isinstance(s.get("pace_dev"), (int, float))]
    cv = [s["ft_cv"] for s in sess if isinstance(s.get("ft_cv"), (int, float))]
    lat = [s["latency_ms"] for s in sess if isinstance(s.get("latency_ms"), (int, float))]
    fps_avg = round(sum(fps) / len(fps)) if fps else None
    fps_p1_approx = _gd_pct(fps_sorted, 0.01)
    return {
        "duration_min": duration_min, "samples": len(sess), "game": game,
        "fps_avg": fps_avg, "fps_min": fps_sorted[0] if fps_sorted else None,
        "fps_max": fps_sorted[-1] if fps_sorted else None,
        "fps_1pct_low": fps_1low or fps_p1_approx,
        "fps_01pct_low": fps_01low,
        "exact_percentiles": bool(hist),
        "stutter_index": round((fps_1low or fps_p1_approx) / fps_avg, 2) if fps_avg and (fps_1low or fps_p1_approx) else None,
        "hitch_total": sum(s.get("hitches") or 0 for s in sess),
        "hitch_threshold_ms": next((s["hitch_thr"] for s in reversed(sess) if isinstance(s.get("hitch_thr"), (int, float))), None),
        "pace_cv_avg": round(sum(cv) / len(cv), 3) if cv else None,
        "pace_dev_avg_ms": round(sum(pace) / len(pace), 2) if pace else None,
        "latency_avg_ms": round(sum(lat) / len(lat)) if lat else None,
        "gpu_temp_max": max((s.get("gpu_temp") or 0) for s in sess) or None,
        "cpu_temp_max": max((s.get("cpu_temp") or 0) for s in sess) or None,
        "gpu_clock_median_mhz": med_clock,
        "problems": problems[:6],
        "has_frametime_data": bool(cv or any(isinstance(s.get("ft_p99"), (int, float)) for s in sess)),
        "_timeline_fps": [{"m": round(i * (dur_s / max(1, len(sess))) / 60, 2), "fps": s.get("fps")}
                          for i, s in enumerate(sess) if isinstance(s.get("fps"), (int, float))][::max(1, len(sess) // 120)],
        "_events": [{"m": round(e["sec"] / 60, 2), "type": e["type"],
                     "cause": (e["causes"][0]["cause"] if e["causes"] else "unknown")} for e in raw_events][:60],
    }




async def _enrich_specs_for_ai(uid: str, specs: dict | None) -> dict:
    """Aggiunge benchmark history (ultimi 5) + tracker summary a specs per il context AI."""
    out = dict(specs) if specs else {}
    # Benchmark history
    try:
        hist = await db.benchmarks.find(
            {"user_id": uid}, {"_id": 0, "after": 1, "created_at": 1, "timestamp": 1}
        ).sort([("created_at", -1), ("timestamp", -1)]).limit(5).to_list(5)
        if hist:
            out["benchmark_history"] = hist
    except Exception:
        pass
    # Tracker summary
    try:
        products = await db.products.find(
            {"user_id": uid}, {"_id": 0, "initial_price": 1, "current_price": 1}
        ).to_list(500)
        saved = sum(
            max(0, (p.get("initial_price") or 0) - (p.get("current_price") or 0))
            for p in products if p.get("initial_price") is not None and p.get("current_price") is not None
        )
        out["tracker_summary"] = {"count": len(products), "total_saved": round(saved, 2)}
    except Exception:
        pass
    return out


class PlannedActionInput(BaseModel):
    title: str
    description: str = ""
    impact: str = ""
    difficulty: str = "facile"  # facile | medio | avanzato
    kind: str = "tweak"  # tweak | benchmark | driver | manual
    tweak_id: str = ""
    source: str = "advisor_diagnose"


class FeedbackInput(BaseModel):
    target_type: str  # "diagnose_action" | "chat_message"
    target_id: str    # diagnose id or chat message id
    action_title: str = ""  # solo per diagnose_action
    rating: str  # "up" | "down"
    comment: str = ""


class AppliedTweakInput(BaseModel):
    title: str
    active: bool = True  # true=segnalo come attivo, false=rimuovo il flag


def _slug(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:80]


async def _get_user_profile(uid: str) -> dict:
    """Restituisce info utili all'AI: tweak gia' attivi, feedback aggregati.
    Usato come 'memoria personalizzata' iniettata nel prompt."""
    applied = await db.applied_tweaks.find(
        {"user_id": uid, "active": True}, {"_id": 0, "title": 1, "slug": 1}
    ).to_list(100)
    # Feedback aggregati: prendo l'ultimo mese
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    thumbs_down = await db.ai_feedback.find(
        {"user_id": uid, "rating": "down", "created_at": {"$gte": since}, "action_title": {"$ne": ""}},
        {"_id": 0, "action_title": 1, "comment": 1},
    ).sort("created_at", -1).to_list(20)
    return {"applied_tweaks": applied, "disliked": thumbs_down}


async def _community_insights(uid: str, specs: dict) -> list:
    """Trova utenti con hardware simile che hanno applicato azioni e visto miglioramenti
    di health/benchmark. Ritorna una lista di stringhe da iniettare nel prompt come few-shot."""
    data = (specs or {}).get("data") or {}
    cpu_key = (data.get("cpu") or "").split()[0:3]  # es. "AMD Ryzen 7"
    gpu_key = (data.get("gpu") or "").split()[0:3]  # es. "NVIDIA RTX 3070"
    if not cpu_key and not gpu_key:
        return []
    try:
        # utenti con CPU famiglia simile (case-insensitive substring del primo brand)
        cpu_prefix = " ".join(cpu_key[:2]) if cpu_key else ""
        gpu_prefix = " ".join(gpu_key[:2]) if gpu_key else ""
        query = {"user_id": {"$ne": uid}, "active": True}
        docs = await db.applied_tweaks.find(query, {"_id": 0, "title": 1, "user_id": 1}).limit(500).to_list(500)
        if not docs:
            return []
        # Aggrega per titolo
        from collections import Counter
        titles = Counter([d["title"] for d in docs])
        top = titles.most_common(5)
        out = []
        for title, count in top:
            if count >= 2:
                out.append(f"- '{title}' \u2192 gi\u00e0 applicato da {count} utenti con hardware simile")
        return out[:5]
    except Exception:
        return []


COACH_PROMPTS = {
    "default": "",
    "fps": "\n\n[MODALITA' COACH FPS] Tono da coach gaming aggressivo. Focus assoluto su FPS, frametime, latenza, jitter e input lag. Consigli concreti per gaming competitivo (Valorant, CS2, Fortnite). Non perdere tempo su feature 'nice to have'.",
    "streaming": "\n\n[MODALITA' COACH STREAMING] Focus su OBS Studio, bitrate, encoding (x264/NVENC/AV1), scenes, audio, monitoraggio dropped frames, upload stability. Interpretazione ottimale del canale Twitch/YouTube dell'utente.",
    "troubleshoot": "\n\n[MODALITA' TROUBLESHOOT] Rispondi in modalita' 'passo dopo passo' guidata: 1 azione per messaggio, chiedi cosa succede dopo, adatta la strategia. Focus su BSOD, crash, driver issues, stutter, freeze.",
    "build": "\n\n[MODALITA' CONSULENTE BUILD] Focus su acquisti hardware: rapporto prezzo/prestazioni, compatibilita', bottleneck, next upgrade suggerito. Cita modelli concreti disponibili sul mercato IT (Amazon, PCPartPicker) e range di prezzo.",
}


class ChatMessageInputExt(ChatMessageInput):
    # Override message to allow empty string when an image is attached.
    # The endpoint will require at least one of {message, image_data_url}.
    message: str = Field(default="", max_length=2000)
    mode: str = "default"
    image_data_url: str = ""


async def _check_ai_rate_limit(uid: str):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    used = await db.chat_messages.count_documents(
        {"user_id": uid, "role": "user", "created_at": {"$gte": cutoff}})
    if used >= AI_RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429,
                            detail=f"Limite AI raggiunto ({AI_RATE_LIMIT_PER_HOUR} richieste/ora). Riprova più tardi.")


def build(get_current_user):
    r = APIRouter(prefix="/api/advisor", tags=["advisor"])
    require_pro_dep = require_pro(get_current_user)

    @r.get("/sessions")
    async def list_sessions(user: dict = Depends(get_current_user)):
        return await db.chat_sessions.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("updated_at", -1).to_list(100)

    @r.get("/suggestions")
    async def suggestions(lang: str = "it", user: dict = Depends(get_current_user)):
        specs = await db.pc_specs.find_one({"user_id": str(user["_id"])}, {"_id": 0})
        d = (specs or {}).get("data", {})
        health = (specs or {}).get("health")
        gpu = (d.get("gpu") or "").upper()
        out = []
        if health:
            fix_by_id = {
                "gpu_temp": "La mia GPU scalda troppo: come abbasso le temperature?",
                "cpu_temp": "La mia CPU raggiunge temperature alte: come la raffreddo meglio?",
                "power": "Come attivo il piano energetico ad alte prestazioni per più FPS?",
                "driver": "I miei driver GPU sono vecchi: come li aggiorno in sicurezza?",
                "startup": "Quali programmi all'avvio posso disabilitare per un boot più veloce?",
                "game_mode": "Come attivo Game Mode e GPU Scheduling su Windows?",
                "hags": "Come abilito l'Hardware-Accelerated GPU Scheduling?",
                "disk": "Come libero spazio sul disco C: in sicurezza?",
                "ram": "La mia RAM è molto utilizzata: come la ottimizzo per il gaming?",
                "temp": "Come pulisco i file temporanei e la cache di Windows?",
            }
            h = compute_health(health)
            for c in sorted(h["checks"], key=lambda x: 0 if x["status"] == "bad" else 1):
                if c["status"] in ("bad", "warn") and c["id"] in fix_by_id:
                    q = fix_by_id[c["id"]]
                    if q not in out:
                        out.append(q)
        if "NVIDIA" in gpu or "GEFORCE" in gpu or "RTX" in gpu or "GTX" in gpu:
            out.append("Migliori impostazioni del pannello NVIDIA per il gaming competitivo")
        elif "AMD" in gpu or "RADEON" in gpu:
            out.append("Migliori impostazioni di AMD Adrenalin per il gaming competitivo")
        defaults = [
            "Come riduco l'input lag per il gaming competitivo?",
            "Migliori impostazioni OBS per streaming a 1080p60",
            "Come ottimizzo Windows 11 per FPS massimi?",
            "Tweak per abbassare le temperature della GPU",
        ]
        for q in defaults:
            if len(out) >= 4:
                break
            if q not in out:
                out.append(q)
        out = out[:4]
        if (lang or "it").startswith("en"):
            en_map = {
                "La mia GPU scalda troppo: come abbasso le temperature?": "My GPU runs too hot: how do I lower the temperatures?",
                "La mia CPU raggiunge temperature alte: come la raffreddo meglio?": "My CPU gets too hot: how do I cool it better?",
                "Come attivo il piano energetico ad alte prestazioni per più FPS?": "How do I enable the high-performance power plan for more FPS?",
                "I miei driver GPU sono vecchi: come li aggiorno in sicurezza?": "My GPU drivers are old: how do I update them safely?",
                "Quali programmi all'avvio posso disabilitare per un boot più veloce?": "Which startup programs can I disable for a faster boot?",
                "Come attivo Game Mode e GPU Scheduling su Windows?": "How do I enable Game Mode and GPU Scheduling on Windows?",
                "Come abilito l'Hardware-Accelerated GPU Scheduling?": "How do I enable Hardware-Accelerated GPU Scheduling?",
                "Come libero spazio sul disco C: in sicurezza?": "How do I free up space on drive C: safely?",
                "La mia RAM è molto utilizzata: come la ottimizzo per il gaming?": "My RAM usage is high: how do I optimize it for gaming?",
                "Come pulisco i file temporanei e la cache di Windows?": "How do I clean temporary files and the Windows cache?",
                "Migliori impostazioni del pannello NVIDIA per il gaming competitivo": "Best NVIDIA Control Panel settings for competitive gaming",
                "Migliori impostazioni di AMD Adrenalin per il gaming competitivo": "Best AMD Adrenalin settings for competitive gaming",
                "Come riduco l'input lag per il gaming competitivo?": "How do I reduce input lag for competitive gaming?",
                "Migliori impostazioni OBS per streaming a 1080p60": "Best OBS settings for 1080p60 streaming",
                "Come ottimizzo Windows 11 per FPS massimi?": "How do I optimize Windows 11 for maximum FPS?",
                "Tweak per abbassare le temperature della GPU": "Tweaks to lower GPU temperatures",
            }
            out = [en_map.get(q, q) for q in out]
        return {"suggestions": out, "personalized": bool(health)}


    @r.get("/sessions/{session_id}")
    async def get_session(session_id: str, user: dict = Depends(get_current_user)):
        return await db.chat_messages.find(
            {"session_id": session_id, "user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", 1).to_list(500)

    @r.delete("/sessions/{session_id}")
    async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
        await db.chat_messages.delete_many({"session_id": session_id, "user_id": str(user["_id"])})
        await db.chat_sessions.delete_one({"id": session_id, "user_id": str(user["_id"])})
        return {"ok": True}

    @r.get("/credits")
    async def ai_credits_status(user: dict = Depends(get_current_user)):
        """Quota messaggi AI: crediti (starter), settimanale (pro), illimitato (streamer)."""
        return await ai_credits.get_ai_quota(db, user)

    @r.post("/chat")
    async def advisor_chat(data: ChatMessageInputExt, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        await _check_ai_rate_limit(uid)
        quota = await ai_credits.get_ai_quota(db, user)
        if quota["mode"] == "weekly" and quota["remaining"] <= 0:
            raise HTTPException(status_code=402, detail={
                "code": "weekly_limit",
                "message": f"Hai raggiunto i {quota['limit']} messaggi settimanali del piano Pro. Il limite si azzera lunedì.",
                "resets_at": quota["resets_at"],
            })
        consumed_bucket = None
        if quota["mode"] == "credits":
            if quota["total"] <= 0:
                raise HTTPException(status_code=402, detail={
                    "code": "no_credits",
                    "message": "Crediti AI esauriti. Completa missioni (+2) o sblocca trofei (+5/15) per guadagnarne altri, oppure passa a Pro.",
                    "upgrade_url": "/pricing",
                })
            consumed_bucket = await ai_credits.consume_credit(db, user)
        image_data_url = (data.image_data_url or "").strip()
        # Require at least one of {message, image}
        if not (data.message or "").strip() and not image_data_url:
            raise HTTPException(status_code=422, detail="Serve un messaggio o un'immagine.")
        # Fallback text if only an image is sent, so history/session title stay meaningful
        if not (data.message or "").strip():
            data.message = "Analizza questa immagine e dammi consigli concreti."
        session_id = data.session_id or str(uuid.uuid4())
        if not await db.chat_sessions.find_one({"id": session_id, "user_id": uid}):
            title = data.message[:40] + ("..." if len(data.message) > 40 else "")
            await db.chat_sessions.insert_one({"id": session_id, "user_id": uid, "title": title,
                                               "created_at": now_iso(), "updated_at": now_iso()})
        history = await db.chat_messages.find(
            {"session_id": session_id, "user_id": uid}, {"_id": 0}).sort("created_at", 1).to_list(500)
        await db.chat_messages.insert_one({"id": str(uuid.uuid4()), "session_id": session_id, "user_id": uid,
                                           "role": "user", "content": data.message, "created_at": now_iso()})
        # v0.7.7 Milestones: track advisor usage
        try:
            from milestones import bump_counter, track_daily_active
            await bump_counter(db, uid, "advisor_messages", 1)
            await track_daily_active(db, uid)
        except Exception:
            pass
        specs = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})
        specs = await _enrich_specs_for_ai(uid, specs)
        specs_text = pc_context_text(specs)
        # Coach mode: aggiunge un suffisso al system prompt
        coach_suffix = COACH_PROMPTS.get(data.mode or "default", "")
        specs_text_full = (specs_text or "") + coach_suffix
        # Image (multi-modal): passa come nota aggiuntiva al messaggio se presente
        message_augmented = data.message

        async def gen():
            yield f"__SESSION__{session_id}__\n"
            full = ""
            try:
                async for chunk in ai_engine.stream_advisor(
                    session_id, history, message_augmented, specs_text_full,
                    data.lang or "it", image_data_url=image_data_url,
                ):
                    full += chunk
                    yield chunk
            except Exception as e:
                err = f"\n\n[Errore AI: {str(e)[:120]}]"
                full += err
                yield err
                await ai_credits.refund_credit(db, user, consumed_bucket)
            await db.chat_messages.insert_one({"id": str(uuid.uuid4()), "session_id": session_id, "user_id": uid,
                                               "role": "assistant", "content": full, "created_at": now_iso()})
            await db.chat_sessions.update_one({"id": session_id, "user_id": uid}, {"$set": {"updated_at": now_iso()}})

        return StreamingResponse(gen(), media_type="text/plain",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


    @r.get("/diagnose/latest")
    async def get_latest_diagnose(user: dict = Depends(get_current_user)):
        """Ritorna l'ultima diagnosi salvata (o 204 se nessuna). Usato dal frontend
        per ripristinare il pannello quando l'utente torna sulla pagina Advisor."""
        uid = str(user["_id"])
        doc = await db.diagnoses.find_one(
            {"user_id": uid}, sort=[("created_at", -1)]
        )
        if not doc:
            return {"available": False}
        return {
            "available": True,
            "id": doc.get("id"),
            "summary": doc.get("summary", ""),
            "actions": doc.get("actions", []),
            "created_at": doc.get("created_at"),
        }

    class DiagnoseInput(BaseModel):
        lang: str = "it"

    @r.post("/diagnose")
    async def diagnose_pc(data: DiagnoseInput | None = None, user: dict = Depends(require_pro_dep)):
        """Genera una diagnosi strutturata: 3-5 azioni prioritizzate per il PC dell'utente.
        Ritorna JSON. Rate limited come chat."""
        uid = str(user["_id"])
        await _check_ai_rate_limit(uid)
        specs = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})
        if not specs or not (specs.get("data") or {}).get("cpu"):
            raise HTTPException(
                status_code=400,
                detail="Nessuna configurazione hardware rilevata. Esegui prima l'agent dalla pagina FrameForge Agent.",
            )
        specs = await _enrich_specs_for_ai(uid, specs)
        specs_text = pc_context_text(specs)
        # Fase 3: personalization + Fase 2: community
        profile = await _get_user_profile(uid)
        community = await _community_insights(uid, specs)
        extra_context = ""
        if profile["applied_tweaks"]:
            extra_context += "\n\n[TWEAK GIA' ATTIVI sul PC dell'utente - NON riproporli come nuove azioni]:\n"
            extra_context += "\n".join(f"- {t['title']}" for t in profile["applied_tweaks"])
        if profile["disliked"]:
            extra_context += "\n\n[FEEDBACK NEGATIVI passati - EVITA suggerimenti simili]:\n"
            extra_context += "\n".join(
                f"- '{d['action_title']}'" + (f" (motivo: {d['comment'][:100]})" if d.get('comment') else "")
                for d in profile["disliked"][:5]
            )
        if community:
            extra_context += "\n\n[COMMUNITY - utenti con hardware simile hanno applicato queste azioni]:\n"
            extra_context += "\n".join(community)
        lang = (data.lang if data else "it") or "it"
        is_en = lang.startswith("en")
        difficulty_values = "easy|medium|advanced" if is_en else "facile|medio|avanzato"
        lang_instruction = (
            "Respond in English only. All strings in the JSON (summary, title, description, verify, impact, cta) MUST be in English."
            if is_en else
            "Rispondi in italiano. Tutte le stringhe del JSON (summary, title, description, verify, impact, cta) DEVONO essere in italiano."
        )
        prompt = (
            "Analizza in maniera strutturata il PC dell'utente e proponi 3-5 azioni "
            "concrete e prioritizzate per migliorarne performance/latenza/stabilita' in gaming e streaming.\n"
            "Rispondi ESCLUSIVAMENTE con un JSON valido (senza testo prima o dopo, senza fence markdown) "
            "in questo schema esatto:\n"
            "{\n"
            "  \"summary\": \"1-2 frasi che riassumono lo stato del PC\",\n"
            "  \"actions\": [\n"
            "    {\n"
            "      \"title\": \"titolo breve, verbo iniziale (es. 'Attiva GPU Scheduling')\",\n"
            "      \"description\": \"2-4 frasi che spiegano cosa fare e perche'\",\n"
            "      \"verify\": \"1-2 frasi: come verificare se e' gia' attivo (percorso Windows Settings o comando PowerShell/registry)\",\n"
            "      \"impact\": \"stima misurabile (es. '+5-10% FPS', '-10 ms latency', '-5\\u00b0C GPU')\",\n"
            f"      \"difficulty\": \"{difficulty_values}\",\n"
            "      \"kind\": \"tweak|driver|hardware|maintenance|manual\",\n"
            "      \"cta\": \"testo del pulsante consigliato (max 25 char)\",\n"
            "      \"priority\": 1\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Priorita' 1 = massima. Ordina per priorita' decrescente. Usa il contesto PC reale. Il campo "
            "'verify' e' SEMPRE obbligatorio e concreto (percorso o comando). Non ripetere azioni gia' "
            f"applicate. {lang_instruction}"
        )
        try:
            raw = await ai_engine.one_shot_advisor(prompt, specs_text=specs_text + extra_context, lang=lang)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Errore AI: {str(e)[:200]}")
        raw = (raw or "").strip()
        # Rimuove eventuali fence markdown
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            data = json.loads(raw)
        except Exception:
            # Prova a estrarre la prima parentesi graffa
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(raw[start:end + 1])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"AI non ha restituito JSON valido: {str(e)[:200]}",
                    )
            else:
                raise HTTPException(status_code=500, detail="AI non ha restituito JSON valido")
        # Persist snapshot
        diagnose_id = str(uuid.uuid4())
        await db.diagnoses.insert_one({
            "id": diagnose_id,
            "user_id": uid,
            "summary": data.get("summary", ""),
            "actions": data.get("actions", []),
            "created_at": now_iso(),
        })
        return {"id": diagnose_id, **data}


    @r.post("/gameplay-doctor")
    async def gameplay_doctor(data: DiagnoseInput | None = None, user: dict = Depends(require_pro_dep)):
        """Gameplay Doctor: analizza le firme frametime dell'ultima sessione di
        monitoring, le correla con la telemetria (strato deterministico) e genera
        il referto AI con soluzioni collegate al PC reale."""
        uid = str(user["_id"])
        await _check_ai_rate_limit(uid)
        tel = await db.pc_telemetry.find_one({"user_id": uid}, {"_id": 0, "samples": 1})
        samples = (tel or {}).get("samples") or []
        sess = _gd_last_session(samples)
        if len(sess) < 60:
            raise HTTPException(status_code=400, detail="Sessione troppo corta: servono almeno 60 secondi di monitoraggio live (avvia il monitor e gioca qualche minuto).")
        stats = _gameplay_stats(sess)
        specs = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})
        specs_text = ""
        if specs and (specs.get("data") or {}).get("cpu"):
            specs = await _enrich_specs_for_ai(uid, specs)
            specs_text = pc_context_text(specs)
        lang = (data.lang if data else "it") or "it"
        is_en = lang.startswith("en")
        lang_instruction = (
            "Respond in English only: all JSON strings MUST be in English."
            if is_en else "Rispondi in italiano: tutte le stringhe del JSON DEVONO essere in italiano."
        )
        no_ft_note = "" if stats["has_frametime_data"] else (
            "\nNOTA: nessun dato frametime per-frame (PresentMon non attivo o agent datato): "
            "basa l'analisi su FPS/telemetria e suggerisci di aggiornare l'agent per l'analisi completa."
        )
        timeline = {"fps": stats.pop("_timeline_fps", []), "events": stats.pop("_events", [])}
        # baseline storica personale (stessa macchina/gioco, ultime 5 sessioni)
        baseline = None
        prev_reports = []
        if stats.get("game"):
            prev_reports = await db.gameplay_reports.find(
                {"user_id": uid, "stats.game": stats["game"]}, {"_id": 0, "stats": 1, "report": 1}
            ).sort("created_at", -1).to_list(5)
        if prev_reports:
            def _avg(key):
                vals = [p["stats"].get(key) for p in prev_reports if isinstance(p.get("stats", {}).get(key), (int, float))]
                return round(sum(vals) / len(vals), 1) if vals else None
            def _delta(cur, base):
                return round((cur - base) / base * 100, 1) if isinstance(cur, (int, float)) and base else None
            b_fps, b_low, b_hitch = _avg("fps_avg"), _avg("fps_1pct_low"), _avg("hitch_total")
            baseline = {
                "sessions": len(prev_reports), "game": stats["game"],
                "fps_avg_base": b_fps, "fps_avg_delta_pct": _delta(stats.get("fps_avg"), b_fps),
                "fps_1low_base": b_low, "fps_1low_delta_pct": _delta(stats.get("fps_1pct_low"), b_low),
                "hitch_base": b_hitch, "hitch_delta_pct": _delta(stats.get("hitch_total"), b_hitch),
            }
        # badge "risolto": problemi del referto precedente che non si ripresentano
        resolved = []
        if prev_reports:
            prev_ids = {i.get("id") or i.get("type") for i in (prev_reports[0].get("report", {}).get("issues") or [])}
            cur_ids = {p["cause"] for p in stats.get("problems", [])}
            resolved = sorted(x for x in prev_ids if x and x not in cur_ids and x != "unknown")
        prompt = (
            "Sei il Gameplay Doctor di FrameForge: genera un REPORT TECNICO (non una chat) "
            "dalla sessione di gioco analizzata. Il referto sotto contiene problemi GIA' deduplicati, "
            "correlati (finestra causale con lag) e ORDINATI PER IMPATTO REALE (% sessione x peso causa): "
            "MANTIENI quell'ordine.\n\n"
            "[REFERTO SESSIONE]\n" + json.dumps(stats, ensure_ascii=False) + no_ft_note + "\n\n"
            + ("[BASELINE STORICA STESSO GIOCO]\n" + json.dumps(baseline, ensure_ascii=False) + "\n\n" if baseline else "")
            + "[TWEAK APPLICABILI NELLA GUI FRAMEFORGE (id=nome)]\n" + _GD_GUI_TWEAKS + "\n\n"
            "REGOLE FERREE:\n"
            "1. TONO da report tecnico: niente frasi da chat ('ho analizzato i tuoi dati', 'ottima domanda').\n"
            "2. NON puoi affermare una causa senza citare i numeri esatti a supporto (clock, temperature, minuti, durate) nel campo evidence.\n"
            "3. Separa SEMPRE fatto e ipotesi: evidence = solo numeri dal referto; diagnosis = inferenza.\n"
            "4. confidence: usa il confidence_hint del referto; se concurrent_signals non vuoto, esplicita l'incertezza in diagnosis ('probabile X, ma anche Y era vicino al limite').\n"
            "5. Un solo fix primario per problema (con gui_tweak dal catalogo se pertinente), alternative come opzioni secondarie.\n"
            "6. fix_impact_estimate: SOLO se deducibile dai dati del referto (es. '7% di clock perso per throttling => recupero stimato ~7%'), altrimenti null. MAI inventare statistiche di altri utenti.\n"
            "7. Massimo 4 issues; sessione pulita => issues=[] e health=good.\n"
            "Rispondi ESCLUSIVAMENTE con JSON valido (niente testo fuori, niente fence):\n"
            "{\n"
            "  \"executive_summary\": {\"main_problem\": \"1 riga\", \"main_fix\": \"1 riga\"},\n"
            "  \"verdict\": \"2-3 frasi tecniche di sintesi\",\n"
            "  \"health\": \"good|minor|bad\", \"score\": 0-100,\n"
            "  \"issues\": [\n"
            "    {\"id\": \"usa il campo cause del problema (es. gpu_thermal_throttle)\",\n"
            "     \"type\": \"microstuttering|hitching|fps_drop|throttling|frame_pacing|input_lag|other\",\n"
            "     \"severity\": \"low|medium|high\", \"confidence\": \"high|medium|low\",\n"
            "     \"impact_pct\": numero, \"occurrences\": numero, \"pattern\": \"isolated|sporadic|periodic|burst\",\n"
            "     \"title\": \"titolo breve\",\n"
            "     \"simple_text\": \"1 frase semplice per utente casual\",\n"
            "     \"evidence\": \"SOLO numeri esatti dal referto\",\n"
            "     \"diagnosis\": \"inferenza, con incertezza esplicita se serve\",\n"
            "     \"tech_detail\": \"2-4 frasi tecniche con i numeri\",\n"
            "     \"fix\": {\"primary\": {\"text\": \"azione\", \"gui_tweak\": \"id o null\"},\n"
            "               \"alternatives\": [{\"text\": \"...\", \"gui_tweak\": \"id o null\"}],\n"
            "               \"impact_estimate\": \"stima o null\"}},\n"
            "  ],\n"
            "  \"comparison\": \"1-2 frasi vs baseline storica (null se assente)\",\n"
            "  \"positive\": \"1 frase su cosa funziona bene\"\n"
            "}\n" + lang_instruction
        )
        try:
            raw = await ai_engine.one_shot_advisor(prompt, specs_text=specs_text, lang=lang)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Errore AI: {str(e)[:200]}")
        raw = (raw or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            report = json.loads(raw)
        except Exception:
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    report = json.loads(raw[start:end + 1])
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"AI non ha restituito JSON valido: {str(e)[:200]}")
            else:
                raise HTTPException(status_code=500, detail="AI non ha restituito JSON valido")
        doc = {
            "id": str(uuid.uuid4()), "user_id": uid,
            "stats": stats, "report": report,
            "timeline": timeline, "baseline": baseline, "resolved": resolved,
            "created_at": now_iso(),
        }
        await db.gameplay_reports.insert_one({**doc})
        doc.pop("_id", None)
        return doc

    @r.get("/gameplay-doctor/latest")
    async def gameplay_doctor_latest(user: dict = Depends(get_current_user)):
        row = await db.gameplay_reports.find_one({"user_id": str(user["_id"])}, {"_id": 0}, sort=[("created_at", -1)])
        return {"report": row}

    @r.get("/planned-actions")
    async def list_planned_actions(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        items = await db.planned_actions.find(
            {"user_id": uid, "done": {"$ne": True}}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return items

    @r.post("/planned-actions")
    async def save_planned_action(data: PlannedActionInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            **data.model_dump(),
            "done": False,
            "created_at": now_iso(),
        }
        await db.planned_actions.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @r.post("/planned-actions/{action_id}/done")
    async def mark_action_done(action_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        res = await db.planned_actions.update_one(
            {"id": action_id, "user_id": uid},
            {"$set": {"done": True, "done_at": now_iso()}},
        )
        if res.matched_count == 0:
            raise HTTPException(404, "Azione non trovata")
        return {"ok": True}

    @r.delete("/planned-actions/{action_id}")
    async def delete_planned_action(action_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        res = await db.planned_actions.delete_one({"id": action_id, "user_id": uid})
        if res.deleted_count == 0:
            raise HTTPException(404, "Azione non trovata")
        return {"ok": True}


    @r.post("/followups")
    async def generate_followups(session_id: str, lang: str = "it", user: dict = Depends(get_current_user)):
        """Genera 3 follow-up brevi dopo l'ultima risposta AI di una sessione."""
        uid = str(user["_id"])
        history = await db.chat_messages.find(
            {"session_id": session_id, "user_id": uid}, {"_id": 0}
        ).sort("created_at", 1).to_list(500)
        if not history:
            return {"suggestions": []}
        try:
            sug = await ai_engine.generate_followups(history, lang=lang)
        except Exception as e:
            return {"suggestions": [], "error": str(e)[:200]}
        return {"suggestions": sug}


    # -------- Fase 1: Feedback thumbs up/down --------
    @r.post("/feedback")
    async def submit_feedback(data: FeedbackInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        if data.rating not in ("up", "down"):
            raise HTTPException(400, "rating deve essere 'up' o 'down'")
        # Upsert per evitare duplicati
        await db.ai_feedback.update_one(
            {"user_id": uid, "target_type": data.target_type, "target_id": data.target_id},
            {"$set": {
                "user_id": uid,
                "target_type": data.target_type,
                "target_id": data.target_id,
                "action_title": data.action_title,
                "rating": data.rating,
                "comment": data.comment[:500],
                "created_at": now_iso(),
            }},
            upsert=True,
        )
        return {"ok": True}

    # -------- Fase 3: Applied Tweaks (personalization memory) --------
    @r.get("/applied-tweaks")
    async def list_applied(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        docs = await db.applied_tweaks.find(
            {"user_id": uid, "active": True}, {"_id": 0}
        ).sort("applied_at", -1).to_list(200)
        return docs

    @r.post("/applied-tweaks")
    async def toggle_applied(data: AppliedTweakInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        slug = _slug(data.title)
        if not slug:
            raise HTTPException(400, "title vuoto")
        await db.applied_tweaks.update_one(
            {"user_id": uid, "slug": slug},
            {"$set": {
                "user_id": uid,
                "slug": slug,
                "title": data.title[:200],
                "active": bool(data.active),
                "applied_at": now_iso(),
            }},
            upsert=True,
        )
        # v0.7.7 Milestones: track only new activations (bump when toggling to active=True)
        if bool(data.active):
            try:
                from milestones import bump_counter
                await bump_counter(db, uid, "tweaks_applied", 1)
            except Exception:
                pass
        return {"ok": True, "slug": slug, "active": bool(data.active)}

    # -------- Fase 1: Outcome tracking (delta benchmark dopo diagnosi) --------
    @r.get("/outcome")
    async def diagnose_outcome(user: dict = Depends(get_current_user)):
        """Calcola il delta di health score / benchmark tra il momento dell'ultima diagnosi
        e i benchmark successivi. Ritorna 'available: false' se non c'e' abbastanza dato."""
        uid = str(user["_id"])
        last_diag = await db.diagnoses.find_one({"user_id": uid}, sort=[("created_at", -1)])
        if not last_diag:
            return {"available": False}
        diag_at = last_diag.get("created_at")
        # benchmark dopo il diagnose
        after = await db.benchmarks.find_one(
            {"user_id": uid, "created_at": {"$gt": diag_at}},
            sort=[("created_at", 1)],
        )
        # benchmark prima del diagnose (o il piu' recente prima)
        before = await db.benchmarks.find_one(
            {"user_id": uid, "created_at": {"$lte": diag_at}},
            sort=[("created_at", -1)],
        )
        if not after or not before:
            return {"available": False, "diagnosis_at": diag_at}
        b_score = (before.get("after") or {}).get("overall") or 0
        a_score = (after.get("after") or {}).get("overall") or 0
        delta = a_score - b_score
        return {
            "available": True,
            "diagnosis_at": diag_at,
            "before_score": b_score,
            "after_score": a_score,
            "delta": delta,
            "actions_count": len(last_diag.get("actions", [])),
        }

    return r
