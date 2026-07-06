import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

import ai_engine
from database import db, now_iso
from helpers import pc_context_text, compute_health
from models import ChatMessageInput


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

    return r
