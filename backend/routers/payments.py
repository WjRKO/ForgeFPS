"""payments.py — Stripe checkout + webhook + status polling (Flow A sandbox).

Endpoints:
    POST /api/payments/checkout        crea sessione Stripe Checkout, ritorna URL
    GET  /api/payments/status/{sid}    stato sessione (usato dal frontend per polling)
    POST /api/stripe/webhook           riceve eventi Stripe (checkout.completed ecc.)

Al completamento del pagamento:
    - users.plan = "pro" | "streamer"
    - users.trial_expires_at = None (piano paid, no scadenza — gestito da Stripe)
    - users.stripe_subscription_id salvato
"""
import os
import stripe
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from bson import ObjectId

from database import db

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Mappa lookup_key Stripe -> piano interno FrameForge
LOOKUP_TO_PLAN = {
    "pro_monthly": "pro", "pro_yearly": "pro",
    "streamer_monthly": "streamer", "streamer_yearly": "streamer",
}


class CheckoutRequest(BaseModel):
    lookup_key: str
    origin_url: str
    quantity: int = Field(1, ge=1, le=1)


def build(get_current_user):
    r = APIRouter(prefix="/api", tags=["payments"])

    @r.post("/payments/checkout")
    async def create_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)):
        if req.lookup_key not in LOOKUP_TO_PLAN:
            raise HTTPException(status_code=400, detail="lookup_key non valida")
        prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
        if not prices:
            raise HTTPException(status_code=500, detail=f"Price non trovato: {req.lookup_key}")
        price = prices[0]
        uid = str(user["_id"])

        # Se l'utente ha gia' un customer Stripe salvato, riusalo
        existing_customer = user.get("stripe_customer_id")
        if not existing_customer:
            cust = stripe.Customer.create(email=user["email"], name=user.get("name", ""), metadata={"user_id": uid})
            existing_customer = cust.id
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"stripe_customer_id": existing_customer}})

        kwargs = dict(
            customer=existing_customer,
            line_items=[{"price": price.id, "quantity": req.quantity}],
            mode="subscription" if price.recurring else "payment",
            success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{req.origin_url}/pricing",
            metadata={"user_id": uid, "lookup_key": req.lookup_key},
        )
        # Country=IT + SaaS -> tax_mode="full" (Stripe SMP)
        try:
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or "").lower()
            if "managed payments" in msg or "ineligible" in msg:
                session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True},
                                                          billing_address_collection="required")
            else:
                raise

        now = datetime.now(timezone.utc)
        await db.payment_transactions.insert_one({
            "session_id": session.id, "user_id": uid, "lookup_key": req.lookup_key,
            "amount": (price.unit_amount or 0), "currency": price.currency,
            "status": "initiated", "payment_status": "pending",
            "created_at": now, "updated_at": now,
        })
        return {"checkout_url": session.url, "session_id": session.id}

    @r.get("/payments/status/{session_id}")
    async def get_status(session_id: str):
        record = await db.payment_transactions.find_one({"session_id": session_id})
        if not record:
            raise HTTPException(404, "Transazione non trovata")
        if record.get("payment_status") != "paid":
            # Fallback webhook: interroga Stripe direttamente in caso di webhook ritardato
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await _apply_paid(session_id, s)
                    record = await db.payment_transactions.find_one({"session_id": session_id})
            except stripe.error.StripeError:
                pass
        return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}

    @r.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Signature invalida")
        obj, t = event["data"]["object"], event["type"]
        now = datetime.now(timezone.utc)

        if t == "checkout.session.completed":
            await _apply_paid(obj["id"], obj)
        elif t == "checkout.session.async_payment_succeeded":
            await db.payment_transactions.update_one({"session_id": obj["id"]},
                {"$set": {"payment_status": "paid", "updated_at": now}})
        elif t == "checkout.session.async_payment_failed":
            await db.payment_transactions.update_one({"session_id": obj["id"]},
                {"$set": {"status": "failed", "payment_status": "failed", "updated_at": now}})
        elif t == "customer.subscription.deleted":
            # Subscription cancellata (dal customer portal o Stripe). Downgrade a starter.
            sub_id = obj["id"]
            user_doc = await db.users.find_one({"stripe_subscription_id": sub_id})
            if user_doc:
                await db.users.update_one({"_id": user_doc["_id"]}, {"$set": {
                    "plan": "starter", "plan_updated_at": now.isoformat(),
                    "trial_expires_at": None, "stripe_subscription_id": None,
                }})
        elif t == "invoice.payment_failed":
            # Pagamento fallito su rinnovo: manteniamo il piano ma segnaliamo un flag
            cust = obj.get("customer")
            if cust:
                await db.users.update_one({"stripe_customer_id": cust},
                    {"$set": {"payment_failed_at": now.isoformat()}})
                # Fire-and-forget email payment_failed
                try:
                    import asyncio as _aio
                    from email_service import send_payment_failed
                    user_doc = await db.users.find_one({"stripe_customer_id": cust})
                    if user_doc:
                        _aio.create_task(send_payment_failed(
                            user_doc["email"], user_doc.get("name", ""),
                            (user_doc.get("plan") or "pro"),
                        ))
                except Exception:
                    pass

        return {"status": "ok"}

    @r.post("/payments/portal")
    async def create_portal(user: dict = Depends(get_current_user)):
        """Genera link al Stripe Customer Portal per l'utente corrente.
        Nel portal l'utente puo': aggiungere/cambiare carta, vedere fatture,
        cancellare o cambiare piano.
        """
        customer_id = user.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=400, detail={
                "code": "no_customer",
                "message": "Nessun metodo di pagamento associato. Sottoscrivi un piano prima.",
            })
        origin = "https://forgefps.dev"
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{origin}/app/billing",
            )
            return {"portal_url": session.url}
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    return r


async def _apply_paid(session_id: str, session_obj):
    """Marca la transazione come paid + upgrade dell'utente sul piano corretto."""
    now = datetime.now(timezone.utc)
    result = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {
            "status": "completed",
            "payment_status": session_obj.get("payment_status") or "paid",
            "stripe_subscription_id": session_obj.get("subscription"),
            "stripe_payment_intent_id": session_obj.get("payment_intent"),
            "updated_at": now,
        }},
    )
    if result.modified_count == 0:
        return  # idempotency: gia' processato
    # Retrieve the transaction to get user_id + lookup_key
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        return
    user_id = tx.get("user_id")
    plan = LOOKUP_TO_PLAN.get(tx.get("lookup_key"))
    if not user_id or not plan:
        return
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {
        "plan": plan,
        "plan_updated_at": now.isoformat(),
        "trial_expires_at": None,  # paid, no scadenza (gestita da Stripe)
        "stripe_subscription_id": session_obj.get("subscription"),
        "payment_failed_at": None,
    }})
    # Fire-and-forget email payment_success
    try:
        import asyncio as _aio
        from email_service import send_payment_success
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            _aio.create_task(send_payment_success(
                user_doc["email"], user_doc.get("name", ""), plan,
                tx.get("amount", 0), tx.get("currency", "eur"),
            ))
    except Exception:
        pass
