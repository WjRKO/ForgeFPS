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


class StartTrialInput(BaseModel):
    plan: str  # "pro_trial" | "streamer_trial"


def build(get_current_user):
    r = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

    @r.get("/status")
    async def status(user: dict = Depends(get_current_user)):
        """Piano corrente + trial info per il frontend (banner, feature-gating UI)."""
        return compute_effective_plan(user)

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
