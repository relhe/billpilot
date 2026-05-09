import pytest
from datetime import datetime, timezone
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def _seed_user(mock_db, username="testuser", password="testpass"):
    await mock_db["users"].insert_one({
        "username": username,
        "hashed_password": _pwd_ctx.hash(password),
        "created_at": datetime.now(timezone.utc),
    })


async def test_login_success(client, mock_db):
    await _seed_user(mock_db)
    resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client, mock_db):
    await _seed_user(mock_db)
    resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "testuser", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user(client):
    resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "nobody", "password": "pass"},
    )
    assert resp.status_code == 401


async def test_refresh_token_success(client, mock_db):
    await _seed_user(mock_db)
    login_resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "testuser", "password": "testpass"},
    )
    refresh_token = login_resp.json()["refresh_token"]
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_with_access_token_fails(client, mock_db):
    await _seed_user(mock_db)
    login_resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "testuser", "password": "testpass"},
    )
    access_token = login_resp.json()["access_token"]
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401
