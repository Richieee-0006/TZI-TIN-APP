"""Podepsané session tokeny a závislosti pro autorizaci (require_user, require_admin)."""
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired
from .config import SESSION_COOKIE, SESSION_MAX_AGE, serializer


# --- Session Helpers ---
def create_session_token(user: Dict[str, Any]) -> str:
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user.get("role", "student"),
        "theme": user.get("theme", "games"),
        "ts": int(time.time())
    }
    return serializer.dumps(payload)


def verify_session_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    return verify_session_token(token)


def require_user(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nejste přihlášeni")
    return user


def require_admin(request: Request) -> Dict[str, Any]:
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pouze pro administrátora")
    return user
