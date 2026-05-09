from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.auth.jwt import verify_token
from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db=Depends(get_db),
) -> dict:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    settings = get_settings()
    try:
        payload = verify_token(
            token,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        if payload.get("type") != "access":
            raise credentials_exc
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = await UserRepository(db).get_by_username(username)
    if user is None:
        raise credentials_exc
    return user
