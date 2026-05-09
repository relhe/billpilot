from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config.database import get_db
from app.config.settings import get_settings
from app.repositories.evidence_repository import EvidenceRepository

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness(db=Depends(get_db)):
    detail = {}
    settings = get_settings()

    # Check MongoDB
    try:
        if db is None:
            raise RuntimeError("DB not initialized")
        await db.command("ping")
        detail["mongodb"] = "ok"
    except Exception as exc:
        detail["mongodb"] = str(exc)

    # Check S3
    try:
        evidence_repo = EvidenceRepository(settings)
        s3_ok = await evidence_repo.check_connectivity()
        detail["s3"] = "ok" if s3_ok else "unreachable"
    except Exception as exc:
        detail["s3"] = str(exc)

    all_ok = all(v == "ok" for v in detail.values())
    http_status = 200 if all_ok else 503
    return JSONResponse(
        status_code=http_status,
        content={"status": "ok" if all_ok else "degraded", "detail": detail},
    )
