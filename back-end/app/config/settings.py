import os
import yaml
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml() -> dict:
    path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── secrets from environment ───────────────────────────────────
    mongo_connection_string: str
    jwt_secret: str
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = ""

    # ── non-secret (yaml defaults, overridable by env) ─────────────
    app_name: str = "BillPilot"
    app_version: str = "1.0.0"
    log_level: str = "info"
    cors_origins: List[str] = ["http://localhost:4200"]
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    db_name: str = "billpilot"
    payments_collection: str = "payments"
    users_collection: str = "users"
    audit_log_collection: str = "audit_log"
    s3_evidence_prefix: str = "evidence"
    allowed_mime_types: List[str] = [
        "application/pdf", "image/png", "image/jpeg"
    ]


@lru_cache
def get_settings() -> Settings:
    _yaml = _load_yaml()
    overrides = {
        "app_name": _yaml["app"]["name"],
        "app_version": _yaml["app"]["version"],
        "cors_origins": _yaml["cors"]["allowed_origins"],
        "log_level": _yaml.get("logging", {}).get("level", "info"),
        "allowed_mime_types": _yaml["storage"]["allowed_mime_types"],
        "db_name": _yaml["database"]["name"],
        "payments_collection": _yaml["database"]["collections"]["payments"],
        "users_collection": _yaml["database"]["collections"].get("users", "users"),
        "audit_log_collection": _yaml["database"]["collections"].get("audit_log", "audit_log"),
        "jwt_algorithm": _yaml.get("jwt", {}).get("algorithm", "HS256"),
        "access_token_expire_minutes": _yaml.get("jwt", {}).get("access_token_expire_minutes", 15),
        "refresh_token_expire_days": _yaml.get("jwt", {}).get("refresh_token_expire_days", 7),
        "s3_evidence_prefix": _yaml.get("s3", {}).get("evidence_prefix", "evidence"),
    }
    return Settings(**overrides)
