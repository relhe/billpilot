import pytest

_VALID_PAYMENT = {
    "payee_first_name": "Carol",
    "payee_last_name": "Danvers",
    "payee_email": "carol@example.com",
    "payee_phone_number": "+12125551234",
    "payee_due_date": "2099-12-01",
    "payee_address_line_1": "1 Avenger Way",
    "payee_city": "New York",
    "payee_country": "US",
    "payee_postal_code": "10001",
    "currency": "USD",
    "due_amount": 250.0,
}


async def test_create_payment_requires_auth(client):
    resp = await client.post("/api/v1/payments", json=_VALID_PAYMENT)
    assert resp.status_code == 401


async def test_create_payment_success(auth_client):
    resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    assert resp.status_code == 201
    assert "id" in resp.json()


async def test_get_payment_success(auth_client):
    create_resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    payment_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/api/v1/payments/{payment_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["payee_first_name"] == "Carol"
    assert data["payee_payment_status"] == "pending"


async def test_get_payment_not_found(auth_client):
    resp = await auth_client.get("/api/v1/payments/64f1a2b3c4d5e6f7a8b9c0d1")
    assert resp.status_code == 404


async def test_list_payments_returns_paginated(auth_client):
    for i in range(3):
        await auth_client.post("/api/v1/payments", json={**_VALID_PAYMENT, "due_amount": float(100 + i)})
    resp = await auth_client.get("/api/v1/payments?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["total_pages"] == 2


async def test_update_payment(auth_client):
    create_resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    payment_id = create_resp.json()["id"]
    updated = {**_VALID_PAYMENT, "due_amount": 500.0}
    resp = await auth_client.put(f"/api/v1/payments/{payment_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["due_amount"] == 500.0
    assert resp.json()["total_due"] == 500.0


async def test_delete_payment(auth_client):
    create_resp = await auth_client.post("/api/v1/payments", json=_VALID_PAYMENT)
    payment_id = create_resp.json()["id"]
    del_resp = await auth_client.delete(f"/api/v1/payments/{payment_id}")
    assert del_resp.status_code == 204
    get_resp = await auth_client.get(f"/api/v1/payments/{payment_id}")
    assert get_resp.status_code == 404


async def test_create_payment_rejects_client_submitted_total_due(auth_client):
    payload = {**_VALID_PAYMENT, "total_due": 9999.0}
    resp = await auth_client.post("/api/v1/payments", json=payload)
    assert resp.status_code == 422
