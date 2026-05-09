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
