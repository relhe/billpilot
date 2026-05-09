from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError

from app.auth.jwt import create_access_token, create_refresh_token, verify_token
from app.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/token", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_db)):
    settings = get_settings()
    user = await UserRepository(db).get_by_username(body.username)
    if user is None or not UserRepository.verify_password(
        body.password, user["hashed_password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = create_access_token(
        subject=body.username,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(
        subject=body.username,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest, db=Depends(get_db)):
    settings = get_settings()
    try:
        payload = verify_token(
            body.refresh_token,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        if payload.get("type") != "refresh":
            raise ValueError
        username = payload["sub"]
    except (JWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = await UserRepository(db).get_by_username(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access_token = create_access_token(
        subject=username,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return AccessTokenResponse(access_token=access_token)
