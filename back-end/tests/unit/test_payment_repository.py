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
