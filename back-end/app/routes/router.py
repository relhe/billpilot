from fastapi import APIRouter
from app.routes.v1.auth_routes import router as auth_router
from app.routes.v1.payment_routes import router as payment_router
from app.routes.v1.health_routes import router as health_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(payment_router)
v1_router.include_router(health_router)
