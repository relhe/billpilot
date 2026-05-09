from __future__ import annotations

import math
from datetime import date, datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.payment import PaymentStatus

T = TypeVar("T")


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payee_first_name: str
    payee_last_name: str
    payee_email: EmailStr
    payee_phone_number: str
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

    @field_validator("due_amount", "discount_percent", "tax_percent", mode="before")
    @classmethod
    def round_two_decimals(cls, v):
        return round(float(v), 2) if v is not None else v


class PaymentUpdate(PaymentCreate):
    pass


class PaymentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    payee_first_name: str
    payee_last_name: str
    payee_email: str
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
    discount_percent: float
    tax_percent: float
    due_amount: float
    total_due: float
    transaction_id: str
    evidence_download_url: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.page_size) if self.page_size > 0 else 0


class PaymentFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    search: Optional[str] = None
    status: Optional[PaymentStatus] = None
    sort_by: str = "payee_due_date"
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")

    @field_validator("page_size", mode="after")
    @classmethod
    def cap_page_size(cls, v):
        return min(v, 100)
