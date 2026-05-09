import csv
import requests
from datetime import datetime
from typing import List

from app.schemas.payment_schemas import PaymentCreate


def parse_csv_to_payments(file_path: str) -> List[dict]:
    payments = []
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                phone = row["payee_phone_number"]
                if not phone.startswith("+"):
                    phone = "+" + phone

                payment = PaymentCreate(
                    payee_first_name=row["payee_first_name"],
                    payee_last_name=row["payee_last_name"],
                    payee_email=row["payee_email"],
                    payee_phone_number=phone,
                    payee_due_date=datetime.strptime(row["payee_due_date"], "%Y-%m-%d").date(),
                    payee_address_line_1=row["payee_address_line_1"],
                    payee_address_line_2=row.get("payee_address_line_2"),
                    payee_city=row["payee_city"],
                    payee_country=row["payee_country"],
                    payee_province_or_state=row.get("payee_province_or_state"),
                    payee_postal_code=row["payee_postal_code"],
                    currency=row["currency"],
                    discount_percent=float(row.get("discount_percent", 0.0)),
                    tax_percent=float(row.get("tax_percent", 0.0)),
                    due_amount=float(row["due_amount"]),
                )
                p = payment.model_dump()
                p["payee_due_date"] = str(p["payee_due_date"])
                payments.append(p)
            except Exception as e:
                print(f"Skipping row {row}: {e}")
    return payments


def post_payments_to_api(payments: List[dict], api_url: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    for payment in payments:
        try:
            requests.post(api_url, json=payment, headers=headers)
        except Exception as e:
            print(f"Error sending payment: {e}")


if __name__ == "__main__":
    import sys
    file_path = "payment_information.csv"
    api_url = "http://127.0.0.1:8000/api/v1/payments"
    token = sys.argv[1] if len(sys.argv) > 1 else ""
    if not token:
        print("Usage: python -m app.utils.normalisation <bearer_token>")
        sys.exit(1)
    payments = parse_csv_to_payments(file_path)
    post_payments_to_api(payments, api_url, token)
    print(f"Sent {len(payments)} payments.")
