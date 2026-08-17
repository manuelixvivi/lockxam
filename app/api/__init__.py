from app.api.academic import router as academic_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.license import router as license_router
from app.api.master import router as master_router
from app.api.school import router as school_router

__all__ = [
    "auth_router",
    "health_router",
    "master_router",
    "school_router",
    "license_router",
    "academic_router",
]
