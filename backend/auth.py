import os
import logging
import jwt
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 15
REFRESH_DAYS = 7
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
COOKIE_SECURE = os.environ.get("FRONTEND_URL", "").startswith("https")


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


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


class ForgotInput(BaseModel):
    email: EmailStr


class ResetInput(BaseModel):
    token: str
    password: str = Field(min_length=6)


def public_user(user: dict) -> dict:
    return {"id": str(user["_id"]), "email": user["email"],
            "name": user.get("name", ""), "role": user.get("role", "user")}


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
        ip = request.client.host if request.client else "unknown"
        identifier = f"{ip}:{email}"
        attempt = await db.login_attempts.find_one({"identifier": identifier})
        if attempt and attempt.get("count", 0) >= MAX_ATTEMPTS:
            locked_until = attempt.get("locked_until")
            if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
                raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        user = await db.users.find_one({"email": email})
        if not user or not verify_password(data.password, user["password_hash"]):
            new_count = (attempt.get("count", 0) if attempt else 0) + 1
            update = {"count": new_count}
            if new_count >= MAX_ATTEMPTS:
                update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        await db.login_attempts.delete_one({"identifier": identifier})
        uid = str(user["_id"])
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
            response.set_cookie("access_token", access, httponly=True, secure=COOKIE_SECURE,
                                samesite="lax", max_age=ACCESS_MINUTES * 60, path="/")
            return {"ok": True}
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    @router.post("/forgot-password")
    async def forgot(data: ForgotInput):
        user = await db.users.find_one({"email": data.email.lower()})
        if user:
            token = secrets.token_urlsafe(32)
            await db.password_reset_tokens.insert_one({
                "token": token, "user_id": str(user["_id"]),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "used": False})
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
        await db.password_reset_tokens.update_one({"token": data.token}, {"$set": {"used": True}})
        return {"ok": True}

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
