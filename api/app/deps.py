import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.security import decode_token

_bearer = HTTPBearer(auto_error=False)


def _user_from_token(token, db: Session) -> models.User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    token = cred.credentials if cred and cred.scheme.lower() == "bearer" else None
    return _user_from_token(token, db)


def get_user_media(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Accept the JWT either in the Authorization header OR the ?token= query
    param (needed so the browser <audio> element can stream with auth; it cannot
    set a header). Internal/tailnet endpoint, so query-param auth is acceptable."""
    bearer = cred.credentials if cred and cred.scheme.lower() == "bearer" else token
    return _user_from_token(bearer, db)


def get_current_admin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return user