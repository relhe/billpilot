import pytest
from datetime import date
from pydantic import ValidationError
from app.schemas.payment_schemas import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaginatedResponse,
    PaymentFilterParams,
)
from app.models.payment import PaymentStatus


def _valid_payload(**overrides):
    base = dict(
        payee_first_name="Jane",
        payee_last_name="Smith",
        payee_email="jane@example.com",
        payee_phone_number="+12125551234",
        payee_due_date=date(2026, 12, 1),
        payee_address_line_1="1 Broadway",
        payee_city="New York",
        payee_country="US",
        payee_postal_code="10004",
        currency="USD",
        due_amount=1000.0,
    )
    base.update(overrides)
    return base


def test_payment_create_rejects_total_due_from_client():
    with pytest.raises(ValidationError):
        PaymentCreate(**_valid_payload(), total_due=999.0)


def test_payment_create_rejects_transaction_id_from_client():
    with pytest.raises(ValidationError):
        PaymentCreate(**_valid_payload(), transaction_id="should-not-be-accepted")


def test_payment_create_rejects_zero_due_amount():
    with pytest.raises(ValidationError):
        PaymentCreate(**_valid_payload(due_amount=0))


def test_payment_create_valid():
    p = PaymentCreate(**_valid_payload())
    assert p.due_amount == 1000.0
    assert p.discount_percent == 0.0


def test_payment_filter_params_defaults():
    f = PaymentFilterParams()
    assert f.page == 1
    assert f.page_size == 20
    assert f.search is None
    assert f.status is None


def test_payment_filter_params_page_size_capped():
    f = PaymentFilterParams(page_size=500)
    assert f.page_size == 100


def test_paginated_response_total_pages():
    r = PaginatedResponse[dict](items=[], total=55, page=1, page_size=20)
    assert r.total_pages == 3
