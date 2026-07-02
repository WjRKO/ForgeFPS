import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

import ai_engine
from database import db, now_iso
from helpers import specs_to_text
from models import ChatMessageInput


def build(get_current_user):
    r = APIRouter(prefix="/api/advisor", tags=["advisor"])

    @r.get("/sessions")
    async def list_sessions(user: dict = Depends(get_current_user)):
        return await db.chat_sessions.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("updated_at", -1).to_list(100)

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
        specs_text = specs_to_text(specs)

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
