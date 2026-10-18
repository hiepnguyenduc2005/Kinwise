import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.errors import AppError

_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = _hasher.hash("kinwise-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def verify_password_dummy(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def new_invitation_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def new_numeric_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *,
    user_id: str,
    role: str,
    session_id: str,
    secret: str,
    minutes: int,
) -> str:
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "sid": session_id,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "sid", "typ", "role"]},
            leeway=15,
        )
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Sign in again to continue.") from exc
    if payload.get("typ") != "access":
        raise AppError(401, "invalid_token", "Sign in again to continue.")
    return payload
