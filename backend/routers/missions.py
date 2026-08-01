"""FrameForge Missions router — /api/missions/*"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Path

from database import db
from missions import get_state, activate, abandon


def build(get_current_user):
    r = APIRouter(prefix="/api/missions", tags=["missions"])

    @r.get("")
    async def missions_state(user: dict = Depends(get_current_user)):
        return await get_state(db, str(user["_id"]))

    @r.post("/activate/{code}")
    async def missions_activate(code: str = Path(...), user: dict = Depends(get_current_user)):
        res = await activate(db, str(user["_id"]), code)
        if not res.get("ok"):
            raise HTTPException(400, res.get("error", "cannot_activate"))
        return res

    @r.post("/abandon/{code}")
    async def missions_abandon(code: str = Path(...), user: dict = Depends(get_current_user)):
        res = await abandon(db, str(user["_id"]), code)
        if not res.get("ok"):
            raise HTTPException(400, res.get("error", "cannot_abandon"))
        return res

    return r
