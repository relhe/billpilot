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
