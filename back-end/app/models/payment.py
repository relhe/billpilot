from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic_core import core_schema


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError(f"Invalid ObjectId: {v!r}")


class PaymentStatus(str, Enum):
    pending = "pending"
    due_now = "due_now"
    overdue = "overdue"
    completed = "completed"


class PaymentDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    payee_first_name: str
    payee_last_name: str
    payee_email: EmailStr
    payee_phone_number: str
    payee_payment_status: PaymentStatus
    payee_added_date_utc: datetime
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str] = None
    payee_city: str
    payee_country: str
    payee_province_or_state: Optional[str] = None
    payee_postal_code: str
    currency: str
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    tax_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    due_amount: float = Field(gt=0)
    total_due: float = 0.0
    transaction_id: str
    evidence_s3_key: Optional[str] = None
