import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    async def advisor_chat(data: ChatMessageInput, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        await _check_ai_rate_limit(uid)
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

        async def gen():
            yield f"__SESSION__{session_id}__\n"
            full = ""
            try:
                async for chunk in ai_engine.stream_advisor(session_id, history, data.message, specs_text, data.lang or "it"):
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
            "      \"impact\": \"stima misurabile (es. '+5-10% FPS', '-10 ms latency', '-5\\u00b0C GPU')\",\n"
            "      \"difficulty\": \"facile|medio|avanzato\",\n"
            "      \"kind\": \"tweak|driver|hardware|maintenance|manual\",\n"
            "      \"cta\": \"testo del pulsante consigliato (max 25 char)\",\n"
            "      \"priority\": 1\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Priorita' 1 = massima. Ordina per priorita' decrescente. Usa il contesto PC reale (health checks, "
            "trend benchmark, temperature) per personalizzare al massimo. Non ripetere azioni gia' evidentemente "
            "applicate dall'utente. Rispondi in italiano se il contesto e' italiano."
        )
        try:
            raw = await ai_engine.one_shot_advisor(prompt, specs_text=specs_text, lang="it")
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

    return r
