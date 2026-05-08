# BillPilot Backend Optimization — Design Spec
**Date:** 2026-05-08
**Author:** Renel Lherisson
**Status:** Approved

---

## 1. Objective

Redesign the BillPilot FastAPI backend from a flat, synchronous, unauthenticated prototype into a production-grade, enterprise-quality service. The redesign targets four dimensions: **performance**, **security**, **reliability**, and **maintainability** — while fully delivering the README-stated feature scope (pagination, filtering, evidence uploads, dynamic status, CSV normalization).

---

## 2. Current State Problems

| Dimension | Issue |
|---|---|
| Performance | Synchronous `pymongo` blocks the async event loop; no pagination; no indexes; evidence stored as binary blobs in MongoDB documents |
| Security | Zero authentication; file upload trusts client-supplied MIME header; no rate limiting; non-atomic multi-step operations |
| Reliability | `total_due` declared as both field and `@property` (silent conflict); `PUT` always returns `{"id": null}`; DB connected at import time with no retry; no logging; frontend upload URL mismatches backend route |
| Maintainability | All routes in one 200-line file; business logic buried in serializer; `constants.py` duplicates `database.py` config reads; `normalisation.py` has its own copy of `Payment`; no tests; no API versioning |

---

## 3. Architecture

### 3.1 Pattern
**Layered architecture: Routes → Services → Repositories**

- **Routes** — HTTP concerns only: parse request, call service, return response
- **Services** — all business logic: status derivation, `total_due` computation, atomicity
- **Repositories** — all I/O: Motor (MongoDB) and boto3 (S3)
- **Models/Schemas** — single source of truth for all Pydantic definitions

### 3.2 Directory Structure

```
back-end/app/
├── main.py                        # app factory, lifespan, middleware stack
├── config/
│   ├── config.yaml                # cors, db, s3, jwt, rate limits, log level
│   └── settings.py                # typed Settings class via pydantic-settings
├── auth/
│   ├── jwt.py                     # access + refresh token create/verify (python-jose, HS256)
│   ├── dependencies.py            # get_current_user FastAPI dependency
│   └── schemas.py                 # TokenResponse, LoginRequest, RefreshRequest
├── models/
│   ├── payment.py                 # PaymentDocument (MongoDB document shape)
│   └── user.py                    # UserDocument
├── repositories/
│   ├── base.py                    # shared Motor helpers, PyObjectId type
│   ├── payment_repository.py      # async CRUD + paginated aggregation pipeline
│   ├── evidence_repository.py     # S3 upload / presigned URL / delete
│   └── user_repository.py         # user lookup for auth
├── services/
│   └── payment_service.py         # all business logic, orchestrates repos
├── routes/
│   ├── v1/
│   │   ├── auth_routes.py         # POST /api/v1/auth/token, /refresh
│   │   ├── payment_routes.py      # thin HTTP layer, all /api/v1/payments/*
│   │   └── health_routes.py       # GET /api/v1/health/live, /ready
│   └── router.py                  # assembles all v1 routes under /api/v1
├── schemas/
│   └── payment_schemas.py         # PaymentCreate, PaymentUpdate, PaymentResponse, PaginatedResponse, PaymentFilterParams
├── middleware/
│   ├── correlation.py             # injects/reads X-Request-ID per request
│   ├── logging.py                 # structured JSON request/response log line
│   └── rate_limit.py              # slowapi limiter instance + config
└── utils/
    ├── audit.py                   # append-only audit log writer
    └── normalisation.py           # CSV → API seeder (uses shared Payment model)
```

---

## 4. Data Model

### 4.1 Payment Document (`payments` collection)

```python
class PaymentDocument(BaseModel):
    id: PyObjectId                       # maps to MongoDB _id
    payee_first_name: str
    payee_last_name: str
    payee_email: EmailStr
    payee_phone_number: str              # stored in E.164 format
    payee_payment_status: PaymentStatus  # enum: pending | due_now | overdue | completed
    payee_added_date_utc: datetime       # UTC datetime (was a hand-rolled string)
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str]
    payee_city: str
    payee_country: str                   # ISO 3166-1 alpha-2
    payee_province_or_state: Optional[str]
    payee_postal_code: str
    currency: str                        # ISO 4217
    discount_percent: float              # 0.00–100.00, default 0.00
    tax_percent: float                   # 0.00–100.00, default 0.00
    due_amount: float
    total_due: float                     # always computed server-side
    transaction_id: str                  # uuid4, unique index
    evidence_s3_key: Optional[str]       # S3 object key, null until evidence uploaded
```

### 4.2 Request/Response Schemas

| Schema | Purpose |
|---|---|
| `PaymentCreate` | POST body — excludes `id`, `total_due`, `transaction_id`, `evidence_s3_key` |
| `PaymentUpdate` | PUT body — same fields as `PaymentCreate` |
| `PaymentResponse` | API response — includes `id`, computed `total_due`, `evidence_download_url` (S3 presigned, 1h TTL) |
| `PaginatedResponse[T]` | Generic wrapper: `items`, `total`, `page`, `page_size`, `total_pages` |
| `PaymentFilterParams` | Query params: `search`, `status`, `sort_by`, `sort_order`, `page`, `page_size` |

### 4.3 User Document (`users` collection)

```python
class UserDocument(BaseModel):
    id: PyObjectId
    username: str          # unique index
    hashed_password: str   # bcrypt
    created_at: datetime
```

### 4.4 Audit Log Document (`audit_log` collection)

```python
class AuditEntry(BaseModel):
    timestamp: datetime
    user_id: str
    action: Literal["create", "update", "delete", "upload_evidence"]
    payment_id: str
    diff: dict             # changed fields only (before/after for updates)
```

### 4.5 MongoDB Indexes

| Collection | Index | Type |
|---|---|---|
| `payments` | `transaction_id` | unique |
| `payments` | `payee_payment_status` | ascending |
| `payments` | `payee_due_date` | ascending |
| `payments` | `payee_email` | ascending |
| `payments` | `payee_first_name`, `payee_last_name` | text (full-text search) |
| `users` | `username` | unique |

Indexes created once at application startup via `lifespan`.

---

## 5. Service Layer

### 5.1 PaymentService Methods

```
get_payment(id, user)           → fetch doc → derive status → attach presigned URL → return PaymentResponse
list_payments(filters, user)    → paginated fetch → derive statuses → return PaginatedResponse
create_payment(data, user)      → compute total_due → assign transaction_id → insert → audit log
update_payment(id, data, user)  → recompute total_due → update → audit log
delete_payment(id, user)        → delete S3 evidence (if present) → delete payment doc → audit log
upload_evidence(id, file, user) → validate file bytes (magic bytes, not header) → S3 upload →
                                   update evidence_s3_key + status=completed (Motor session) → audit log
download_evidence(id, user)     → fetch evidence_s3_key → return presigned URL
```

### 5.2 Status Derivation Rule (service only, never in serializer)

```
if status == completed        → keep completed (evidence is present)
elif due_date > today         → pending
elif due_date == today        → due_now
elif due_date < today         → overdue
```

Status is derived on every read. The stored `payee_payment_status` value is the source of truth only for `completed`.

### 5.3 total_due Computation

```
discount = due_amount * (discount_percent / 100)
tax      = due_amount * (tax_percent / 100)
total_due = round(due_amount - discount + tax, 2)
```

Discount and tax are both computed as independent percentages of `due_amount` (not sequentially). Computed in service before every insert and update. Never accepted from client input.

### 5.4 Atomicity

S3 is external and cannot participate in a MongoDB transaction. Both operations use a **compensating transaction** pattern:

- `upload_evidence`: upload to S3 first → update MongoDB. If the MongoDB update fails, delete the S3 object as compensation. The window of inconsistency (S3 uploaded, MongoDB not yet updated) is milliseconds and self-corrects.
- `delete_payment`: delete S3 object first → delete MongoDB document. If S3 delete fails, the MongoDB document is left intact and the error is surfaced to the caller.

---

## 6. Repository Layer

### 6.1 PaymentRepository

All methods are `async`. Uses Motor's `AsyncIOMotorClient`.

```
create(doc: dict)                        → InsertOneResult
get_by_id(id: str)                       → dict | None
list_paginated(filters: PaymentFilterParams) → (list[dict], total_count: int)
update(id: str, fields: dict)            → dict | None  # returns updated doc
delete(id: str)                          → bool
create_indexes()                         → None  # called at startup
```

`list_paginated` uses a MongoDB aggregation pipeline:
```
$match (status, text search)
→ $sort
→ $facet: { data: [$skip, $limit], total: [$count] }
```

### 6.2 EvidenceRepository

```
upload(s3_key: str, file_bytes: bytes, content_type: str) → str  # returns s3_key
get_presigned_url(s3_key: str, expires: int = 3600)       → str
delete(s3_key: str)                                        → None
check_connectivity()                                       → bool  # for health probe
```

S3 key format: `evidence/{payment_id}/{uuid4}.{ext}`

---

## 7. Authentication

- **Algorithm:** HS256 (python-jose)
- **Access token TTL:** 15 minutes
- **Refresh token TTL:** 7 days
- **Password hashing:** bcrypt (passlib)
- **Endpoints:**
  - `POST /api/v1/auth/token` — `{username, password}` → `{access_token, refresh_token, token_type}`
  - `POST /api/v1/auth/refresh` — `{refresh_token}` → `{access_token, token_type}`
- **Protection:** All `/api/v1/payments/*` routes require `Authorization: Bearer <token>`
- **Rate limit on auth:** 5 requests/minute per IP

---

## 8. Pagination & Filtering

`GET /api/v1/payments` accepts query parameters:

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |
| `search` | str | — | Full-text search on first + last name |
| `status` | PaymentStatus | — | Filter by payment status |
| `sort_by` | str | `payee_due_date` | Field to sort on |
| `sort_order` | `asc`\|`desc` | `asc` | Sort direction |

Response:
```json
{
  "items": [...],
  "total": 342,
  "page": 1,
  "page_size": 20,
  "total_pages": 18
}
```

---

## 9. Middleware Stack

Applied in this order in `main.py`:

| Middleware | Behaviour |
|---|---|
| `CorrelationMiddleware` | Reads `X-Request-ID` header or generates UUID4; injects into request state and echoes in response header |
| `LoggingMiddleware` | Emits one structured JSON log line per request: `method`, `path`, `status_code`, `duration_ms`, `request_id`, `user_id` |
| `RateLimitMiddleware` | slowapi — 100 req/min per IP globally; 5 req/min per IP on `/auth/token` |
| `CORSMiddleware` | Origins from `config.yaml` |

---

## 10. Observability

### 10.1 Structured Logging (structlog)
- All log output is newline-delimited JSON
- Every log entry includes: `timestamp`, `level`, `request_id`, `event`
- Service-level logs include `user_id`, `payment_id` where applicable
- Log level configurable via `config.yaml` (`debug` | `info` | `warning` | `error`)

### 10.2 Audit Trail
- Collection: `audit_log` (MongoDB)
- Written by `utils/audit.py` on every payment mutation
- Append-only: no routes expose update or delete on audit entries
- `diff` field contains before/after values for updates

### 10.3 Health Probes
- `GET /api/v1/health/live` — returns `200 {"status": "ok"}` immediately (liveness)
- `GET /api/v1/health/ready` — pings MongoDB + S3; returns `200 {"status": "ok"}` if both respond, `503 {"status": "degraded", "detail": {...}}` if either fails (readiness)

---

## 11. Error Handling

Global exception handlers registered in `main.py`:

| Exception | HTTP Status | Response shape |
|---|---|---|
| `RequestValidationError` | 422 | `{"error": "validation_error", "detail": [...]}` |
| `HTTPException` | as raised | `{"error": "<slug>", "detail": "<message>"}` |
| `PyMongoError` | 503 | `{"error": "database_error", "detail": "..."}` |
| `BotoCoreError` | 503 | `{"error": "storage_error", "detail": "..."}` |
| Unhandled `Exception` | 500 | `{"error": "internal_error", "detail": "An unexpected error occurred"}` — full traceback logged, never exposed to client |

---

## 12. API Routes Summary

All routes prefixed `/api/v1/`.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/token` | — | Obtain access + refresh tokens |
| POST | `/auth/refresh` | — | Refresh access token |
| GET | `/payments` | ✓ | Paginated + filtered payment list |
| GET | `/payments/{id}` | ✓ | Single payment |
| POST | `/payments` | ✓ | Create payment |
| PUT | `/payments/{id}` | ✓ | Update payment |
| DELETE | `/payments/{id}` | ✓ | Delete payment + evidence |
| POST | `/payments/{id}/evidence` | ✓ | Upload evidence file |
| GET | `/payments/{id}/evidence` | ✓ | Get presigned download URL |
| GET | `/health/live` | — | Liveness probe |
| GET | `/health/ready` | — | Readiness probe |

---

## 13. Dependencies to Add

```
motor                  # async MongoDB driver
pydantic-settings      # typed settings from env + yaml
python-jose[cryptography]  # JWT
passlib[bcrypt]        # password hashing
boto3                  # S3 client
slowapi                # rate limiting for FastAPI
structlog              # structured logging
python-magic           # file byte inspection (magic bytes validation)
```

Remove: `gridfs` (unused import), `fastapi-cors` (redundant — `fastapi[all]` already includes CORS middleware).

Keep: `requests` — still used by `normalisation.py` to POST seeded payments to the API. Add `httpx` for async HTTP in tests.

---

## 14. Out of Scope

- Frontend changes (covered separately)
- Redis caching (can be added as a later optimization layer)
- OpenTelemetry tracing export (hooks are in place via correlation IDs; exporter wiring is a separate concern)
- Role-based access control beyond authenticated/unauthenticated
