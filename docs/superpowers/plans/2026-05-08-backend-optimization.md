# BillPilot Backend Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the BillPilot FastAPI backend with a clean layered architecture (Routes → Services → Repositories) delivering JWT auth, async Motor DB, S3 evidence storage, server-side pagination/filtering, structured logging, audit trail, rate limiting, and health probes under `/api/v1/`.

**Architecture:** Routes handle HTTP only; Services own all business logic (status derivation, `total_due`, atomicity); Repositories own all I/O (Motor for MongoDB, boto3 for S3). Motor replaces pymongo for non-blocking async. JWT guards all payment endpoints. Evidence files move from MongoDB binary blobs to S3 objects referenced by key in the payment document.

**Tech Stack:** FastAPI, Motor (async MongoDB), python-jose (JWT), passlib/bcrypt, boto3 (S3), slowapi (rate limiting), structlog (structured logging), pydantic-settings, pytest + pytest-asyncio + mongomock-motor + moto[s3]

---

## File Map

### Created (new files)
```
back-end/
├── pytest.ini
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_jwt.py
│   │   ├── test_payment_service.py
│   │   └── test_schemas.py
│   └── integration/
│       ├── __init__.py
│       ├── test_auth_routes.py
│       ├── test_payment_routes.py
│       └── test_health_routes.py
└── app/
    ├── auth/
    │   ├── __init__.py
    │   ├── jwt.py                 # token create/verify
    │   ├── dependencies.py        # get_current_user FastAPI dependency
    │   └── schemas.py             # LoginRequest, TokenResponse, RefreshRequest
    ├── models/
    │   ├── payment.py             # PaymentDocument, PaymentStatus, PyObjectId
    │   └── user.py                # UserDocument
    ├── repositories/
    │   ├── __init__.py
    │   ├── base.py                # shared Motor helpers
    │   ├── payment_repository.py  # async CRUD + aggregation pagination
    │   ├── evidence_repository.py # S3 upload/presigned/delete/health
    │   └── user_repository.py     # user lookup + create
    ├── services/
    │   ├── __init__.py
    │   └── payment_service.py     # all business logic
    ├── schemas/
    │   └── payment_schemas.py     # PaymentCreate, PaymentUpdate, PaymentResponse,
    │                              # PaginatedResponse, PaymentFilterParams
    ├── middleware/
    │   ├── __init__.py
    │   ├── correlation.py         # X-Request-ID injection
    │   ├── logging.py             # structured per-request log line
    │   └── rate_limit.py          # slowapi limiter instance
    ├── routes/
    │   └── v1/
    │       ├── __init__.py
    │       ├── auth_routes.py     # POST /api/v1/auth/token, /refresh
    │       ├── payment_routes.py  # all /api/v1/payments/* (thin)
    │       └── health_routes.py   # GET /api/v1/health/live, /ready
    └── utils/
        └── audit.py               # append-only audit log writer
```

### Modified (existing files)
```
back-end/requirements.txt              # add motor, pydantic-settings, python-jose, etc.
back-end/app/config/config.yaml        # add jwt, s3, logging sections
back-end/app/config/settings.py        # replace with pydantic-settings Settings class
back-end/app/config/database.py        # replace pymongo with Motor + lifespan helpers
back-end/app/main.py                   # app factory, lifespan, middleware, error handlers
back-end/app/models/__init__.py        # re-export from models/payment.py
back-end/app/routes/__init__.py        # mount v1 router
back-end/app/schemas/__init__.py       # re-export from schemas/payment_schemas.py
back-end/app/utils/normalisation.py    # remove duplicate Payment model
back-end/.env.example                  # add JWT_SECRET, AWS_*, S3_BUCKET_NAME
back-end/Dockerfile                    # add libmagic apt install
```

### Deleted (replaced)
```
back-end/app/models/payment_model.py   # replaced by models/payment.py
back-end/app/schemas/payment_schema.py # replaced by schemas/payment_schemas.py
back-end/app/routes/payment_routes.py  # replaced by routes/v1/payment_routes.py
back-end/app/constants/constants.py    # merged into settings.py
back-end/app/utils/utils.py            # merged into payment_service.py
```

---

## Task 1: Project Setup — Dependencies, Config, Scaffolding

**Files:**
- Modify: `back-end/requirements.txt`
- Modify: `back-end/app/config/config.yaml`
- Modify: `back-end/.env.example`
- Create: `back-end/pytest.ini`
- Create: `back-end/tests/__init__.py`, `back-end/tests/unit/__init__.py`, `back-end/tests/integration/__init__.py`
- Create: `back-end/tests/conftest.py`
- Create: `back-end/app/auth/__init__.py`, `back-end/app/repositories/__init__.py`, `back-end/app/services/__init__.py`, `back-end/app/middleware/__init__.py`, `back-end/app/routes/v1/__init__.py`

- [ ] **Step 1: Replace `back-end/requirements.txt`**

```
pydantic
pydantic[email]
pydantic-settings
fastapi
fastapi[all]
uvicorn
motor
pymongo[srv]
python-dotenv
pyyaml
pandas
python-multipart
pycountry
phonenumbers
requests
python-jose[cryptography]
passlib[bcrypt]
boto3
slowapi
structlog
httpx
pytest
pytest-asyncio
mongomock-motor
moto[s3]
```

- [ ] **Step 2: Add new sections to `back-end/app/config/config.yaml`**

Add these sections to the end of the existing file (keep all existing content):

```yaml
jwt:
  algorithm: "HS256"
  access_token_expire_minutes: 15
  refresh_token_expire_days: 7

s3:
  evidence_prefix: "evidence"

logging:
  level: "info"

database:
  name: "billpilot"
  collections:
    payments: "payments"
    users: "users"
    audit_log: "audit_log"
```

Note: the existing `database.collections.evidence` entry is removed — evidence is now in S3.

- [ ] **Step 3: Update `back-end/.env.example`**

```
# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=changeme
MONGO_CONNECTION_STRING=mongodb://admin:changeme@localhost:27017/billpilot?authSource=admin

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET=change-me-to-a-long-random-secret

# ── AWS / S3 ──────────────────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=billpilot-evidence

# ── Production image tag ──────────────────────────────────────────────────────
# IMAGE_TAG=latest
```

- [ ] **Step 4: Create `back-end/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 5: Create all empty `__init__.py` stubs**

Create empty files at:
- `back-end/tests/__init__.py`
- `back-end/tests/unit/__init__.py`
- `back-end/tests/integration/__init__.py`
- `back-end/app/auth/__init__.py`
- `back-end/app/repositories/__init__.py`
- `back-end/app/services/__init__.py`
- `back-end/app/middleware/__init__.py`
- `back-end/app/routes/v1/__init__.py`

- [ ] **Step 6: Create `back-end/tests/conftest.py`**

```python
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
```

- [ ] **Step 7: Install dependencies**

```bash
cd back-end && pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 8: Commit**

```bash
git add back-end/requirements.txt back-end/app/config/config.yaml back-end/.env.example \
        back-end/pytest.ini back-end/tests/ back-end/app/auth/__init__.py \
        back-end/app/repositories/__init__.py back-end/app/services/__init__.py \
        back-end/app/middleware/__init__.py back-end/app/routes/v1/__init__.py
git commit -m "chore: scaffold enterprise backend — deps, config, test infrastructure"
```

---

## Task 2: Typed Settings

**Files:**
- Modify: `back-end/app/config/settings.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_settings.py`**

```python
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
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_settings.py -v
```

Expected: `ImportError` or `AttributeError` — `Settings` doesn't exist yet.

- [ ] **Step 3: Replace `back-end/app/config/settings.py`**

```python
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
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_settings.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/config/settings.py back-end/tests/unit/test_settings.py
git commit -m "feat: typed Settings class with pydantic-settings"
```

---

## Task 3: Async Database Module (Motor)

**Files:**
- Modify: `back-end/app/config/database.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_database.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.config.settings import get_settings


def test_get_db_returns_none_before_connect():
    from app.config import database
    database._db = None
    result = database.get_db()
    assert result is None


@pytest.mark.asyncio
async def test_connect_and_close_db():
    from app.config import database

    mock_client = MagicMock()
    mock_client.get_database.return_value = MagicMock(name="mock_db")

    with patch("app.config.database.AsyncIOMotorClient", return_value=mock_client):
        get_settings.cache_clear()
        settings = get_settings()
        await database.connect_db(settings)
        assert database.get_db() is not None
        await database.close_db()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_database.py -v
```

Expected: `ImportError` — `connect_db` doesn't exist yet.

- [ ] **Step 3: Replace `back-end/app/config/database.py`**

```python
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config.settings import Settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db(settings: Settings) -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_connection_string)
    _db = _client[settings.db_name]


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None


def get_db() -> AsyncIOMotorDatabase | None:
    return _db
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_database.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/config/database.py back-end/tests/unit/test_database.py
git commit -m "feat: replace pymongo with Motor async client"
```

---

## Task 4: Domain Models

**Files:**
- Create: `back-end/app/models/payment.py`
- Create: `back-end/app/models/user.py`
- Modify: `back-end/app/models/__init__.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_models.py`**

```python
import pytest
from datetime import date, datetime, timezone
from bson import ObjectId
from app.models.payment import PaymentDocument, PaymentStatus, PyObjectId
from app.models.user import UserDocument


def test_pyobjectid_accepts_valid_objectid():
    oid = str(ObjectId())
    assert PyObjectId.validate(oid) == oid


def test_pyobjectid_accepts_objectid_instance():
    oid = ObjectId()
    result = PyObjectId.validate(oid)
    assert result == str(oid)


def test_pyobjectid_rejects_invalid():
    with pytest.raises(ValueError):
        PyObjectId.validate("not-an-objectid")


def test_payment_status_values():
    assert PaymentStatus.pending == "pending"
    assert PaymentStatus.due_now == "due_now"
    assert PaymentStatus.overdue == "overdue"
    assert PaymentStatus.completed == "completed"


def test_payment_document_defaults():
    doc = PaymentDocument(
        payee_first_name="John",
        payee_last_name="Doe",
        payee_email="john@example.com",
        payee_phone_number="+12125551234",
        payee_payment_status=PaymentStatus.pending,
        payee_added_date_utc=datetime.now(timezone.utc),
        payee_due_date=date(2026, 6, 1),
        payee_address_line_1="123 Main St",
        payee_city="New York",
        payee_country="US",
        payee_postal_code="10001",
        currency="USD",
        due_amount=500.00,
        total_due=500.00,
        transaction_id="abc-123",
    )
    assert doc.discount_percent == 0.0
    assert doc.tax_percent == 0.0
    assert doc.evidence_s3_key is None


def test_user_document_fields():
    user = UserDocument(
        username="admin",
        hashed_password="$2b$12$...",
        created_at=datetime.now(timezone.utc),
    )
    assert user.username == "admin"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_models.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/models/payment.py`**

```python
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic_core import core_schema


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError(f"Invalid ObjectId: {v!r}")


class PaymentStatus(str, Enum):
    pending = "pending"
    due_now = "due_now"
    overdue = "overdue"
    completed = "completed"


class PaymentDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    payee_first_name: str
    payee_last_name: str
    payee_email: EmailStr
    payee_phone_number: str
    payee_payment_status: PaymentStatus
    payee_added_date_utc: datetime
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str] = None
    payee_city: str
    payee_country: str
    payee_province_or_state: Optional[str] = None
    payee_postal_code: str
    currency: str
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    tax_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    due_amount: float = Field(gt=0)
    total_due: float = 0.0
    transaction_id: str
    evidence_s3_key: Optional[str] = None
```

- [ ] **Step 4: Create `back-end/app/models/user.py`**

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.payment import PyObjectId
from pydantic import Field


class UserDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    username: str
    hashed_password: str
    created_at: datetime
```

- [ ] **Step 5: Update `back-end/app/models/__init__.py`**

```python
from app.models.payment import PaymentDocument, PaymentStatus, PyObjectId
from app.models.user import UserDocument

__all__ = ["PaymentDocument", "PaymentStatus", "PyObjectId", "UserDocument"]
```

- [ ] **Step 6: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_models.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add back-end/app/models/ back-end/tests/unit/test_models.py
git commit -m "feat: domain models — PaymentDocument, UserDocument, PaymentStatus"
```

---

## Task 5: Request/Response Schemas

**Files:**
- Create: `back-end/app/schemas/payment_schemas.py`
- Modify: `back-end/app/schemas/__init__.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_schemas.py`**

```python
import pytest
from datetime import date, datetime, timezone
from pydantic import ValidationError
from app.schemas.payment_schemas import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaginatedResponse,
    PaymentFilterParams,
)
from app.models.payment import PaymentStatus


def _valid_payload(**overrides):
    base = dict(
        payee_first_name="Jane",
        payee_last_name="Smith",
        payee_email="jane@example.com",
        payee_phone_number="+12125551234",
        payee_due_date=date(2026, 12, 1),
        payee_address_line_1="1 Broadway",
        payee_city="New York",
        payee_country="US",
        payee_postal_code="10004",
        currency="USD",
        due_amount=1000.0,
    )
    base.update(overrides)
    return base


def test_payment_create_rejects_total_due_from_client():
    with pytest.raises(ValidationError):
        PaymentCreate(**_valid_payload(), total_due=999.0)


def test_payment_create_rejects_transaction_id_from_client():
    with pytest.raises(ValidationError):
        PaymentCreate(**_valid_payload(), transaction_id="should-not-be-accepted")


def test_payment_create_rejects_zero_due_amount():
    with pytest.raises(ValidationError):
        PaymentCreate(**_valid_payload(due_amount=0))


def test_payment_create_valid():
    p = PaymentCreate(**_valid_payload())
    assert p.due_amount == 1000.0
    assert p.discount_percent == 0.0


def test_payment_filter_params_defaults():
    f = PaymentFilterParams()
    assert f.page == 1
    assert f.page_size == 20
    assert f.search is None
    assert f.status is None


def test_payment_filter_params_page_size_capped():
    f = PaymentFilterParams(page_size=500)
    assert f.page_size == 100


def test_paginated_response_total_pages():
    r = PaginatedResponse[dict](items=[], total=55, page=1, page_size=20)
    assert r.total_pages == 3
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_schemas.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/schemas/payment_schemas.py`**

```python
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.payment import PaymentStatus, PyObjectId

T = TypeVar("T")


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payee_first_name: str
    payee_last_name: str
    payee_email: EmailStr
    payee_phone_number: str
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str] = None
    payee_city: str
    payee_country: str
    payee_province_or_state: Optional[str] = None
    payee_postal_code: str
    currency: str
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    tax_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    due_amount: float = Field(gt=0)

    @field_validator("due_amount", "discount_percent", "tax_percent", mode="before")
    @classmethod
    def round_two_decimals(cls, v):
        return round(float(v), 2) if v is not None else v


class PaymentUpdate(PaymentCreate):
    pass


class PaymentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    payee_first_name: str
    payee_last_name: str
    payee_email: str
    payee_phone_number: str
    payee_payment_status: PaymentStatus
    payee_added_date_utc: datetime
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str] = None
    payee_city: str
    payee_country: str
    payee_province_or_state: Optional[str] = None
    payee_postal_code: str
    currency: str
    discount_percent: float
    tax_percent: float
    due_amount: float
    total_due: float
    transaction_id: str
    evidence_download_url: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.page_size) if self.page_size > 0 else 0


class PaymentFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    search: Optional[str] = None
    status: Optional[PaymentStatus] = None
    sort_by: str = "payee_due_date"
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")

    @field_validator("page_size", mode="after")
    @classmethod
    def cap_page_size(cls, v):
        return min(v, 100)
```

- [ ] **Step 4: Update `back-end/app/schemas/__init__.py`**

```python
from app.schemas.payment_schemas import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaginatedResponse,
    PaymentFilterParams,
)

__all__ = [
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentResponse",
    "PaginatedResponse",
    "PaymentFilterParams",
]
```

- [ ] **Step 5: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_schemas.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add back-end/app/schemas/ back-end/tests/unit/test_schemas.py
git commit -m "feat: request/response schemas with strict validation"
```

---

## Task 6: Payment Repository

**Files:**
- Create: `back-end/app/repositories/base.py`
- Create: `back-end/app/repositories/payment_repository.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_payment_repository.py`**

```python
import pytest
from datetime import date, datetime, timezone
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment_schemas import PaymentFilterParams
from app.models.payment import PaymentStatus


@pytest.fixture
async def repo(mock_db):
    return PaymentRepository(mock_db)


def _payment_doc(**overrides):
    base = {
        "payee_first_name": "Alice",
        "payee_last_name": "Walker",
        "payee_email": "alice@example.com",
        "payee_phone_number": "+12125550001",
        "payee_payment_status": "pending",
        "payee_added_date_utc": datetime.now(timezone.utc),
        "payee_due_date": date(2026, 12, 1),
        "payee_address_line_1": "1 Main St",
        "payee_city": "NYC",
        "payee_country": "US",
        "payee_postal_code": "10001",
        "currency": "USD",
        "discount_percent": 0.0,
        "tax_percent": 0.0,
        "due_amount": 200.0,
        "total_due": 200.0,
        "transaction_id": "txn-001",
        "evidence_s3_key": None,
    }
    base.update(overrides)
    return base


async def test_create_and_get_payment(repo):
    doc = _payment_doc()
    inserted_id = await repo.create(doc)
    assert inserted_id is not None

    result = await repo.get_by_id(inserted_id)
    assert result is not None
    assert result["payee_first_name"] == "Alice"


async def test_get_by_id_returns_none_for_missing(repo):
    result = await repo.get_by_id(str(ObjectId()))
    assert result is None


async def test_update_payment(repo):
    inserted_id = await repo.create(_payment_doc())
    updated = await repo.update(inserted_id, {"payee_first_name": "Updated"})
    assert updated["payee_first_name"] == "Updated"


async def test_delete_payment(repo):
    inserted_id = await repo.create(_payment_doc())
    deleted = await repo.delete(inserted_id)
    assert deleted is True
    assert await repo.get_by_id(inserted_id) is None


async def test_list_paginated_returns_items_and_count(repo):
    for i in range(5):
        await repo.create(_payment_doc(transaction_id=f"txn-{i}"))
    filters = PaymentFilterParams(page=1, page_size=3)
    items, total = await repo.list_paginated(filters)
    assert len(items) == 3
    assert total == 5


async def test_list_paginated_filters_by_status(repo):
    await repo.create(_payment_doc(
        transaction_id="t1", payee_payment_status="completed"
    ))
    await repo.create(_payment_doc(
        transaction_id="t2", payee_payment_status="pending"
    ))
    filters = PaymentFilterParams(status="completed")
    items, total = await repo.list_paginated(filters)
    assert total == 1
    assert items[0]["payee_payment_status"] == "completed"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_payment_repository.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/repositories/base.py`**

```python
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self._col = db[collection_name]

    @staticmethod
    def to_object_id(id_str: str) -> ObjectId | None:
        if ObjectId.is_valid(id_str):
            return ObjectId(id_str)
        return None
```

- [ ] **Step 4: Create `back-end/app/repositories/payment_repository.py`**

```python
from __future__ import annotations

from typing import Tuple, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository
from app.schemas.payment_schemas import PaymentFilterParams


class PaymentRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "payments")

    async def create_indexes(self) -> None:
        await self._col.create_index("transaction_id", unique=True)
        await self._col.create_index("payee_payment_status")
        await self._col.create_index("payee_due_date")
        await self._col.create_index("payee_email")
        await self._col.create_index(
            [("payee_first_name", "text"), ("payee_last_name", "text")]
        )

    async def create(self, doc: dict) -> str:
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, id_str: str) -> dict | None:
        oid = self.to_object_id(id_str)
        if oid is None:
            return None
        return await self._col.find_one({"_id": oid})

    async def update(self, id_str: str, fields: dict) -> dict | None:
        oid = self.to_object_id(id_str)
        if oid is None:
            return None
        await self._col.update_one({"_id": oid}, {"$set": fields})
        return await self._col.find_one({"_id": oid})

    async def delete(self, id_str: str) -> bool:
        oid = self.to_object_id(id_str)
        if oid is None:
            return False
        result = await self._col.delete_one({"_id": oid})
        return result.deleted_count == 1

    async def list_paginated(
        self, filters: PaymentFilterParams
    ) -> Tuple[List[dict], int]:
        match: dict = {}

        if filters.status:
            match["payee_payment_status"] = filters.status.value

        if filters.search:
            match["$text"] = {"$search": filters.search}

        sort_direction = 1 if filters.sort_order == "asc" else -1
        skip = (filters.page - 1) * filters.page_size

        pipeline = [
            {"$match": match},
            {"$sort": {filters.sort_by: sort_direction}},
            {
                "$facet": {
                    "data": [
                        {"$skip": skip},
                        {"$limit": filters.page_size},
                    ],
                    "total": [{"$count": "count"}],
                }
            },
        ]

        cursor = self._col.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            return [], 0

        data = result[0].get("data", [])
        total_list = result[0].get("total", [])
        total = total_list[0]["count"] if total_list else 0
        return data, total
```

- [ ] **Step 5: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_payment_repository.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add back-end/app/repositories/ back-end/tests/unit/test_payment_repository.py
git commit -m "feat: PaymentRepository with async Motor and paginated aggregation"
```

---

## Task 7: Auth — JWT, User Repository, Dependencies, Routes

**Files:**
- Create: `back-end/app/auth/jwt.py`
- Create: `back-end/app/auth/schemas.py`
- Create: `back-end/app/repositories/user_repository.py`
- Create: `back-end/app/auth/dependencies.py`
- Create: `back-end/app/routes/v1/auth_routes.py`
- Create: `back-end/tests/unit/test_jwt.py`
- Create: `back-end/tests/integration/test_auth_routes.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_jwt.py`**

```python
import pytest
from datetime import timedelta
from jose import JWTError
from app.auth.jwt import create_access_token, create_refresh_token, verify_token

SECRET = "test-secret-key-for-testing-only-32chars"
ALGORITHM = "HS256"


def test_create_and_verify_access_token():
    token = create_access_token(
        subject="user123", secret=SECRET, algorithm=ALGORITHM, expires_delta=timedelta(minutes=15)
    )
    payload = verify_token(token, secret=SECRET, algorithm=ALGORITHM)
    assert payload["sub"] == "user123"
    assert payload["type"] == "access"


def test_create_and_verify_refresh_token():
    token = create_refresh_token(
        subject="user123", secret=SECRET, algorithm=ALGORITHM, expires_delta=timedelta(days=7)
    )
    payload = verify_token(token, secret=SECRET, algorithm=ALGORITHM)
    assert payload["sub"] == "user123"
    assert payload["type"] == "refresh"


def test_verify_token_raises_on_invalid():
    with pytest.raises(JWTError):
        verify_token("bad.token.here", secret=SECRET, algorithm=ALGORITHM)


def test_verify_token_raises_on_wrong_secret():
    token = create_access_token(
        subject="u1", secret=SECRET, algorithm=ALGORITHM, expires_delta=timedelta(minutes=5)
    )
    with pytest.raises(JWTError):
        verify_token(token, secret="wrong-secret", algorithm=ALGORITHM)
```

- [ ] **Step 2: Run JWT test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_jwt.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/auth/jwt.py`**

```python
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
```

- [ ] **Step 4: Run JWT test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_jwt.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Create `back-end/app/auth/schemas.py`**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 6: Create `back-end/app/repositories/user_repository.py`**

```python
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext

from app.repositories.base import BaseRepository

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")

    async def get_by_username(self, username: str) -> dict | None:
        return await self._col.find_one({"username": username})

    async def create(self, username: str, plain_password: str) -> str:
        doc = {
            "username": username,
            "hashed_password": _pwd_ctx.hash(plain_password),
            "created_at": datetime.now(timezone.utc),
        }
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_ctx.verify(plain, hashed)
```

- [ ] **Step 7: Create `back-end/app/auth/dependencies.py`**

```python
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
```

- [ ] **Step 8: Create `back-end/app/routes/v1/auth_routes.py`**

```python
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

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
from jose import JWTError

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
```

- [ ] **Step 9: Write `back-end/tests/integration/test_auth_routes.py`**

```python
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
```

These tests require the main app to be wired. Run them after Task 15 (main app factory). Mark as pending for now and continue.

- [ ] **Step 10: Commit**

```bash
git add back-end/app/auth/ back-end/app/repositories/user_repository.py \
        back-end/app/routes/v1/auth_routes.py back-end/tests/unit/test_jwt.py \
        back-end/tests/integration/test_auth_routes.py
git commit -m "feat: JWT auth — tokens, user repository, auth routes"
```

---

## Task 8: Evidence Repository (S3)

**Files:**
- Create: `back-end/app/repositories/evidence_repository.py`
- Create: `back-end/tests/unit/test_evidence_repository.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_evidence_repository.py`**

```python
import pytest
from unittest.mock import MagicMock, patch
from app.repositories.evidence_repository import EvidenceRepository, validate_file_bytes

SETTINGS = MagicMock(
    aws_access_key_id="test",
    aws_secret_access_key="test",
    aws_region="us-east-1",
    s3_bucket_name="test-bucket",
    s3_evidence_prefix="evidence",
)


def test_validate_file_bytes_accepts_pdf():
    pdf_bytes = b"%PDF-1.4 fake content"
    assert validate_file_bytes(pdf_bytes, "application/pdf") is True


def test_validate_file_bytes_accepts_png():
    png_bytes = b"\x89PNG\r\n\x1a\n fake"
    assert validate_file_bytes(png_bytes, "image/png") is True


def test_validate_file_bytes_accepts_jpeg():
    jpeg_bytes = b"\xff\xd8\xff\xe0 fake"
    assert validate_file_bytes(jpeg_bytes, "image/jpeg") is True


def test_validate_file_bytes_rejects_mismatch():
    pdf_bytes = b"%PDF-1.4 fake"
    assert validate_file_bytes(pdf_bytes, "image/png") is False


def test_validate_file_bytes_rejects_unknown():
    assert validate_file_bytes(b"random bytes", "application/pdf") is False


def test_s3_key_format():
    repo = EvidenceRepository(SETTINGS)
    key = repo._make_key("payment123", "invoice.pdf")
    assert key.startswith("evidence/payment123/")
    assert key.endswith(".pdf")


@pytest.mark.asyncio
async def test_upload_stores_object():
    repo = EvidenceRepository(SETTINGS)
    mock_s3 = MagicMock()
    repo._s3 = mock_s3

    key = await repo.upload("pay1", b"%PDF-content", "application/pdf", "doc.pdf")
    assert key.startswith("evidence/pay1/")
    mock_s3.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_delete_removes_object():
    repo = EvidenceRepository(SETTINGS)
    mock_s3 = MagicMock()
    repo._s3 = mock_s3

    await repo.delete("evidence/pay1/file.pdf")
    mock_s3.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="evidence/pay1/file.pdf"
    )
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_evidence_repository.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/repositories/evidence_repository.py`**

```python
from __future__ import annotations

import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_MAGIC_BYTES: dict[bytes, str] = {
    b"%PDF": "application/pdf",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def validate_file_bytes(content: bytes, declared_type: str) -> bool:
    for magic, mime in _MAGIC_BYTES.items():
        if content.startswith(magic):
            return mime == declared_type
    return False


class EvidenceRepository:
    def __init__(self, settings):
        self._bucket = settings.s3_bucket_name
        self._prefix = settings.s3_evidence_prefix
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def _make_key(self, payment_id: str, filename: str) -> str:
        ext = os.path.splitext(filename)[-1].lower() or ".bin"
        return f"{self._prefix}/{payment_id}/{uuid.uuid4()}{ext}"

    async def upload(
        self,
        payment_id: str,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> str:
        key = self._make_key(payment_id, filename)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    async def get_presigned_url(self, s3_key: str, expires: int = 3600) -> str:
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": s3_key},
            ExpiresIn=expires,
        )

    async def delete(self, s3_key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=s3_key)

    async def check_connectivity(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
            return True
        except (BotoCoreError, ClientError):
            return False
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_evidence_repository.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/repositories/evidence_repository.py \
        back-end/tests/unit/test_evidence_repository.py
git commit -m "feat: EvidenceRepository — S3 upload, presigned URL, magic-bytes validation"
```

---

## Task 9: Audit Utility

**Files:**
- Create: `back-end/app/utils/audit.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_audit.py`**

```python
import pytest
from datetime import datetime, timezone
from mongomock_motor import AsyncMongoMockClient
from app.utils.audit import write_audit_entry


@pytest.fixture
async def db():
    client = AsyncMongoMockClient()
    return client["test"]


async def test_write_audit_entry_inserts_document(db):
    await write_audit_entry(
        db=db,
        collection="audit_log",
        user_id="user123",
        action="create",
        payment_id="pay456",
        diff={"payee_first_name": {"after": "Alice"}},
    )
    count = await db["audit_log"].count_documents({})
    assert count == 1


async def test_audit_entry_has_required_fields(db):
    await write_audit_entry(
        db=db,
        collection="audit_log",
        user_id="user123",
        action="update",
        payment_id="pay789",
        diff={"due_amount": {"before": 100.0, "after": 200.0}},
    )
    doc = await db["audit_log"].find_one({})
    assert doc["user_id"] == "user123"
    assert doc["action"] == "update"
    assert doc["payment_id"] == "pay789"
    assert "timestamp" in doc
    assert doc["diff"]["due_amount"]["before"] == 100.0
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_audit.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/utils/audit.py`**

```python
from datetime import datetime, timezone
from typing import Literal

AuditAction = Literal["create", "update", "delete", "upload_evidence"]


async def write_audit_entry(
    *,
    db,
    collection: str,
    user_id: str,
    action: AuditAction,
    payment_id: str,
    diff: dict,
) -> None:
    await db[collection].insert_one(
        {
            "timestamp": datetime.now(timezone.utc),
            "user_id": user_id,
            "action": action,
            "payment_id": payment_id,
            "diff": diff,
        }
    )
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_audit.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/utils/audit.py back-end/tests/unit/test_audit.py
git commit -m "feat: append-only audit log utility"
```

---

## Task 10: Payment Service

**Files:**
- Create: `back-end/app/services/payment_service.py`
- Create: `back-end/tests/unit/test_payment_service.py`

- [ ] **Step 1: Write `back-end/tests/unit/test_payment_service.py`**

```python
import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.payment import PaymentStatus
from app.schemas.payment_schemas import PaymentCreate, PaymentFilterParams
from app.services.payment_service import PaymentService, compute_total_due


# ── unit tests for pure functions ──────────────────────────────────────────


def test_compute_total_due_no_discount_no_tax():
    assert compute_total_due(100.0, 0.0, 0.0) == 100.0


def test_compute_total_due_with_discount():
    assert compute_total_due(100.0, 10.0, 0.0) == 90.0


def test_compute_total_due_with_tax():
    assert compute_total_due(100.0, 0.0, 10.0) == 110.0


def test_compute_total_due_discount_and_tax():
    # 100 - 10 (10% discount) + 10 (10% tax on original) = 100
    assert compute_total_due(100.0, 10.0, 10.0) == 100.0


# ── status derivation ──────────────────────────────────────────────────────


def test_derive_status_completed_stays_completed():
    from app.services.payment_service import derive_status
    result = derive_status(PaymentStatus.completed, date(2020, 1, 1))
    assert result == PaymentStatus.completed


def test_derive_status_future_due_date_is_pending():
    from app.services.payment_service import derive_status
    result = derive_status(PaymentStatus.pending, date(2099, 12, 31))
    assert result == PaymentStatus.pending


def test_derive_status_past_due_date_is_overdue():
    from app.services.payment_service import derive_status
    result = derive_status(PaymentStatus.pending, date(2000, 1, 1))
    assert result == PaymentStatus.overdue


# ── service methods with mocked repos ─────────────────────────────────────


@pytest.fixture
def payment_repo():
    return AsyncMock()


@pytest.fixture
def evidence_repo():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def settings():
    s = MagicMock()
    s.audit_log_collection = "audit_log"
    s.allowed_mime_types = ["application/pdf", "image/png", "image/jpeg"]
    return s


@pytest.fixture
def service(payment_repo, evidence_repo, mock_db, settings):
    return PaymentService(
        payment_repo=payment_repo,
        evidence_repo=evidence_repo,
        db=mock_db,
        settings=settings,
    )


def _mock_payment_doc(overrides=None):
    doc = {
        "_id": "64f1a2b3c4d5e6f7a8b9c0d1",
        "payee_first_name": "Alice",
        "payee_last_name": "Walker",
        "payee_email": "alice@example.com",
        "payee_phone_number": "+12125550001",
        "payee_payment_status": "pending",
        "payee_added_date_utc": datetime.now(timezone.utc),
        "payee_due_date": date(2099, 12, 1),
        "payee_address_line_1": "1 Main St",
        "payee_city": "NYC",
        "payee_country": "US",
        "payee_postal_code": "10001",
        "currency": "USD",
        "discount_percent": 0.0,
        "tax_percent": 0.0,
        "due_amount": 200.0,
        "total_due": 200.0,
        "transaction_id": "txn-abc",
        "evidence_s3_key": None,
    }
    if overrides:
        doc.update(overrides)
    return doc


async def test_create_payment_computes_total_due(service, payment_repo):
    payment_repo.create.return_value = "new-id"
    payload = PaymentCreate(
        payee_first_name="Bob",
        payee_last_name="Jones",
        payee_email="bob@example.com",
        payee_phone_number="+12125550002",
        payee_due_date=date(2099, 6, 1),
        payee_address_line_1="2 Main St",
        payee_city="NYC",
        payee_country="US",
        payee_postal_code="10001",
        currency="USD",
        due_amount=100.0,
        discount_percent=10.0,
        tax_percent=5.0,
    )
    user = {"_id": "uid", "username": "admin"}
    result_id = await service.create_payment(payload, user)
    assert result_id == "new-id"
    inserted = payment_repo.create.call_args[0][0]
    # total_due = 100 - 10 + 5 = 95
    assert inserted["total_due"] == 95.0


async def test_get_payment_attaches_presigned_url(service, payment_repo, evidence_repo):
    doc = _mock_payment_doc({"evidence_s3_key": "evidence/p1/file.pdf"})
    payment_repo.get_by_id.return_value = doc
    evidence_repo.get_presigned_url.return_value = "https://s3.example.com/signed"

    result = await service.get_payment("pay1", user={})
    assert result.evidence_download_url == "https://s3.example.com/signed"


async def test_get_payment_no_evidence_url_when_no_key(service, payment_repo):
    doc = _mock_payment_doc()
    payment_repo.get_by_id.return_value = doc
    result = await service.get_payment("pay1", user={})
    assert result.evidence_download_url is None


async def test_delete_payment_removes_s3_object(service, payment_repo, evidence_repo):
    doc = _mock_payment_doc({"evidence_s3_key": "evidence/p1/file.pdf"})
    payment_repo.get_by_id.return_value = doc
    payment_repo.delete.return_value = True

    await service.delete_payment("pay1", user={"_id": "uid", "username": "admin"})
    evidence_repo.delete.assert_called_once_with("evidence/p1/file.pdf")
    payment_repo.delete.assert_called_once_with("pay1")
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd back-end && pytest tests/unit/test_payment_service.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `back-end/app/services/payment_service.py`**

```python
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

from app.models.payment import PaymentStatus
from app.repositories.evidence_repository import validate_file_bytes
from app.schemas.payment_schemas import (
    PaginatedResponse,
    PaymentCreate,
    PaymentFilterParams,
    PaymentResponse,
    PaymentUpdate,
)
from app.utils.audit import write_audit_entry


def compute_total_due(due_amount: float, discount_percent: float, tax_percent: float) -> float:
    discount = due_amount * (discount_percent / 100)
    tax = due_amount * (tax_percent / 100)
    return round(due_amount - discount + tax, 2)


def derive_status(current: PaymentStatus, due_date: date) -> PaymentStatus:
    if current == PaymentStatus.completed:
        return PaymentStatus.completed
    today = datetime.now(timezone.utc).date()
    if due_date > today:
        return PaymentStatus.pending
    if due_date == today:
        return PaymentStatus.due_now
    return PaymentStatus.overdue


def _doc_to_response(doc: dict, evidence_url: str | None = None) -> PaymentResponse:
    due_date = doc["payee_due_date"]
    if isinstance(due_date, datetime):
        due_date = due_date.date()

    derived = derive_status(
        PaymentStatus(doc["payee_payment_status"]), due_date
    )

    return PaymentResponse(
        id=str(doc["_id"]),
        payee_first_name=doc["payee_first_name"],
        payee_last_name=doc["payee_last_name"],
        payee_email=doc["payee_email"],
        payee_phone_number=doc["payee_phone_number"],
        payee_payment_status=derived,
        payee_added_date_utc=doc["payee_added_date_utc"],
        payee_due_date=due_date,
        payee_address_line_1=doc["payee_address_line_1"],
        payee_address_line_2=doc.get("payee_address_line_2"),
        payee_city=doc["payee_city"],
        payee_country=doc["payee_country"],
        payee_province_or_state=doc.get("payee_province_or_state"),
        payee_postal_code=doc["payee_postal_code"],
        currency=doc["currency"],
        discount_percent=doc.get("discount_percent", 0.0),
        tax_percent=doc.get("tax_percent", 0.0),
        due_amount=doc["due_amount"],
        total_due=doc["total_due"],
        transaction_id=doc["transaction_id"],
        evidence_download_url=evidence_url,
    )


class PaymentService:
    def __init__(self, *, payment_repo, evidence_repo, db, settings):
        self._payments = payment_repo
        self._evidence = evidence_repo
        self._db = db
        self._settings = settings

    async def _presigned_url(self, doc: dict) -> str | None:
        key = doc.get("evidence_s3_key")
        if not key:
            return None
        return await self._evidence.get_presigned_url(key)

    async def get_payment(self, payment_id: str, user: dict) -> PaymentResponse:
        doc = await self._payments.get_by_id(payment_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        url = await self._presigned_url(doc)
        return _doc_to_response(doc, url)

    async def list_payments(
        self, filters: PaymentFilterParams, user: dict
    ) -> PaginatedResponse[PaymentResponse]:
        docs, total = await self._payments.list_paginated(filters)
        items = []
        for doc in docs:
            url = await self._presigned_url(doc)
            items.append(_doc_to_response(doc, url))
        return PaginatedResponse[PaymentResponse](
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    async def create_payment(self, data: PaymentCreate, user: dict) -> str:
        doc = data.model_dump()
        doc["total_due"] = compute_total_due(
            doc["due_amount"], doc["discount_percent"], doc["tax_percent"]
        )
        doc["transaction_id"] = str(uuid.uuid4())
        doc["payee_payment_status"] = PaymentStatus.pending.value
        doc["payee_added_date_utc"] = datetime.now(timezone.utc)
        doc["evidence_s3_key"] = None

        inserted_id = await self._payments.create(doc)
        await write_audit_entry(
            db=self._db,
            collection=self._settings.audit_log_collection,
            user_id=str(user.get("_id", "")),
            action="create",
            payment_id=inserted_id,
            diff={"after": doc},
        )
        return inserted_id

    async def update_payment(self, payment_id: str, data: PaymentUpdate, user: dict) -> PaymentResponse:
        existing = await self._payments.get_by_id(payment_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        fields = data.model_dump()
        fields["total_due"] = compute_total_due(
            fields["due_amount"], fields["discount_percent"], fields["tax_percent"]
        )

        before = {k: existing.get(k) for k in fields}
        updated = await self._payments.update(payment_id, fields)
        await write_audit_entry(
            db=self._db,
            collection=self._settings.audit_log_collection,
            user_id=str(user.get("_id", "")),
            action="update",
            payment_id=payment_id,
            diff={"before": before, "after": fields},
        )
        url = await self._presigned_url(updated)
        return _doc_to_response(updated, url)

    async def delete_payment(self, payment_id: str, user: dict) -> None:
        doc = await self._payments.get_by_id(payment_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        s3_key = doc.get("evidence_s3_key")
        if s3_key:
            await self._evidence.delete(s3_key)

        deleted = await self._payments.delete(payment_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        await write_audit_entry(
            db=self._db,
            collection=self._settings.audit_log_collection,
            user_id=str(user.get("_id", "")),
            action="delete",
            payment_id=payment_id,
            diff={"before": doc},
        )

    async def upload_evidence(
        self, payment_id: str, file: UploadFile, user: dict
    ) -> None:
        content_type = file.content_type or ""
        if content_type not in self._settings.allowed_mime_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}",
            )

        file_bytes = await file.read()

        if not validate_file_bytes(file_bytes, content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match declared content type",
            )

        doc = await self._payments.get_by_id(payment_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        # Compensating transaction: upload to S3, then update MongoDB
        s3_key = await self._evidence.upload(
            payment_id, file_bytes, content_type, file.filename or "evidence"
        )
        try:
            await self._payments.update(payment_id, {
                "evidence_s3_key": s3_key,
                "payee_payment_status": PaymentStatus.completed.value,
            })
        except Exception:
            await self._evidence.delete(s3_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record evidence upload",
            )

        await write_audit_entry(
            db=self._db,
            collection=self._settings.audit_log_collection,
            user_id=str(user.get("_id", "")),
            action="upload_evidence",
            payment_id=payment_id,
            diff={"s3_key": s3_key},
        )

    async def download_evidence(self, payment_id: str, user: dict) -> str:
        doc = await self._payments.get_by_id(payment_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        s3_key = doc.get("evidence_s3_key")
        if not s3_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No evidence file")
        return await self._evidence.get_presigned_url(s3_key)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd back-end && pytest tests/unit/test_payment_service.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/services/payment_service.py back-end/tests/unit/test_payment_service.py
git commit -m "feat: PaymentService — status derivation, total_due, compensating transactions, audit"
```

---

## Task 11: Payment Routes

**Files:**
- Create: `back-end/app/routes/v1/payment_routes.py`
- Create: `back-end/tests/integration/test_payment_routes.py`

- [ ] **Step 1: Create `back-end/app/routes/v1/payment_routes.py`**

```python
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment_schemas import (
    PaginatedResponse,
    PaymentCreate,
    PaymentFilterParams,
    PaymentResponse,
    PaymentUpdate,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


def _get_service(db=Depends(get_db)) -> PaymentService:
    settings = get_settings()
    return PaymentService(
        payment_repo=PaymentRepository(db),
        evidence_repo=EvidenceRepository(settings),
        db=db,
        settings=settings,
    )


@router.get("", response_model=PaginatedResponse[PaymentResponse])
async def list_payments(
    filters: PaymentFilterParams = Depends(),
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    return await service.list_payments(filters, user)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    return await service.get_payment(payment_id, user)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    inserted_id = await service.create_payment(body, user)
    return {"id": inserted_id}


@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: str,
    body: PaymentUpdate,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    return await service.update_payment(payment_id, body, user)


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: str,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    await service.delete_payment(payment_id, user)


@router.post("/{payment_id}/evidence", status_code=status.HTTP_200_OK)
async def upload_evidence(
    payment_id: str,
    file: UploadFile = File(...),
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    await service.upload_evidence(payment_id, file, user)
    return {"message": "Evidence uploaded, payment marked as completed"}


@router.get("/{payment_id}/evidence")
async def download_evidence(
    payment_id: str,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    url = await service.download_evidence(payment_id, user)
    return {"download_url": url}
```

- [ ] **Step 2: Write `back-end/tests/integration/test_payment_routes.py`**

```python
import pytest
from datetime import date, datetime, timezone

_VALID_PAYMENT = {
    "payee_first_name": "Carol",
    "payee_last_name": "Danvers",
    "payee_email": "carol@example.com",
    "payee_phone_number": "+12125551234",
    "payee_due_date": "2099-12-01",
    "payee_address_line_1": "1 Avenger Way",
    "payee_city": "New York",
    "payee_country": "US",
    "payee_postal_code": "10001",
    "currency": "USD",
    "due_amount": 250.0,
}


async def test_create_payment_requires_auth(client):
    resp = await client.post("/api/v1/payments", json=_VALID_PAYMENT)
    assert resp.status_code == 401


async def test_create_payment_success(auth_client):
    resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    assert resp.status_code == 201
    assert "id" in resp.json()


async def test_get_payment_success(auth_client):
    create_resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    payment_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/api/v1/payments/{payment_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["payee_first_name"] == "Carol"
    assert data["payee_payment_status"] == "pending"


async def test_get_payment_not_found(auth_client):
    resp = await auth_client.get("/api/v1/payments/64f1a2b3c4d5e6f7a8b9c0d1")
    assert resp.status_code == 404


async def test_list_payments_returns_paginated(auth_client):
    for i in range(3):
        await auth_client.post("/api/v1/payments", json={**_VALID_PAYMENT, "due_amount": float(100 + i)})
    resp = await auth_client.get("/api/v1/payments?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["total_pages"] == 2


async def test_update_payment(auth_client):
    create_resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    payment_id = create_resp.json()["id"]
    updated = {**_VALID_PAYMENT, "due_amount": 500.0}
    resp = await auth_client.put(f"/api/v1/payments/{payment_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["due_amount"] == 500.0
    assert resp.json()["total_due"] == 500.0


async def test_delete_payment(auth_client):
    create_resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    payment_id = create_resp.json()["id"]
    del_resp = await auth_client.delete(f"/api/v1/payments/{payment_id}")
    assert del_resp.status_code == 204
    get_resp = await auth_client.get(f"/api/v1/payments/{payment_id}")
    assert get_resp.status_code == 404


async def test_create_payment_rejects_client_submitted_total_due(auth_client):
    payload = {**_VALID_PAYMENT, "total_due": 9999.0}
    resp = await auth_client.post("/api/v1/payments", json=payload)
    assert resp.status_code == 422
```

These integration tests depend on the main app factory (Task 15). Mark them pending and run after Task 15.

- [ ] **Step 3: Commit**

```bash
git add back-end/app/routes/v1/payment_routes.py back-end/tests/integration/test_payment_routes.py
git commit -m "feat: thin payment routes under /api/v1/payments"
```

---

## Task 12: Health Routes

**Files:**
- Create: `back-end/app/routes/v1/health_routes.py`
- Create: `back-end/tests/integration/test_health_routes.py`

- [ ] **Step 1: Create `back-end/app/routes/v1/health_routes.py`**

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.evidence_repository import EvidenceRepository

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    detail = {}
    settings = get_settings()

    # Check MongoDB
    try:
        db = get_db()
        if db is None:
            raise RuntimeError("DB not initialized")
        await db.command("ping")
        detail["mongodb"] = "ok"
    except Exception as exc:
        detail["mongodb"] = str(exc)

    # Check S3
    try:
        evidence_repo = EvidenceRepository(settings)
        s3_ok = await evidence_repo.check_connectivity()
        detail["s3"] = "ok" if s3_ok else "unreachable"
    except Exception as exc:
        detail["s3"] = str(exc)

    all_ok = all(v == "ok" for v in detail.values())
    http_status = 200 if all_ok else 503
    return JSONResponse(
        status_code=http_status,
        content={"status": "ok" if all_ok else "degraded", "detail": detail},
    )
```

- [ ] **Step 2: Write `back-end/tests/integration/test_health_routes.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch


async def test_liveness_always_200(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readiness_with_healthy_db(client, mock_db):
    mock_db.command = AsyncMock(return_value={"ok": 1})
    with patch(
        "app.routes.v1.health_routes.EvidenceRepository.check_connectivity",
        new=AsyncMock(return_value=True),
    ):
        resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200


async def test_readiness_503_when_db_down(client):
    with patch(
        "app.routes.v1.health_routes.get_db", return_value=None
    ):
        resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
```

These run after Task 15. Mark as pending.

- [ ] **Step 3: Commit**

```bash
git add back-end/app/routes/v1/health_routes.py back-end/tests/integration/test_health_routes.py
git commit -m "feat: liveness and readiness health probes"
```

---

## Task 13: Middleware Stack

**Files:**
- Create: `back-end/app/middleware/correlation.py`
- Create: `back-end/app/middleware/logging.py`
- Create: `back-end/app/middleware/rate_limit.py`

- [ ] **Step 1: Create `back-end/app/middleware/correlation.py`**

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

- [ ] **Step 2: Create `back-end/app/middleware/logging.py`**

```python
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
```

- [ ] **Step 3: Create `back-end/app/middleware/rate_limit.py`**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
```

- [ ] **Step 4: Commit**

```bash
git add back-end/app/middleware/
git commit -m "feat: correlation ID, structured logging, and rate-limit middleware"
```

---

## Task 14: Router Assembly

**Files:**
- Create: `back-end/app/routes/router.py`
- Modify: `back-end/app/routes/__init__.py`

- [ ] **Step 1: Create `back-end/app/routes/router.py`**

```python
from fastapi import APIRouter
from app.routes.v1.auth_routes import router as auth_router
from app.routes.v1.payment_routes import router as payment_router
from app.routes.v1.health_routes import router as health_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(payment_router)
v1_router.include_router(health_router)
```

- [ ] **Step 2: Update `back-end/app/routes/__init__.py`**

```python
from app.routes.router import v1_router

__all__ = ["v1_router"]
```

- [ ] **Step 3: Commit**

```bash
git add back-end/app/routes/router.py back-end/app/routes/__init__.py
git commit -m "feat: v1 router assembly"
```

---

## Task 15: Main App Factory + Error Handlers + Lifespan

**Files:**
- Modify: `back-end/app/main.py`

- [ ] **Step 1: Replace `back-end/app/main.py`**

```python
import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config.database import close_db, connect_db, get_db
from app.config.settings import get_settings
from app.middleware.correlation import CorrelationMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import limiter
from app.repositories.payment_repository import PaymentRepository
from app.routes.router import v1_router


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await connect_db(settings)
        db = get_db()
        await PaymentRepository(db).create_indexes()
        yield
        await close_db()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # ── rate limiting ──────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── middleware (outermost first) ───────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(CorrelationMiddleware)

    # ── global exception handlers ──────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "detail": exc.errors()},
        )

    @app.exception_handler(PyMongoError)
    async def mongo_error_handler(request: Request, exc: PyMongoError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "database_error", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        structlog.get_logger().error("unhandled_exception", exc=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "detail": "An unexpected error occurred"},
        )

    # ── routes ─────────────────────────────────────────────────────
    app.include_router(v1_router)

    return app


app = create_app()
```

- [ ] **Step 2: Run the full integration test suite**

```bash
cd back-end && pytest tests/integration/ -v
```

Expected: all integration tests pass (auth, payment, health).

- [ ] **Step 3: Run the full test suite**

```bash
cd back-end && pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Verify the app starts**

```bash
cd back-end && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected: server starts, no import errors. `GET http://localhost:8000/api/v1/health/live` returns `{"status": "ok"}`.

- [ ] **Step 5: Commit**

```bash
git add back-end/app/main.py
git commit -m "feat: app factory with lifespan, middleware stack, and global error handlers"
```

---

## Task 16: Normalisation Update & Old File Cleanup

**Files:**
- Modify: `back-end/app/utils/normalisation.py`
- Delete: `back-end/app/models/payment_model.py`
- Delete: `back-end/app/schemas/payment_schema.py`
- Delete: `back-end/app/routes/payment_routes.py`
- Delete: `back-end/app/constants/constants.py`
- Delete: `back-end/app/utils/utils.py`

- [ ] **Step 1: Update `back-end/app/utils/normalisation.py`** to remove the duplicate `Payment` model and use the shared one

```python
import csv
import requests
from datetime import datetime, date
from typing import List

from app.models.payment import PaymentStatus
from app.schemas.payment_schemas import PaymentCreate


def parse_csv_to_payments(file_path: str) -> List[dict]:
    payments = []
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp_utc = int(row["payee_added_date_utc"])
                phone = row["payee_phone_number"]
                if not phone.startswith("+"):
                    phone = "+" + phone

                payment = PaymentCreate(
                    payee_first_name=row["payee_first_name"],
                    payee_last_name=row["payee_last_name"],
                    payee_email=row["payee_email"],
                    payee_phone_number=phone,
                    payee_due_date=datetime.strptime(row["payee_due_date"], "%Y-%m-%d").date(),
                    payee_address_line_1=row["payee_address_line_1"],
                    payee_address_line_2=row.get("payee_address_line_2"),
                    payee_city=row["payee_city"],
                    payee_country=row["payee_country"],
                    payee_province_or_state=row.get("payee_province_or_state"),
                    payee_postal_code=row["payee_postal_code"],
                    currency=row["currency"],
                    discount_percent=float(row.get("discount_percent", 0.0)),
                    tax_percent=float(row.get("tax_percent", 0.0)),
                    due_amount=float(row["due_amount"]),
                )
                payments.append(payment.model_dump())
            except Exception as e:
                print(f"Skipping row {row}: {e}")
    return payments


def post_payments_to_api(payments: List[dict], api_url: str) -> None:
    for payment in payments:
        try:
            payment["payee_due_date"] = str(payment["payee_due_date"])
            requests.post(api_url, json=payment)
        except Exception as e:
            print(f"Error sending payment: {e}")


if __name__ == "__main__":
    file_path = "payment_information.csv"
    api_url = "http://127.0.0.1:8000/api/v1/payments"
    payments = parse_csv_to_payments(file_path)
    post_payments_to_api(payments, api_url)
```

- [ ] **Step 2: Delete old files**

```bash
rm back-end/app/models/payment_model.py
rm back-end/app/schemas/payment_schema.py
rm back-end/app/routes/payment_routes.py
rm back-end/app/constants/constants.py
rm back-end/app/utils/utils.py
```

- [ ] **Step 3: Run full test suite to confirm nothing broken**

```bash
cd back-end && pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old files, update normalisation to use shared model"
```

---

## Task 17: Docker & Environment Updates

**Files:**
- Modify: `back-end/Dockerfile`
- Modify: `back-end/Dockerfile.dev`
- Modify: `docker-compose.dev.yml`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update `back-end/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Update `back-end/Dockerfile.dev`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: Add new env vars to `docker-compose.dev.yml` backend service**

In the `backend` service `environment` block, add:
```yaml
JWT_SECRET: ${JWT_SECRET:-change-me-dev-secret}
AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:-}
AWS_REGION: ${AWS_REGION:-us-east-1}
S3_BUCKET_NAME: ${S3_BUCKET_NAME:-}
```

- [ ] **Step 4: Add the same env vars to `docker-compose.yml` (production) backend service**

In the `backend` service `environment` block, add:
```yaml
JWT_SECRET: ${JWT_SECRET}
AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
AWS_REGION: ${AWS_REGION:-us-east-1}
S3_BUCKET_NAME: ${S3_BUCKET_NAME}
```

- [ ] **Step 5: Run final full test suite**

```bash
cd back-end && pytest -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add back-end/Dockerfile back-end/Dockerfile.dev docker-compose.dev.yml docker-compose.yml
git commit -m "chore: update Dockerfiles and compose files for new env vars and health check path"
```

---

## Task 18: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Commands and Architecture sections of `CLAUDE.md`**

Update the backend dev command:
```bash
cd back-end
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Set required env vars (see .env.example), then:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Update the run tests command:
```bash
cd back-end && pytest              # all tests
cd back-end && pytest tests/unit/  # unit only
cd back-end && pytest tests/integration/  # integration only
cd back-end && pytest tests/unit/test_payment_service.py -v  # single file
```

Update the API routes section to reflect `/api/v1/` prefix and new routes.

Update the backend structure description to reflect the new layered architecture.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new backend architecture"
```

---

## Self-Review Checklist

- [x] **Auth** — JWT create/verify, user repo, login/refresh routes, `get_current_user` dependency: Tasks 7
- [x] **Async Motor** — connect_db, close_db, get_db, PaymentRepository all async: Tasks 3, 6
- [x] **S3 evidence** — upload, presigned URL, delete, magic-byte validation, compensating transaction: Tasks 8, 10
- [x] **Pagination + filtering** — `list_paginated` with aggregation pipeline, `PaymentFilterParams`, `PaginatedResponse`: Tasks 6, 5
- [x] **Status derivation** — `derive_status()` in service, not serializer: Task 10
- [x] **`total_due` server-side** — computed in service, rejected from client via `extra="forbid"`: Tasks 5, 10
- [x] **Structured logging** — structlog JSON, `LoggingMiddleware` per-request: Tasks 13, 15
- [x] **Audit trail** — `write_audit_entry` on create/update/delete/upload: Tasks 9, 10
- [x] **Rate limiting** — slowapi global 100/min, stricter on auth route: Tasks 13, 15
- [x] **Health probes** — liveness + readiness (DB ping + S3 check): Task 12
- [x] **API versioning** — all routes under `/api/v1/`: Tasks 7, 11, 12, 14
- [x] **Correlation IDs** — `CorrelationMiddleware`, `X-Request-ID` header: Tasks 13, 15
- [x] **Indexes** — created at startup via `lifespan`: Tasks 6, 15
- [x] **Old files removed** — payment_model.py, payment_schema.py, old routes, constants.py, utils.py: Task 16
- [x] **Type consistency** — `PaymentFilterParams` used in both repo and service; `PaymentResponse` returned from service; `_doc_to_response` helper consistent across get/list/update
