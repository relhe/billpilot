import pytest
from unittest.mock import MagicMock
from app.repositories.evidence_repository import EvidenceRepository, validate_file_bytes

SETTINGS = MagicMock(
    aws_access_key_id="test",
    aws_secret_access_key="test",
    aws_region="us-east-1",
    s3_bucket_name="test-bucket",
    s3_evidence_prefix="evidence",
)


def test_validate_file_bytes_accepts_pdf():
    assert validate_file_bytes(b"%PDF-1.4 fake content", "application/pdf") is True


def test_validate_file_bytes_accepts_png():
    assert validate_file_bytes(b"\x89PNG\r\n\x1a\n fake", "image/png") is True


def test_validate_file_bytes_accepts_jpeg():
    assert validate_file_bytes(b"\xff\xd8\xff\xe0 fake", "image/jpeg") is True


def test_validate_file_bytes_rejects_mismatch():
    assert validate_file_bytes(b"%PDF-1.4 fake", "image/png") is False


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
