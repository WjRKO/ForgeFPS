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
    async def suggestions(user: dict = Depends(get_current_user)):
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
        return {"suggestions": out[:4], "personalized": bool(health)}


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
                async for chunk in ai_engine.stream_advisor(session_id, history, data.message, specs_text):
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
