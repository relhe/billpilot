import os
import pytest
from app.config.settings import get_settings, Settings


def test_settings_loads_required_secrets():
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_secret == os.environ["JWT_SECRET"]
    assert s.mongo_connection_string == os.environ["MONGO_CONNECTION_STRING"]
    assert s.s3_bucket_name == os.environ["S3_BUCKET_NAME"]


def test_settings_loads_jwt_config_from_yaml():
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_algorithm == "HS256"
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 7


def test_settings_loads_collections():
    get_settings.cache_clear()
    s = get_settings()
    assert s.payments_collection == "payments"
    assert s.users_collection == "users"
    assert s.audit_log_collection == "audit_log"


def test_settings_allowed_mime_types():
    get_settings.cache_clear()
    s = get_settings()
    assert "application/pdf" in s.allowed_mime_types
    assert "image/png" in s.allowed_mime_types
