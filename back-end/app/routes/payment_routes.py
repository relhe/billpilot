from datetime import datetime, date
from fastapi import APIRouter, HTTPException, File, UploadFile
import uuid
import gridfs
from starlette.responses import StreamingResponse

from app.models.payment_model import Payment
from app.schemas.payment_schema import serialize_payments, serialize_payment
from app.config.database import db, payments_collection, evidence_collection
from bson import ObjectId

from app.utils.utils import compute_total_due
from app.constants.constants import ALLOWED_MIME_TYPES


router = APIRouter()

fs = gridfs.GridFS(db)


@router.get("/")
async def get_payments():
    payments = serialize_payments(payments_collection.find())
    return payments


@router.get("/{id}")
async def get_payment(id: str):
    payment = serialize_payment(
        payments_collection.find_one({"_id": ObjectId(id)}))
    if payment:
        return payment
    else:
        raise HTTPException(status_code=404, detail="Payment not found")


@router.post("/")
async def create_payment(payment: Payment):
    # Convert the payment object to a dictionary
    payment_dict = payment.dict()

    payment_dict["total_due"] = compute_total_due(
        payment_dict["due_amount"],
        payment_dict.get("discount_percent", 0.0),
        payment_dict.get("tax_percent", 0.0),
    )

    # Ensure payee_due_date is converted to datetime
    if isinstance(payment_dict["payee_due_date"], date):
        payment_dict["payee_due_date"] = datetime.combine(
            payment_dict["payee_due_date"], datetime.min.time()
        )

    payment_dict["transaction_id"] = payment_dict.get(
        "transaction_id") or str(uuid.uuid4())

    try:
        result = payments_collection.insert_one(payment_dict)
        return {"id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {e.details.get('errmsg')}"
        )


@router.put("/{id}")
async def update_payment(id: str, payment: Payment):
    # Convert the payment object to a dictionary
    payment_dict = payment.dict()

    payment_dict["total_due"] = compute_total_due(
        payment_dict["due_amount"],
        payment_dict.get("discount_percent", 0.0),
        payment_dict.get("tax_percent", 0.0),
    )

    # Ensure payee_due_date is converted to datetime
    if isinstance(payment_dict["payee_due_date"], date):
        payment_dict["payee_due_date"] = datetime.combine(
            payment_dict["payee_due_date"], datetime.min.time()
        )

    # Ensure transaction_id is unique
    payment_dict["transaction_id"] = payment_dict.get(
        "transaction_id") or str(uuid.uuid4())

    try:
        # Update the document in the database
        result = payments_collection.update_one(
            {"_id": ObjectId(id)}, {"$set": payment_dict})
        return {"id": str(result.upserted_id)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {e.details.get('errmsg')}"
        )


@router.delete("/{id}")
async def delete_payment(id: str):
    result = payments_collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 1:
        # Delete the evidence file
        evidence_collection.delete_one({"payment_id": ObjectId(id)})
        return {"message": "Success"}
    else:
        raise HTTPException(status_code=404, detail="Error")


@router.delete("/")
async def delete_all_payments():
    payments_collection.delete_many({})
    evidence_collection.delete_many({})
    return {"message": "All payments deleted"}


@router.post("/upload/{id}")
async def upload_evidence(id: str, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Error: Unsupported file type: {file.content_type}.\
                Allowed types are pdf, png, or jpg.",
        )

    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=400, detail="Error :Invalid ID format.")

    try:
        evidence_document = {
            "payment_id": ObjectId(id),
            "file_content": await file.read(),
            "filename": file.filename,
            "content_type": file.content_type,
        }
        evidence_collection.insert_one(
            evidence_document)

        # Update the payment status to completed
        update_result = payments_collection.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "payee_payment_status": "completed",
                }
            },
        )

        if update_result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Error : Payment not found.")

        return {
            "message": "File uploaded, payee payment status is completed.",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error: {str(e)}")


@router.get("/download/{evidence_id}")
async def download_evidence(evidence_id: str):
    if not ObjectId.is_valid(evidence_id):
        raise HTTPException(
            status_code=400, detail="Error : Invalid ID format.")

    try:
        evidence = evidence_collection.find_one(
            {"payment_id": ObjectId(evidence_id)})

        if not evidence:
            raise HTTPException(
                status_code=404, detail="Error: File not found.")

        file_content = evidence["file_content"]
        filename = evidence["filename"]
        content_type = evidence["content_type"]

        return StreamingResponse(
            iter([file_content]),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error: {str(e)}")
