import csv
from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import requests
import json


class Payment(BaseModel):
    payee_first_name: str
    payee_last_name: str
    payee_payment_status: Literal["completed", "due_now", "overdue", "pending"]
    payee_added_date_utc: str
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str]
    payee_city: str
    payee_country: str
    payee_province_or_state: Optional[str]
    payee_postal_code: str
    payee_phone_number: str
    payee_email: str
    currency: str
    discount_percent: Optional[float] = Field(default=0.00, ge=0.00, le=100.00)
    tax_percent: Optional[float] = Field(default=0.00, ge=0.00, le=100.00)
    due_amount: float
    total_due: Optional[float] = Field(default=0.00)


def parse_csv_to_payments(file_path: str) -> List[Payment]:
    payments = []

    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            try:
                # Convert payee_added_date_utc to the desired format
                timestamp_utc = int(row['payee_added_date_utc'])
                payee_added_date_utc = datetime.utcfromtimestamp(timestamp_utc)
                formatted_added_date = payee_added_date_utc.strftime(
                    "%b %d, %Y, %I:%M %p")

                # Validate and adjust phone number to E.164 format
                phone_number = row['payee_phone_number']
                if not phone_number.startswith("+"):
                    phone_number = "+" + phone_number

                # Create a Payment object
                payment = Payment(
                    payee_first_name=row['payee_first_name'],
                    payee_last_name=row['payee_last_name'],
                    payee_payment_status=row['payee_payment_status'],
                    payee_added_date_utc=formatted_added_date,
                    payee_due_date=datetime.strptime(
                        row['payee_due_date'], "%Y-%m-%d").date(),
                    payee_address_line_1=row['payee_address_line_1'],
                    payee_address_line_2=row.get('payee_address_line_2', None),
                    payee_city=row['payee_city'],
                    payee_country=row['payee_country'],
                    payee_province_or_state=row.get(
                        'payee_province_or_state', None),
                    payee_postal_code=row['payee_postal_code'],
                    payee_phone_number=phone_number,
                    payee_email=row['payee_email'],
                    currency=row['currency'],
                    discount_percent=float(row.get('discount_percent', 0.00)),
                    tax_percent=float(row.get('tax_percent', 0.00)),
                    due_amount=float(row['due_amount']),
                    total_due=float(row.get('total_due', 0.00))
                )

                payments.append(payment)

            except Exception as e:
                print(f"Error processing row {row}: {e}")

    return payments


def post_payments_to_api(payments: List[Payment], api_url: str):
    for payment in payments:
        try:
            # Serialize Payment object, converting date fields to ISO format
            payment_data = payment.dict()
            payment_data["payee_due_date"] = payment.payee_due_date.isoformat()

            requests.post(api_url, json=payment_data)
        except Exception as e:
            print(
                f"Error sending payment {payment.payee_first_name} {payment.payee_last_name}: {e}")


# Example usage
if __name__ == "__main__":
    file_path = "payment_information.csv"
    # Update this to match your API endpoint
    api_url = "http://127.0.0.1:8000/payments/"
    payments = parse_csv_to_payments(file_path)
    post_payments_to_api(payments, api_url)
