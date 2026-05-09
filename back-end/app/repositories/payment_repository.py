from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Tuple, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository
from app.schemas.payment_schemas import PaymentFilterParams


def _serialize_doc(doc: dict) -> dict:
    """Convert Python types that BSON cannot encode (e.g. date → datetime)."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, date) and not isinstance(v, datetime):
            # Store date as UTC midnight datetime so Motor/BSON is happy
            out[k] = datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
        else:
            out[k] = v
    return out


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
        result = await self._col.insert_one(_serialize_doc(doc))
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
        await self._col.update_one({"_id": oid}, {"$set": _serialize_doc(fields)})
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
