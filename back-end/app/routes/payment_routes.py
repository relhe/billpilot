from fastapi import APIRouter, HTTPException
from datetime import datetime, date
from app.models.payment_model import Payment
from app.schemas.payment_schema import serialize_payments, serialize_payment
from app.config.database import payments_collection
from bson import ObjectId

router = APIRouter()


@router.get("/")
async def get_payments():
    payments = serialize_payments(payments_collection.find())
    return payments


@router.post("/")
async def create_payment(payment: Payment):
    # Convert the payment object to a dictionary
    payment_dict = payment.dict()

    # Ensure payee_due_date is converted to datetime
    if isinstance(payment_dict["payee_due_date"], date):
        payment_dict["payee_due_date"] = datetime.combine(
            payment_dict["payee_due_date"], datetime.min.time()
        )

    # Insert the document into the database
    result = payments_collection.insert_one(payment_dict)
    return {"id": str(result.inserted_id)}
