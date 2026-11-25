import hashlib, secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()

def hash_password(pw: str) -> str:
    return _ph.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, InvalidHashError):
        return False

def new_session_token() -> tuple[str, str]:
    """(raw token for cookie, sha256 hash for DB). Raw token is never stored."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
