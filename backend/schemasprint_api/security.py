import hashlib
import hmac
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

SESSION_COOKIE = "__Host-schemasprint_session"
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True, slots=True)
class Principal:
    session_id: str
    user_id: str
    auth_user_id: str
    roles: frozenset[str]
    allowlisted: bool
    identity_verified: bool
    age_declared: bool
    policies_current: bool
    mfa_current: bool


def token_digest(token: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def csrf_token(session_id: str, csrf_key: str) -> str:
    return hmac.new(csrf_key.encode(), session_id.encode(), hashlib.sha256).hexdigest()


def require_csrf(request: Request, principal: Principal, csrf_key: str) -> None:
    supplied = request.headers.get(CSRF_HEADER, "")
    expected = csrf_token(principal.session_id, csrf_key)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_FAILED")
