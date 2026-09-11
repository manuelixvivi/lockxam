import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

# Ensure uploads directory exists
try:
    os.makedirs("uploads/questions", exist_ok=True)
except Exception:
    pass

from app import (
    models as _models,  # noqa: F401  # Ensure all SQLAlchemy models are registered with Base.metadata
)
from app.api.academic import router as academic_router
from app.api.admin_class import router as admin_class_router
from app.api.admin_exam_schedule import router as admin_exam_schedule_router
from app.api.admin_subject import router as admin_subject_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.exam import router as exam_router
from app.api.exam_command import router as exam_command_router
from app.api.health import router as health_router
from app.api.license import router as license_router
from app.api.master import router as master_router
from app.api.proctor import router as proctor_router
from app.api.school import router as school_router
from app.api.school_staff import router as school_staff_router
from app.api.school_student import router as school_student_router
from app.api.superadmin_ai import router as superadmin_ai_router
from app.api.teacher import dashboard_router, questions_router
from app.api.teacher import router as teacher_router
from app.core.database import Base, SessionLocal, engine
from app.core.environment import is_production_environment
from app.database.seed_master import seed_master_data
from app.exceptions import register_exception_handlers
from app.logging.logger import logger
from app.middleware import RequestContextMiddleware

# Production-safe schema initialization:
# Default is strictly "false". Table creation in production/staging environments
# MUST run authoritatively via Alembic migrations (`alembic upgrade head`).
should_auto_migrate = os.getenv("AUTO_CREATE_TABLES", "false").lower() in ("true", "1", "yes")

if should_auto_migrate:
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            seed_master_data(db)
        finally:
            db.close()
    except Exception as _err:
        logger.warning(f"Deferred DB init on import: {_err}")

app = FastAPI(title="EquiGrade API", version="1.0.0")

# Enforce fail-fast configuration checks on production startup
if is_production_environment():
    from app.core.security.keys import get_ai_webhook_secret
    get_ai_webhook_secret()


# Serve uploaded static files securely
try:
    os.makedirs("uploads/questions", exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
except Exception as _static_err:
    logger.warning(f"Static files mount skipped: {_static_err}")

# Register RequestContextMiddleware for tracking latency, Request ID, IP, user agent
app.add_middleware(RequestContextMiddleware)

# Production-hardened CORS policy:
# Enforces explicit allowlist in production, disallows wildcard Vercel subdomain regex by default.
raw_origins = os.getenv("ALLOWED_ORIGINS", "")
if is_production_environment():
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    allow_origin_regex = os.getenv("CORS_ORIGIN_REGEX", None)
else:
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    allow_origin_regex = os.getenv("CORS_ORIGIN_REGEX", None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Device-Id",
        "X-Device-Token",
        "X-Request-ID",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)

# Register global exception handlers for application exceptions
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(health_router, prefix="/api/v1")


@app.get("/api/info")
async def root_info():
    return {"status": "ok", "app": "EquiGrade x Lockxam API"}


@app.get("/health/db")
async def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.error(f"Health check DB probe failed: {exc}")
        raise HTTPException(status_code=503, detail="Database connectivity failure")


app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(master_router)
app.include_router(school_router)
app.include_router(license_router)
app.include_router(academic_router)
app.include_router(teacher_router)
app.include_router(questions_router)
app.include_router(dashboard_router)
app.include_router(proctor_router)
app.include_router(exam_router)
app.include_router(exam_command_router)
app.include_router(school_staff_router)
app.include_router(school_student_router)
app.include_router(admin_subject_router)
app.include_router(admin_class_router)
app.include_router(admin_exam_schedule_router)
app.include_router(superadmin_ai_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "EquiGrade API", "version": "1.0.0"}


# Mount Built Frontend Dist static files for Single-Port Production Serving only if explicitly enabled
from fastapi.responses import FileResponse  # noqa: E402

serve_spa_enabled = os.getenv("SERVE_SPA", "false").lower() in ("true", "1", "yes")

dist_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if serve_spa_enabled and os.path.exists(dist_path):
    assets_path = os.path.join(dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="dist_assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if (
            full_path.startswith("api")
            or full_path.startswith("uploads")
            or full_path.startswith("health")
        ):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not Found")
        target_file = os.path.join(dist_path, full_path)
        if full_path and os.path.isfile(target_file):
            return FileResponse(target_file)
        return FileResponse(os.path.join(dist_path, "index.html"))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
