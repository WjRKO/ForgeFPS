"""FrameForge Dashboard router — GET /api/dashboard.

La home dell'app faceva 8 richieste in parallelo per disegnare un solo schermo,
e due di quelle erano fra gli endpoint piu' cari dell'API: /pc-specs annota
tutta la lista di programmi all'avvio e /pc-health scorre l'intera collezione
pc_specs per calcolare un percentile di flotta che la dashboard non mostra
nemmeno. Qui si legge lo stesso documento pc_specs una volta sola e si tiene
solo quello che la pagina disegna davvero.

Le forme dei campi restano identiche a quelle dei singoli endpoint, che
continuano a esistere per le pagine di dettaglio.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from database import db
from helpers import compute_health
from devices import device_filter
from missions import get_state


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["dashboard"])

    @r.get("/dashboard")
    async def dashboard(user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        dev = await device_filter(db, uid)

        # Un solo documento copre specs + health + benchmark.
        pc = await db.pc_specs.find_one(dev, {"_id": 0, "data": 1, "health": 1,
                                              "benchmark": 1, "updated_at": 1}) or {}

        health = {"available": False}
        if pc.get("health"):
            health = {**compute_health(pc["health"]), "available": True}

        prices = await db.products.find(
            {"user_id": uid}, {"_id": 0, "initial_price": 1, "current_price": 1}).to_list(500)
        saved = sum(p["initial_price"] - p["current_price"] for p in prices
                    if p.get("initial_price") and p.get("current_price")
                    and p["current_price"] < p["initial_price"])

        udoc = await db.users.find_one(
            {"_id": user["_id"]},
            {"discord_user_id": 1, "discord_username": 1, "discord_avatar": 1}) or {}

        return {
            "stats": {
                "tracked_products": len(prices),
                "builds": await db.builds.count_documents({"user_id": uid}),
                "chat_sessions": await db.chat_sessions.count_documents({"user_id": uid}),
                "unread_notifications": await db.notifications.count_documents(
                    {"user_id": uid, "read": False}),
                "total_saved": round(saved, 2),
            },
            "products": await db.products.find({"user_id": uid}, {"_id": 0})
                                         .sort("created_at", -1).to_list(5),
            "specs": {"data": pc.get("data"), "updated_at": pc.get("updated_at")},
            "health": health,
            "benchmark": {
                "latest": pc.get("benchmark"),
                "history": await db.benchmarks.find({"user_id": uid}, {"_id": 0})
                                              .sort("created_at", -1).to_list(10),
            },
            "discord": {
                "linked": bool(udoc.get("discord_user_id")),
                "user_id": udoc.get("discord_user_id"),
                "username": udoc.get("discord_username", ""),
                "avatar": udoc.get("discord_avatar", ""),
            },
            "notifications": await db.notifications.find({"user_id": uid}, {"_id": 0})
                                                   .sort("created_at", -1).to_list(100),
            "missions": await get_state(db, uid),
        }

    return r
