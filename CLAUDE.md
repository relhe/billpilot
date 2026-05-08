# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (FastAPI)
```bash
cd back-end
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Set MONGO_CONNECTION_STRING in environment, then:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
cp .env.example .env   # edit MONGO_ROOT_USER / MONGO_ROOT_PASSWORD
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
python -m app.utils.normalisation   # reads payment_information.csv, POSTs to API
```

## Architecture

### Request flow
```
Browser → Angular frontend (:4200)
  → PaymentService (HttpClient) → environment.serverUrl/payments
  → [dev] direct to FastAPI :8000/api/...
  → [prod] nginx :80 proxies /api/ → backend container
  → FastAPI routes → MongoDB (billpilot db)
```

### Backend structure (`back-end/app/`)
- `main.py` — FastAPI app; registers `payment_router` under `/api`, applies CORS from config
- `config/config.yaml` — single source of truth: CORS origins, DB names, allowed MIME types
- `config/settings.py` — loads config.yaml; `config` dict imported everywhere
- `config/database.py` — reads `MONGO_CONNECTION_STRING` env var, exposes `db`, `payments_collection`, `evidence_collection`
- `models/payment_model.py` — Pydantic `Payment` model with validators: ISO 3166-1 alpha-2 country, E.164 phone, date format `"Jan 12, 2025, 3:00 PM"`; `total_due` is computed server-side via `utils.compute_total_due`
- `schemas/payment_schema.py` — serialization layer; **this is where `due_now`/`overdue` statuses are dynamically applied** on read by comparing `payee_due_date` to today
- `routes/payment_routes.py` — all REST endpoints; evidence files stored as raw bytes in the `evidence` collection (not GridFS despite the import)
- `utils/normalisation.py` — standalone script to seed MongoDB from a CSV

### Frontend structure (`front-end/src/app/`)
- Pages: `main-screen` (list + filter), `add-payment`, `edit-payment/:id`
- Shared components: `payment-card`, `header`, `footer`, `visibility`
- `services/payment/payment.service.ts` — all API calls; upload uses `/api/upload/:id`, download uses `/api/payments/download/:id` (note: upload URL differs from the `/api/payments/...` pattern)
- `services/autocompletion/autocompletion.service.ts` — calls external APIs (`countriesnow.space`, `restcountries.com`) for country/currency dropdowns
- `interfaces/payment.ts` — TypeScript `Payment` interface (note: field is `total_amount` here vs `total_due` in the backend model — a known inconsistency)

### Key invariants
- `payee_payment_status` is stored in MongoDB but dynamically overridden to `due_now` or `overdue` on every read in `payment_schema.py`; only `completed` and `pending` persist meaningfully
- Uploading evidence automatically sets `payee_payment_status` to `completed` server-side
- `total_due` is always recomputed on create/update; the value sent by the client is ignored
- Evidence files are stored as binary blobs in the `evidence` MongoDB collection, keyed by `payment_id` (ObjectId)
- CORS allowed origins are in `config.yaml`, not hardcoded; add new origins there
