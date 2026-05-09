# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (FastAPI)
```bash
cd back-end
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Set required env vars (see .env.example), then:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Required environment variables:
- `MONGO_CONNECTION_STRING` — MongoDB URI
- `JWT_SECRET` — secret for HS256 JWT signing
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME` — for S3 evidence storage

### Backend tests
```bash
cd back-end
pytest                          # all tests
pytest tests/unit/              # unit tests only (no env vars needed beyond defaults)
pytest tests/integration/       # integration tests (require env vars)
pytest tests/unit/test_payment_service.py -v   # single file

# With env vars for integration tests:
MONGO_CONNECTION_STRING="mongodb://admin:changeme@localhost:27017/billpilot?authSource=admin" \
  JWT_SECRET="test-secret" AWS_ACCESS_KEY_ID="x" AWS_SECRET_ACCESS_KEY="x" S3_BUCKET_NAME="x" \
  pytest tests/integration/ -v
```

### Frontend (Angular)
```bash
cd front-end
npm install
ng serve               # dev server at :4200
ng build               # production build
ng test                # run all Karma/Jasmine tests
ng test --include='**/payment.service.spec.ts'  # run a single test file
```

### Docker (development)
```bash
cp .env.example .env   # edit MONGO_ROOT_USER / MONGO_ROOT_PASSWORD / JWT_SECRET
docker compose -f docker-compose.dev.yml up --build
# frontend :4200, backend :8000, mongodb :27017
```

### Docker (production — pre-built images)
```bash
docker compose up -d   # pulls trimax10/billpilot-{backend,frontend}:latest
```

### CSV data import
```bash
cd back-end
# Obtain a JWT token first, then:
python -m app.utils.normalisation <bearer_token>
```

## Architecture

### Request flow
```
Browser → Angular frontend (:4200)
  → PaymentService (HttpClient) → environment.serverUrl/api/v1/payments
  → [dev] direct to FastAPI :8000/api/v1/...
  → [prod] nginx :80 proxies /api/ → backend container
  → Routes → Services → Repositories → MongoDB / S3
```

### Backend layered architecture (`back-end/app/`)

**Entry points:**
- `main.py` — `create_app()` factory: lifespan (Motor connect + index creation), middleware stack (CORS → LoggingMiddleware → CorrelationMiddleware), global exception handlers, `v1_router`
- `config/config.yaml` — non-secret config: CORS origins, DB/collection names, allowed MIME types, log level
- `config/settings.py` — `Settings` (pydantic-settings): loads secrets from env vars, non-secrets from config.yaml; `get_settings()` is `@lru_cache`
- `config/database.py` — Motor async client: `connect_db()`, `close_db()`, `get_db()`

**Layers:**
- `routes/v1/` — HTTP only: parse request, call service, return response. Auth routes (`/api/v1/auth/token`, `/api/v1/auth/refresh`), payment routes (`/api/v1/payments/*`), health routes (`/api/v1/health/live`, `/api/v1/health/ready`)
- `services/payment_service.py` — all business logic: `compute_total_due`, `derive_status`, CRUD orchestration, compensating transaction for S3+MongoDB atomicity
- `repositories/` — all I/O: `PaymentRepository` (Motor/MongoDB), `EvidenceRepository` (boto3/S3), `UserRepository` (bcrypt)

**Models & schemas:**
- `models/payment.py` — `PaymentDocument`, `PaymentStatus` enum, `PyObjectId`
- `models/user.py` — `UserDocument`
- `schemas/payment_schemas.py` — `PaymentCreate`, `PaymentUpdate`, `PaymentResponse`, `PaginatedResponse[T]`, `PaymentFilterParams`
- `auth/` — JWT creation/verification, `get_current_user` dependency, auth schemas

**Cross-cutting:**
- `middleware/correlation.py` — injects/echoes `X-Request-ID` per request
- `middleware/logging.py` — structured JSON log line per request (structlog)
- `middleware/rate_limit.py` — slowapi limiter (100 req/min global, 5/min on auth)
- `utils/audit.py` — `write_audit_entry()`: append-only audit log in MongoDB

### Frontend structure (`front-end/src/app/`)
- Pages: `main-screen` (list + filter), `add-payment`, `edit-payment/:id`
- Shared components: `payment-card`, `header`, `footer`, `visibility`
- `services/payment/payment.service.ts` — all API calls to `/api/v1/payments/*`
- `services/autocompletion/autocompletion.service.ts` — calls external APIs (`countriesnow.space`, `restcountries.com`) for country/currency dropdowns

### Key invariants
- `payee_payment_status` is derived on every read by `derive_status()` in `PaymentService`; only `completed` is sticky (set when evidence is uploaded). `pending`/`due_now`/`overdue` are always recomputed from `payee_due_date` vs today.
- `total_due` is always recomputed server-side: `round(due_amount - discount + tax, 2)` where both discount and tax are independent percentages of `due_amount`. Client-submitted `total_due` is rejected (HTTP 422) via `extra="forbid"` on `PaymentCreate`.
- Evidence files are stored in S3 (`evidence/{payment_id}/{uuid}.{ext}`); `evidence_s3_key` in MongoDB holds the key; presigned URLs (1h TTL) are returned on read.
- S3 + MongoDB atomicity uses compensating transactions: upload S3 first, then update MongoDB; if MongoDB update fails, delete S3 object.
- All `/api/v1/payments/*` routes require `Authorization: Bearer <token>`.
- CORS allowed origins are in `config/config.yaml`, not hardcoded.
- MongoDB indexes created at startup via `lifespan`: unique on `transaction_id`, ascending on `payee_payment_status`, `payee_due_date`, `payee_email`; text index on first+last name.
