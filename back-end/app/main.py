from fastapi import FastAPI
from app.routes.payment_routes import router as payment_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS settings
origins = [
    "http://localhost:4200", 'www.scholarnethub.com', 'scholarnethub.com'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of allowed origins
    allow_credentials=True,  # Allow cookies and headers like Authorization
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


app.include_router(payment_router, prefix="/payments", tags=["Payments"])
