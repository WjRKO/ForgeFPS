import os
import logging
import jwt
import bcrypt
import secrets
import pyotp
import qrcode
import io
import base64
from argon2 import PasswordHasher
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId

_ph = PasswordHasher()

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 15
REFRESH_DAYS = 7
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
COOKIE_SECURE = os.environ.get("FRONTEND_URL", "").startswith("https")


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        if hashed.startswith("$argon2"):
            _ph.verify(hashed, plain)
            return True
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    return not hashed.startswith("$argon2")


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_MINUTES),
               "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id,
               "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS),
               "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=COOKIE_SECURE,
                        samesite="lax", max_age=ACCESS_MINUTES * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=COOKIE_SECURE,
                        samesite="lax", max_age=REFRESH_DAYS * 86400, path="/")


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)


class LoginInput(BaseModel):
    email: EmailStr
    password: str
    code: str | None = Field(default=None, max_length=16)


class MfaCodeInput(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class ForgotInput(BaseModel):
    email: EmailStr


class ResetInput(BaseModel):
    token: str
    password: str = Field(min_length=6)


class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UpdateProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PreferencesInput(BaseModel):
    local_only: bool = False
    email_alerts: bool = False
    language: str = Field(default="it", max_length=5)


class DeleteAccountInput(BaseModel):
    password: str


def public_user(user: dict) -> dict:
    return {"id": str(user["_id"]), "email": user["email"],
            "name": user.get("name", ""), "role": user.get("role", "user"),
            "mfa_enabled": bool(user.get("mfa_enabled"))}


def _parse_device_label(ua: str) -> str:
    """Parse a short human-readable device label from a User-Agent string.
    Used for the cross-device magic-link scan notification (never exposes IP)."""
    if not ua:
        return "Dispositivo sconosciuto"
    s = ua.lower()
    if "iphone" in s: return "iPhone"
    if "ipad" in s: return "iPad"
    if "android" in s:
        if "tablet" in s: return "Tablet Android"
        return "Android"
    if "windows" in s: return "Windows"
    if "mac os" in s or "macintosh" in s: return "Mac"
    if "linux" in s: return "Linux"
    return "Dispositivo sconosciuto"


def _verify_mfa(user: dict, code: str) -> bool:
    if not code:
        return False
    code = code.strip().replace(" ", "")
    secret = user.get("mfa_secret")
    if secret and pyotp.TOTP(secret).verify(code, valid_window=1):
        return True
    for rc in user.get("mfa_recovery", []):
        if verify_password(code, rc):
            return True
    return False


async def _enforce_login_lockout(db, identifier: str):
    """Raise 429 if this identifier is currently locked out."""
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= MAX_ATTEMPTS:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    return attempt


async def _record_failed_login(db, identifier: str, previous_attempt: dict | None):
    """Increment failure counter for this identifier; apply lockout if threshold reached."""
    new_count = (previous_attempt.get("count", 0) if previous_attempt else 0) + 1
    update = {"count": new_count}
    if new_count >= MAX_ATTEMPTS:
        update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)


async def _consume_mfa_recovery_code(db, user: dict, code: str):
    """Remove any matching recovery code from the user's recovery list (idempotent)."""
    matches = [rc for rc in user.get("mfa_recovery", []) if verify_password(code.strip(), rc)]
    if matches:
        await db.users.update_one({"_id": user["_id"]}, {"$pull": {"mfa_recovery": {"$in": matches}}})


def build_auth_router(db):
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    async def get_current_user(request: Request) -> dict:
        token = request.cookies.get("access_token")
        if not token:
            header = request.headers.get("Authorization", "")
            if header.startswith("Bearer "):
                token = header[7:]
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")
            user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    @router.post("/register")
    async def register(data: RegisterInput, response: Response):
        email = data.email.lower()
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        doc = {"email": email, "password_hash": hash_password(data.password),
               "name": data.name, "role": "user",
               "created_at": datetime.now(timezone.utc).isoformat()}
        res = await db.users.insert_one(doc)
        uid = str(res.inserted_id)
        set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
        doc["_id"] = res.inserted_id
        return public_user(doc)

    @router.post("/login")
    async def login(data: LoginInput, request: Request, response: Response):
        email = data.email.lower()
        # Preferisci X-Forwarded-For (dietro ingress/reverse-proxy) per non contare
        # ogni replica come utente diverso e permettere il brute-force lockout.
        xff = request.headers.get("x-forwarded-for", "")
        ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
        identifier = f"{ip}:{email}"
        previous_attempt = await _enforce_login_lockout(db, identifier)
        user = await db.users.find_one({"email": email})
        if not user or not verify_password(data.password, user["password_hash"]):
            await _record_failed_login(db, identifier, previous_attempt)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        await db.login_attempts.delete_one({"identifier": identifier})
        uid = str(user["_id"])
        if user.get("mfa_enabled"):
            if not _verify_mfa(user, data.code or ""):
                return {"mfa_required": True}
            await _consume_mfa_recovery_code(db, user, data.code or "")
        if needs_rehash(user["password_hash"]):
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(data.password)}})
        set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
        return public_user(user)

    @router.post("/logout")
    async def logout(response: Response, user: dict = Depends(get_current_user)):
        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")
        return {"ok": True}

    @router.get("/me")
    async def me(user: dict = Depends(get_current_user)):
        return public_user(user)

    # Magic-link ('Continue on mobile') endpoints — extracted to auth_magic.py
    from auth_magic import register_magic_routes
    register_magic_routes(
        router, db, get_current_user, set_auth_cookies,
        create_access_token, create_refresh_token,
        public_user, _parse_device_label,
    )

    @router.post("/refresh")
    async def refresh(request: Request, response: Response):
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(status_code=401, detail="No refresh token")
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")
            user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            access = create_access_token(str(user["_id"]), user["email"])
            set_auth_cookies(response, access, create_refresh_token(str(user["_id"])))
            return {"ok": True}
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    @router.post("/forgot-password")
    async def forgot(data: ForgotInput, request: Request):
        user = await db.users.find_one({"email": data.email.lower()})
        if user:
            token = secrets.token_urlsafe(32)
            # Salva token con metadati denormalizzati per il pannello admin
            # (finché non integriamo email vera via Resend: /api/admin/password-resets
            # permette all'admin di consegnare il link a mano all'utente).
            await db.password_reset_tokens.insert_one({
                "token": token,
                "user_id": str(user["_id"]),
                "email": data.email.lower(),
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "used": False,
                "used_at": None,
                "ip": (request.client.host if request.client else None) if request else None,
            })
            print(f"[PASSWORD RESET] Link: /reset-password?token={token}")
        return {"ok": True, "message": "If the email exists, a reset link was sent."}

    @router.post("/reset-password")
    async def reset(data: ResetInput):
        rec = await db.password_reset_tokens.find_one({"token": data.token})
        if not rec or rec.get("used"):
            raise HTTPException(status_code=400, detail="Invalid or used token")
        exp = rec["expires_at"]
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Token expired")
        await db.users.update_one({"_id": ObjectId(rec["user_id"])},
                                  {"$set": {"password_hash": hash_password(data.password)}})
        await db.password_reset_tokens.update_one(
            {"token": data.token},
            {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}})
        return {"ok": True}

    @router.get("/preferences")
    async def get_preferences(user: dict = Depends(get_current_user)):
        p = user.get("preferences") or {}
        return {"local_only": p.get("local_only", False),
                "email_alerts": p.get("email_alerts", False),
                "language": p.get("language", "it")}

    @router.put("/preferences")
    async def set_preferences(data: PreferencesInput, user: dict = Depends(get_current_user)):
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"preferences": data.model_dump()}})
        return {"ok": True, **data.model_dump()}

    @router.patch("/profile")
    async def update_profile(data: UpdateProfileInput, user: dict = Depends(get_current_user)):
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"name": data.name}})
        updated = await db.users.find_one({"_id": user["_id"]})
        return public_user(updated)

    @router.post("/change-password")
    async def change_password(data: ChangePasswordInput, response: Response, user: dict = Depends(get_current_user)):
        if not verify_password(data.current_password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Password attuale non corretta")
        if data.new_password == data.current_password:
            raise HTTPException(status_code=400, detail="La nuova password deve essere diversa da quella attuale")
        await db.users.update_one({"_id": user["_id"]},
                                  {"$set": {"password_hash": hash_password(data.new_password)}})
        uid = str(user["_id"])
        set_auth_cookies(response, create_access_token(uid, user["email"]), create_refresh_token(uid))
        return {"ok": True}

    @router.post("/delete-account")
    async def delete_account(data: DeleteAccountInput, response: Response, user: dict = Depends(get_current_user)):
        if user.get("role") == "admin":
            raise HTTPException(status_code=400, detail="Gli account admin non possono essere eliminati da qui")
        if not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Password non corretta")
        uid = str(user["_id"])
        await db.users.delete_one({"_id": user["_id"]})
        for coll in ("products", "price_history", "builds", "chat_sessions", "chat_messages",
                     "notifications", "pc_specs", "agent_tokens", "push_subscriptions"):
            await db[coll].delete_many({"user_id": uid})
        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")
        return {"ok": True}

    # MFA (TOTP) endpoints — extracted to auth_mfa.py
    from auth_mfa import register_mfa_routes
    register_mfa_routes(router, db, get_current_user, MfaCodeInput, hash_password, _verify_mfa)

    return router, get_current_user


async def seed_admin(db):
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        logging.warning("ADMIN_EMAIL/ADMIN_PASSWORD not set; skipping admin seed")
        return
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({"email": email, "password_hash": hash_password(password),
                                   "name": "Admin", "role": "admin",
                                   "created_at": datetime.now(timezone.utc).isoformat()})
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
