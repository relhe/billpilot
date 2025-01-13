from datetime import datetime


def serialize_payment(payment):
    """
    Serialize a payment document to a dictionary format for the API response.

    Args:
        payment (dict): The payment document from MongoDB.

    Returns:
        dict: The serialized payment.
    """
    payee_due_date = payment.get("payee_due_date")

    # Ensure `payee_due_date` is converted to `datetime.date` for comparison
    if isinstance(payee_due_date, datetime):
        payee_due_date = payee_due_date.date()

    today = datetime.now().date()

    if payee_due_date == today:
        payment["payee_payment_status"] = "due_now"
    elif payee_due_date and payee_due_date < today:
        payment["payee_payment_status"] = "overdue"

    return {
        "id": str(payment.get("_id")),
        "payee_first_name": payment.get("payee_first_name", ""),
        "payee_last_name": payment.get("payee_last_name", ""),
        "payee_payment_status": payment.get("payee_payment_status", ""),
        "payee_added_date_utc": payment.get("payee_added_date_utc", ""),
        "payee_due_date": payee_due_date.isoformat() if payee_due_date else None,
        "payee_address_line_1": payment.get("payee_address_line_1", ""),
        "payee_address_line_2": payment.get("payee_address_line_2", ""),
        "payee_city": payment.get("payee_city", ""),
        "payee_country": payment.get("payee_country", ""),
        "payee_province_or_state": payment.get("payee_province_or_state", ""),
        "payee_postal_code": payment.get("payee_postal_code", ""),
        "payee_phone_number": payment.get("payee_phone_number", ""),
        "payee_email": payment.get("payee_email", ""),
        "currency": payment.get("currency", ""),
        "discount_percent": payment.get("discount_percent", 0.0),
        "tax_percent": payment.get("tax_percent", 0.0),
        "due_amount": payment.get("due_amount", 0.0),
        "total_due": payment.get("total_due", 0.0),
    }


def serialize_payments(payments) -> list:
    return [serialize_payment(payment) for payment in payments]
