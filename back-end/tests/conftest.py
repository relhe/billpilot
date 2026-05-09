import os

os.environ.setdefault("MONGO_CONNECTION_STRING", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient


@pytest_asyncio.fixture
async def mock_db():
    client = AsyncMongoMockClient()
    return client["billpilot_test"]


@pytest_asyncio.fixture
async def app(mock_db):
    from app.config.settings import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    from app.config.database import get_db
    application = create_app()
    application.dependency_overrides[get_db] = lambda: mock_db
    yield application
    application.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(app, mock_db):
    """Client with a pre-created user and valid auth token."""
    from passlib.context import CryptContext
    from datetime import datetime, timezone

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    await mock_db["users"].insert_one({
        "username": "testuser",
        "hashed_password": pwd_ctx.hash("testpass"),
        "created_at": datetime.now(timezone.utc),
    })

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/v1/auth/token",
            json={"username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac
