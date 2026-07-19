import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import ai_engine
from database import db, now_iso
from helpers import pc_context_text, compute_health
from models import ChatMessageInput

AI_RATE_LIMIT_PER_HOUR = 100


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

    @r.post("/chat")
    async def advisor_chat(data: ChatMessageInputExt, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        await _check_ai_rate_limit(uid)
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

    @r.post("/diagnose")
    async def diagnose_pc(user: dict = Depends(get_current_user)):
        """Genera una diagnosi strutturata: 3-5 azioni prioritizzate per il PC dell'utente.
        Ritorna JSON. Rate limited come chat."""
        uid = str(user["_id"])
        await _check_ai_rate_limit(uid)
        specs = await db.pc_specs.find_one({"user_id": uid}, {"_id": 0})
        if not specs or not (specs.get("data") or {}).get("cpu"):
            raise HTTPException(
                status_code=400,
                detail="Nessuna configurazione hardware rilevata. Esegui prima l'agent dalla pagina Desktop Agent.",
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
            "      \"difficulty\": \"facile|medio|avanzato\",\n"
            "      \"kind\": \"tweak|driver|hardware|maintenance|manual\",\n"
            "      \"cta\": \"testo del pulsante consigliato (max 25 char)\",\n"
            "      \"priority\": 1\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Priorita' 1 = massima. Ordina per priorita' decrescente. Usa il contesto PC reale. Il campo "
            "'verify' e' SEMPRE obbligatorio e concreto (percorso o comando). Non ripetere azioni gia' "
            "applicate. Rispondi in italiano."
        )
        try:
            raw = await ai_engine.one_shot_advisor(prompt, specs_text=specs_text + extra_context, lang="it")
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
    async def generate_followups(session_id: str, user: dict = Depends(get_current_user)):
        """Genera 3 follow-up brevi dopo l'ultima risposta AI di una sessione."""
        uid = str(user["_id"])
        history = await db.chat_messages.find(
            {"session_id": session_id, "user_id": uid}, {"_id": 0}
        ).sort("created_at", 1).to_list(500)
        if not history:
            return {"suggestions": []}
        try:
            sug = await ai_engine.generate_followups(history, lang="it")
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
