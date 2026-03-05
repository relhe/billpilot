from fastapi import FastAPI
from app.routes.payment_routes import router as payment_router
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import config

app = FastAPI(
    title=config["app"]["name"],
    version=config["app"]["version"],
)

cors_cfg = config["cors"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_cfg["allowed_origins"],
    allow_credentials=cors_cfg["allow_credentials"],
    allow_methods=cors_cfg["allow_methods"],
    allow_headers=cors_cfg["allow_headers"],
)

app.include_router(payment_router, prefix="/api", tags=["Payments"])
