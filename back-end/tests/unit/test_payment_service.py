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
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=AsyncMock())
    return db


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
