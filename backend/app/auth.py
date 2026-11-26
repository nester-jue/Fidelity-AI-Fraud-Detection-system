import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import quote
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


# ── Authenticator-app MFA ( RFC 6238 TOTP, pure standard library ) ──────
def generate_totp_secret() -> str:
    """Return a base32 secret suitable for Google Authenticator / Authy."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_at(secret: str, counter: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    message = struct.pack(">Q", counter)
    digest = hmac.new(key, message, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 1_000_000).zfill(6)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify a 6-digit code, allowing a one-step clock skew by default."""
    if not secret or not code or not str(code).isdigit():
        return False
    step = int(time.time()) // 30
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_totp_at(secret, step + delta), str(code).zfill(6)):
            return True
    return False


def totp_provisioning_uri(username: str, secret: str, issuer: str = None) -> str:
    issuer = issuer or settings.ORGANIZATION
    label = quote(f"{issuer}:{username}")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )
