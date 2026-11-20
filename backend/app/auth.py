import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import jwt
from .core.config import settings
from .models.sqlalchemy_models import RoleEnum

# Password hashing using PBKDF2-HMAC-SHA256 (safe, zero external binary dependency)
def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return f"pbkdf2:sha256:100000${salt}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if not hashed_password.startswith("pbkdf2:sha256:"):
            # Fallback for plain bcrypt or other legacy hashes if needed
            return False
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        header, salt, stored_hash = parts
        iterations = int(header.split(":")[-1])
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=iterations,
        )
        return hmac.compare_digest(key.hex(), stored_hash)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except Exception:
        return None
