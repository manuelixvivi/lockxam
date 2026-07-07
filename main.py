from fastapi import FastAPI
from sqlalchemy import text

from app import (
    models as _models,  # noqa: F401  # Ensure all SQLAlchemy models are registered with Base.metadata
)
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.database import Base, engine
from app.exceptions import register_exception_handlers
from app.middleware import RequestContextMiddleware

# Ensure all database tables exist (e.g. login_attempts)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EquiGrade API", version="1.0.0")

# Register RequestContextMiddleware for tracking latency, Request ID, IP, user agent
app.add_middleware(RequestContextMiddleware)

# Register global exception handlers for application exceptions
register_exception_handlers(app)

app.include_router(health_router)


@app.get("/")
async def root():
    return {"message": "EquiGrade API Running"}


@app.get("/health/db")
async def db_health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return {"status": "connected"}


app.include_router(auth_router)
