"""MFA (TOTP) sub-routes extracted from auth.py to keep build_auth_router lean.
Provides: /mfa/status, /mfa/setup, /mfa/enable, /mfa/disable.
Contract identical to previous inline definitions (same paths, payloads, responses).
"""
import base64
import io
import secrets

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException


def register_mfa_routes(router: APIRouter, db, get_current_user, MfaCodeInput, hash_password, verify_mfa):
    """Attach MFA endpoints to the given router. All handlers use the shared
    get_current_user dependency built by auth.build_auth_router()."""

    @router.get("/mfa/status")
    async def mfa_status(user: dict = Depends(get_current_user)):
        return {"enabled": bool(user.get("mfa_enabled"))}

    @router.post("/mfa/setup")
    async def mfa_setup(user: dict = Depends(get_current_user)):
        secret = pyotp.random_base32()
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"mfa_pending": secret}})
        uri = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="FrameForge")
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_data = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        return {"secret": secret, "otpauth_uri": uri, "qr": qr_data}

    @router.post("/mfa/enable")
    async def mfa_enable(data: MfaCodeInput, user: dict = Depends(get_current_user)):
        secret = user.get("mfa_pending")
        if not secret:
            raise HTTPException(status_code=400, detail="Avvia prima la configurazione MFA")
        if not pyotp.TOTP(secret).verify(data.code.strip().replace(" ", ""), valid_window=1):
            raise HTTPException(status_code=400, detail="Codice non valido")
        recovery = [secrets.token_hex(4) for _ in range(10)]
        await db.users.update_one({"_id": user["_id"]}, {
            "$set": {"mfa_enabled": True, "mfa_secret": secret,
                     "mfa_recovery": [hash_password(r) for r in recovery]},
            "$unset": {"mfa_pending": ""}})
        return {"ok": True, "recovery_codes": recovery}

    @router.post("/mfa/disable")
    async def mfa_disable(data: MfaCodeInput, user: dict = Depends(get_current_user)):
        if not user.get("mfa_enabled"):
            return {"ok": True}
        if not verify_mfa(user, data.code):
            raise HTTPException(status_code=400, detail="Codice non valido")
        await db.users.update_one({"_id": user["_id"]},
                                  {"$unset": {"mfa_enabled": "", "mfa_secret": "",
                                              "mfa_recovery": "", "mfa_pending": ""}})
        return {"ok": True}
