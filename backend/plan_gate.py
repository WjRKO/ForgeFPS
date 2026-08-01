"""plan_gate.py — Piano SaaS: normalizzazione, controllo scadenza trial, feature gating.

Piani supportati (colonna `plan` in `users`):
    starter                 default gratuito
    pro                     abbonamento Pro attivo (pagante)
    pro_trial               trial Pro attivo (14gg, no carta)
    pro_expired             trial/paid Pro scaduto (30gg di grace con banner "riattiva")
    streamer                abbonamento Streamer attivo (pagante)
    streamer_trial          trial Streamer attivo (14gg)
    streamer_expired        trial/paid Streamer scaduto (30gg di grace)

Compat: valori legacy "free" e "creator" restano supportati come alias
(free -> starter, creator -> streamer).
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Depends

# --- Alias / normalizzazione ---------------------------------------------------
_LEGACY = {"free": "starter", "creator": "streamer"}

PRO_TIERS = {"pro", "pro_trial", "streamer", "streamer_trial"}
STREAMER_TIERS = {"streamer", "streamer_trial"}
TRIAL_TIERS = {"pro_trial", "streamer_trial"}
EXPIRED_TIERS = {"pro_expired", "streamer_expired"}

TRIAL_DAYS = 14
GRACE_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_plan(raw) -> str:
    """Mappa i valori legacy (free/creator) sui nuovi (starter/streamer)."""
    if not raw:
        return "starter"
    raw = str(raw).strip().lower()
    return _LEGACY.get(raw, raw)


def compute_effective_plan(user: dict) -> dict:
    """Calcola il piano *effettivo* dato lo stato dell'utente.

    Se `plan` e' un *_trial ma `trial_expires_at` e' passato, il piano
    effettivo diventa *_expired (grace period). Se anche il grace period e'
    passato, diventa starter.

    Ritorna dict:
        plan_stored:          quello nel DB (raw)
        plan_effective:       quello che vale ORA (starter/pro/streamer/pro_expired/...)
        trial_expires_at:     iso string o None
        trial_days_left:      int >= 0 (0 se scaduto)
        grace_days_left:      int >= 0 (30gg dopo trial scaduto)
        is_pro:               bool (accesso feature Pro)
        is_streamer:          bool (accesso feature Streamer)
        show_reactivate:      bool (banner riattiva Pro nel grace period)
    """
    stored = normalize_plan(user.get("plan"))
    now = _now()
    exp = _parse_iso(user.get("trial_expires_at"))

    effective = stored
    trial_days_left = 0
    grace_days_left = 0
    show_reactivate = False

    if stored in TRIAL_TIERS and exp:
        if exp > now:
            trial_days_left = max(0, (exp - now).days + (1 if (exp - now).seconds > 0 else 0))
        else:
            # Trial scaduto -> passa a *_expired (grace period)
            effective = "pro_expired" if stored == "pro_trial" else "streamer_expired"
            grace_end = exp + timedelta(days=GRACE_DAYS)
            if grace_end > now:
                grace_days_left = max(0, (grace_end - now).days + (1 if (grace_end - now).seconds > 0 else 0))
                show_reactivate = True
            else:
                # Grace terminata -> torna a starter
                effective = "starter"
                show_reactivate = False

    is_pro = effective in {"pro", "pro_trial", "streamer", "streamer_trial"}
    is_streamer = effective in {"streamer", "streamer_trial"}

    return {
        "plan_stored": stored,
        "plan_effective": effective,
        "trial_expires_at": user.get("trial_expires_at"),
        "trial_days_left": trial_days_left,
        "grace_days_left": grace_days_left,
        "is_pro": is_pro,
        "is_streamer": is_streamer,
        "show_reactivate": show_reactivate,
        "trial_used": bool(user.get("trial_used")),
    }


# --- FastAPI dependency helpers -----------------------------------------------
def require_pro(get_current_user):
    """Ritorna una dependency che accetta solo utenti Pro / Streamer / trial attivi.

    Uso in un router:
        require_pro_dep = require_pro(get_current_user)
        @r.get("/foo")
        async def foo(user: dict = Depends(require_pro_dep)):
            ...
    """
    async def dep(user: dict = Depends(get_current_user)):
        info = compute_effective_plan(user)
        if not info["is_pro"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "plan_required",
                    "required": "pro",
                    "current": info["plan_effective"],
                    "message": "Questa feature richiede il piano Pro o superiore.",
                    "upgrade_url": "/pricing",
                },
            )
        return {**user, "_plan_info": info}
    return dep


def require_streamer(get_current_user):
    """Solo utenti Streamer / streamer_trial attivi."""
    async def dep(user: dict = Depends(get_current_user)):
        info = compute_effective_plan(user)
        if not info["is_streamer"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "plan_required",
                    "required": "streamer",
                    "current": info["plan_effective"],
                    "message": "Questa feature richiede il piano Streamer.",
                    "upgrade_url": "/pricing",
                },
            )
        return {**user, "_plan_info": info}
    return dep


# --- Entitlements (piano + feature Earned Premium sbloccate via trofei) --------
def plan_402(required: str, current: str, message: str, code: str = "plan_required") -> HTTPException:
    return HTTPException(status_code=402, detail={
        "code": code, "required": required, "current": current,
        "message": message, "upgrade_url": "/pricing",
    })


async def get_entitlements(db, user: dict) -> dict:
    """Piano effettivo + feature flags: incluse nel piano O guadagnate coi trofei."""
    info = compute_effective_plan(user)
    prog = await db.user_progress.find_one({"user_id": str(user["_id"])}, {"features": 1})
    feats = (prog or {}).get("features") or {}
    is_pro = info["is_pro"]
    info["entitlements"] = {
        "adv_tweaks": is_pro or bool(feats.get("adv_tweaks") or feats.get("advanced_registry_tweaks")),
        "history_90d": is_pro or bool(feats.get("history_90d")),
        "pdf_report": is_pro or bool(feats.get("pdf_report")),
        "gpu_reference_full": is_pro or bool(feats.get("gpu_reference_full")),
        "full_benchmark": is_pro,
        "tracker_limit": 25 if is_pro else 3,
        "device_limit": 99 if info["is_streamer"] else (3 if is_pro else 1),
    }
    return info
