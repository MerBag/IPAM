from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
import jwt
from jwt.exceptions import InvalidTokenError

from app.config import settings


password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
# A real Argon2id hash is used when a username does not exist to reduce login timing leakage.
DUMMY_HASH = password_hasher.hash("merbag-dummy-password-never-used")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(encoded: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(encoded)
    except InvalidHashError:
        return True


def create_access_token(*, user_id: int, username: str, role: str) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        return int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid access token") from exc
