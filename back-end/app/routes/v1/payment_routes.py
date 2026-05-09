from fastapi import APIRouter, Depends, File, UploadFile, status

from app.auth.dependencies import get_current_user
from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment_schemas import (
    PaginatedResponse,
    PaymentCreate,
    PaymentFilterParams,
    PaymentResponse,
    PaymentUpdate,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


def _get_service(db=Depends(get_db)) -> PaymentService:
    settings = get_settings()
    return PaymentService(
        payment_repo=PaymentRepository(db),
        evidence_repo=EvidenceRepository(settings),
        db=db,
        settings=settings,
    )


@router.get("", response_model=PaginatedResponse[PaymentResponse])
async def list_payments(
    filters: PaymentFilterParams = Depends(),
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    return await service.list_payments(filters, user)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    return await service.get_payment(payment_id, user)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    inserted_id = await service.create_payment(body, user)
    return {"id": inserted_id}


@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: str,
    body: PaymentUpdate,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    return await service.update_payment(payment_id, body, user)


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: str,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    await service.delete_payment(payment_id, user)


@router.post("/{payment_id}/evidence", status_code=status.HTTP_200_OK)
async def upload_evidence(
    payment_id: str,
    file: UploadFile = File(...),
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    await service.upload_evidence(payment_id, file, user)
    return {"message": "Evidence uploaded, payment marked as completed"}


@router.get("/{payment_id}/evidence")
async def download_evidence(
    payment_id: str,
    service: PaymentService = Depends(_get_service),
    user: dict = Depends(get_current_user),
):
    url = await service.download_evidence(payment_id, user)
    return {"download_url": url}
