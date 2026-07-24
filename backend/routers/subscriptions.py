"""subscriptions.py — Gestione piani SaaS FrameForge.

Endpoint:
    GET  /api/subscriptions/status           lo stato piano dell'utente corrente
    POST /api/subscriptions/start-trial      attiva 14gg trial Pro/Streamer (una volta per utente)
    POST /api/subscriptions/cancel-trial     downgrade immediato a starter (opzionale)

Stripe integration NON e' ancora agganciato — l'upgrade a `pro` paid
avverra' quando integriamo il checkout webhook. Per ora esiste solo il trial.
"""
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import db
from plan_gate import compute_effective_plan, TRIAL_DAYS


# --- Upgrade suggestion (engagement-driven) ----------------------------------
# Prezzi (in EUR, IVA-inclusa) — vedi PRICING_COPY_v2.md
_PRICE_BOOK = {
    "pro": {"monthly": 7, "yearly": 70, "save": 14},
    "streamer": {"monthly": 16, "yearly": 160, "save": 32},
}


async def compute_upgrade_suggestion(user: dict, info: dict):
    """Suggerisce il miglior piano/ciclo di fatturazione per convertire il trial.

    Regole:
      - Piani `pro`/`streamer` gia' attivi -> None (nessuna suggestione)
      - `starter` senza mai aver provato trial -> None (mostrato altrove come banner trial)
      - `pro_trial`/`streamer_trial` -> engagement score decide monthly vs yearly
      - `pro_expired`/`streamer_expired` -> yearly (riattivazione = commitment)
    """
    eff = info["plan_effective"]
    if eff in ("pro", "streamer"):
        return None
    if eff not in ("pro_trial", "streamer_trial", "pro_expired", "streamer_expired"):
        return None

    tier = "streamer" if eff.startswith("streamer") else "pro"
    uid = str(user["_id"])
    since_iso = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

    # Engagement signals ultimi 14gg
    ai_count = await db.chat_messages.count_documents({"user_id": uid, "created_at": {"$gte": since_iso}})
    health_count = await db.health_history.count_documents({"user_id": uid, "timestamp": {"$gte": since_iso}})
    telem_count = await db.pc_telemetry.count_documents({"user_id": uid})

    score = (ai_count * 2) + health_count + min(telem_count, 20)
    is_expired = eff.endswith("_expired")

    if is_expired or score >= 15:
        recommended = "yearly"
        reason = (
            "Riattiva risparmiando 2 mesi con l'annuale."
            if is_expired else
            "Sei un power user — l'annuale ti fa risparmiare 2 mesi."
        )
    else:
        recommended = "monthly"
        reason = f"Continua da dove hai lasciato — €{_PRICE_BOOK[tier]['monthly']}/mese, cancelli quando vuoi."

    prices = _PRICE_BOOK[tier]
    return {
        "tier": tier,
        "tier_label": tier.capitalize(),
        "lookup_monthly": f"{tier}_monthly",
        "lookup_yearly": f"{tier}_yearly",
        "recommended_cycle": recommended,
        "recommended_lookup": f"{tier}_{recommended}",
        "monthly_price": prices["monthly"],
        "yearly_price": prices["yearly"],
        "save_amount": prices["save"],
        "reason": reason,
        "engagement_score": score,
    }


class StartTrialInput(BaseModel):
    plan: str  # "pro_trial" | "streamer_trial"


def build(get_current_user):
    r = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

    @r.get("/status")
    async def status(user: dict = Depends(get_current_user)):
        """Piano corrente + trial info + suggestione upgrade personalizzata."""
        info = compute_effective_plan(user)
        suggestion = await compute_upgrade_suggestion(user, info)
        return {**info, "suggested_upgrade": suggestion}

    @r.post("/start-trial")
    async def start_trial(payload: StartTrialInput, user: dict = Depends(get_current_user)):
        """Attiva 14gg trial Pro o Streamer.

        Regole:
        - Un utente puo' fare il trial UNA sola volta per tier.
        - Se ha gia' un trial attivo o un piano pagato, ritorna 400.
        - Se il suo trial e' gia' scaduto (grace period o oltre), niente rifare.

        Body: {"plan": "pro_trial" | "streamer_trial"}
        """
        wanted = (payload.plan or "").strip().lower()
        if wanted not in ("pro_trial", "streamer_trial"):
            raise HTTPException(status_code=400, detail="Plan non supportato per trial")

        info = compute_effective_plan(user)
        # Rifiuto: gia' su piano attivo o gia' usato il trial
        if info["is_pro"]:
            raise HTTPException(status_code=400, detail={
                "code": "already_on_plan",
                "message": f"Hai gia' un piano {info['plan_effective']} attivo.",
                "current": info["plan_effective"],
            })
        if info["trial_used"]:
            raise HTTPException(status_code=400, detail={
                "code": "trial_already_used",
                "message": "Hai gia' utilizzato il periodo di prova gratuito.",
            })

        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=TRIAL_DAYS)

        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "plan": wanted,
                "trial_started_at": now.isoformat(),
                "trial_expires_at": expires.isoformat(),
                "trial_used": True,
                "plan_updated_at": now.isoformat(),
            }},
        )

        # Rileggo per la risposta
        u2 = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
        return {
            "ok": True,
            "message": f"Trial {wanted} attivato! Hai {TRIAL_DAYS} giorni pieni di accesso.",
            **compute_effective_plan(u2),
        }

    @r.post("/cancel-trial")
    async def cancel_trial(user: dict = Depends(get_current_user)):
        """Downgrade immediato a starter (utente decide di uscire dal trial in anticipo).

        Effetto: azzeriamo il trial e mettiamo piano=starter. `trial_used` resta
        True per prevenire abusi (niente doppio-trial cambiando idea).
        """
        info = compute_effective_plan(user)
        if info["plan_stored"] not in ("pro_trial", "streamer_trial"):
            raise HTTPException(status_code=400, detail="Non hai un trial attivo da cancellare")

        now = datetime.now(timezone.utc)
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "plan": "starter",
                "trial_expires_at": now.isoformat(),  # scaduto ORA
                "plan_updated_at": now.isoformat(),
            }},
        )
        u2 = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
        return {"ok": True, "message": "Trial cancellato. Sei tornato al piano Starter.", **compute_effective_plan(u2)}

    return r
