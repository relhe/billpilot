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
