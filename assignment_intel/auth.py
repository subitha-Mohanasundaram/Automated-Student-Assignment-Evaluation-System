from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt


def hash_password(password: str) -> str:
    pw = (password or "").encode("utf-8")
    if len(pw) < 8:
        raise ValueError("password_too_short")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw((password or "").encode("utf-8"), (password_hash or "").encode("utf-8"))
    except Exception:
        return False


def _jwt_secret() -> str:
    # In production, set JWT_SECRET to a long random string.
    return os.environ.get("JWT_SECRET", "dev-secret-change-me")


def issue_session_token(*, user_id: int, username: str, role: str, ttl_hours: int = 24 * 7) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(int(user_id)),
        "username": str(username),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=int(ttl_hours))).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_session_token(token: str) -> dict[str, Any]:
    obj = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    if not isinstance(obj, dict):
        raise ValueError("invalid_token")
    return obj

