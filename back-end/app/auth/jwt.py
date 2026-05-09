from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt


def create_access_token(
    *, subject: str, secret: str, algorithm: str, expires_delta: timedelta
) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(
    *, subject: str, secret: str, algorithm: str, expires_delta: timedelta
) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, secret, algorithm=algorithm)


def verify_token(token: str, *, secret: str, algorithm: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=[algorithm])
