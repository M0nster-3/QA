"""
认证服务：用户名即身份，无需密码。

输入用户名 → 存在则登录，不存在则自动创建。
JWT 签发/验证照旧。
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from .database import get_db, now_iso

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = "<JWT_SECRET_KEY>"
ALGORITHM = "HS256"
EXPIRE_DAYS = 36500       # ~100 年，无密码模式长期有效

security = HTTPBearer()

# ── 简易 IP 级频率限制 ──────────────────────────────────────
_rate_limit: dict[str, list[float]] = {}  # ip → [timestamp, ...]
_RATE_LIMIT = 10   # 每个 IP 每分钟最多 10 次登录
_RATE_WINDOW = 60  # 窗口 60 秒


def _check_rate_limit(ip: str) -> bool:
    """检查是否在频率限制内。返回 True 表示允许。"""
    import time
    now = time.time()
    records = _rate_limit.get(ip, [])
    records = [t for t in records if now - t < _RATE_WINDOW]
    _rate_limit[ip] = records
    if len(records) >= _RATE_LIMIT:
        return False
    records.append(now)
    return True


class LoginRequest(BaseModel):
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    is_new: bool = False


def create_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=EXPIRE_DAYS)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        username = payload.get("username")
        if user_id is None or username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request):
    """用户名登录：已存在直接登，不存在自动创建。"""
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    # 频率限制
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait.")

    db = get_db()
    try:
        row = db.execute(
            "SELECT user_id, username FROM users WHERE username = ?", (username,)
        ).fetchone()

        if row is None:
            # 新用户 → 自动创建
            db.execute(
                "INSERT INTO users (username, created_at) VALUES (?, ?)",
                (username, now_iso()),
            )
            db.commit()
            user_id = db.execute(
                "SELECT user_id FROM users WHERE username = ?", (username,)
            ).fetchone()["user_id"]
            is_new = True
        else:
            user_id = row["user_id"]
            is_new = False

        token = create_token(user_id, username)
        return TokenResponse(
            access_token=token, user_id=user_id, username=username, is_new=is_new
        )
    finally:
        db.close()


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"user_id": user["user_id"], "username": user["username"]}
