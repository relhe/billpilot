import pytest
from datetime import timedelta
from jose import JWTError
from app.auth.jwt import create_access_token, create_refresh_token, verify_token

SECRET = "test-secret-key-for-testing-only-32chars"
ALGORITHM = "HS256"


def test_create_and_verify_access_token():
    token = create_access_token(
        subject="user123", secret=SECRET, algorithm=ALGORITHM,
        expires_delta=timedelta(minutes=15)
    )
    payload = verify_token(token, secret=SECRET, algorithm=ALGORITHM)
    assert payload["sub"] == "user123"
    assert payload["type"] == "access"


def test_create_and_verify_refresh_token():
    token = create_refresh_token(
        subject="user123", secret=SECRET, algorithm=ALGORITHM,
        expires_delta=timedelta(days=7)
    )
    payload = verify_token(token, secret=SECRET, algorithm=ALGORITHM)
    assert payload["sub"] == "user123"
    assert payload["type"] == "refresh"


def test_verify_token_raises_on_invalid():
    with pytest.raises(JWTError):
        verify_token("bad.token.here", secret=SECRET, algorithm=ALGORITHM)


def test_verify_token_raises_on_wrong_secret():
    token = create_access_token(
        subject="u1", secret=SECRET, algorithm=ALGORITHM,
        expires_delta=timedelta(minutes=5)
    )
    with pytest.raises(JWTError):
        verify_token(token, secret="wrong-secret", algorithm=ALGORITHM)
