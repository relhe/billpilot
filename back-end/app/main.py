from fastapi import FastAPI
from app.routes.payment_routes import router as payment_router

app = FastAPI()

app.include_router(payment_router, prefix="/payments", tags=["Payments"])
