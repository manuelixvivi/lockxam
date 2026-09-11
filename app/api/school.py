from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_authenticated, require_staff, require_superadmin
from app.exceptions.base import BusinessException
from app.models.security.enums import UserRole
from app.schemas.school.school import (
    PaginatedSchoolResponse,
    SchoolCreateRequest,
    SchoolCreateResponse,
    SchoolResponse,
    SchoolUpdateRequest,
    SuperAdminDashboardSummaryResponse,
)
from app.services.school.school_service import SchoolService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/schools", tags=["School Management"])


@router.get(
    "/superadmin/dashboard-summary",
    response_model=SuperAdminDashboardSummaryResponse,
    dependencies=[Depends(require_superadmin())],
)
def get_superadmin_dashboard_summary(db: Session = Depends(get_db)):
    return SchoolService.get_superadmin_dashboard_summary(db)


@router.get(
    "/paginated",
    response_model=PaginatedSchoolResponse,
    dependencies=[Depends(require_superadmin())],
)
def list_schools_paginated(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    limit = max(1, min(page_size, 100))
    skip = (max(1, page) - 1) * limit
    schools, total = SchoolService.list_schools_paginated(
        db, limit=limit, skip=skip, search=search
    )
    return {
        "items": schools,
        "total": total,
        "page": page,
        "page_size": limit,
    }


@router.post(
    "",
    response_model=SchoolCreateResponse,
    status_code=201,
)
def create_school(
    request: Request,
    data: SchoolCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_superadmin()),
):
    school = SchoolService.create_school(db, data)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="SCHOOL",
        action_name="CREATE_SCHOOL",
        school_id=school.id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"npsn": school.npsn, "name": school.name},
    )

    return {
        "school": school,
        "admin_credentials": {
            "username": getattr(school, "admin_username", None),
            "temporary_password": getattr(school, "temporary_password", ""),
        },
    }


@router.get(
    "",
    response_model=list[SchoolResponse],
    dependencies=[Depends(require_superadmin())],
)
def list_schools(
    limit: int | None = None,
    skip: int = 0,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    if limit is not None or search is not None:
        schools, _ = SchoolService.list_schools_paginated(
            db, limit=limit or 50, skip=skip, search=search
        )
        return schools
    return SchoolService.get_all_schools(db)


@router.get(
    "/{identifier}",
    response_model=SchoolResponse,
)
def get_school(
    identifier: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_authenticated()),
):
    school = SchoolService.get_school_by_id_or_public_id(db, identifier)
    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")

    if user_role not in [UserRole.SUPERADMIN, "SUPERADMIN"]:
        if not user_school_id or school.id != user_school_id:
            raise BusinessException(
                "Akses ditolak: Anda tidak memiliki akses ke profil sekolah ini.",
                status_code=403,
            )
    return school


@router.get(
    "/{identifier}/dashboard-summary",
)
def get_school_dashboard_summary(
    identifier: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_authenticated()),
):
    school = SchoolService.get_school_by_id_or_public_id(db, identifier)
    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")

    if user_role not in [UserRole.SUPERADMIN, "SUPERADMIN"]:
        if not user_school_id or school.id != user_school_id:
            raise BusinessException(
                "Akses ditolak: Anda tidak memiliki akses ke ringkasan sekolah ini.",
                status_code=403,
            )
    return SchoolService.get_dashboard_summary(db, identifier)



@router.put(
    "/{public_id}",
    response_model=SchoolResponse,
)
def update_school_full(
    request: Request,
    public_id: UUID,
    data: SchoolUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_superadmin()),
):
    school = SchoolService.update_school(db, public_id, data)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="SCHOOL",
        action_name="UPDATE_SCHOOL_FULL",
        school_id=school.id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"npsn": school.npsn, "name": school.name},
    )

    return school


@router.patch(
    "/{public_id}",
    response_model=SchoolResponse,
)
def update_school_partial(
    request: Request,
    public_id: UUID,
    data: SchoolUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_staff()),
):
    target_school = SchoolService.get_school_by_public_id(db, public_id)
    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")

    if user_role in [UserRole.ADMIN, "SCHOOL_ADMIN"]:
        if target_school.id != user_school_id:
            raise BusinessException(
                "You are not authorized to update another school's profile", status_code=403
            )
        if (
            data.npsn is not None
            or data.code is not None
            or data.name is not None
            or data.is_active is not None
        ):
            raise BusinessException(
                "School Admin cannot modify locked fields (NPSN, Code, Name, Active Status). Contact SuperAdmin.",
                status_code=403,
            )

    school = SchoolService.update_school(db, public_id, data)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="SCHOOL",
        action_name="UPDATE_SCHOOL_PARTIAL",
        school_id=school.id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"npsn": school.npsn, "name": school.name},
    )

    return school


@router.delete(
    "/{public_id}",
)
def delete_school(
    request: Request,
    public_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_superadmin()),
):
    # Fetch school to log details
    school = SchoolService.get_school_by_public_id(db, public_id)

    SchoolService.delete_school(db, public_id)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="SCHOOL",
        action_name="DELETE_SCHOOL",
        school_id=school.id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"npsn": school.npsn, "name": school.name},
    )

    return {"message": "School successfully deleted"}


@router.post(
    "/{public_id}/reset-admin-password",
)
def reset_admin_password(
    request: Request,
    public_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_superadmin()),
):
    admin_username, new_password = SchoolService.reset_school_admin_password(db, public_id)
    school = SchoolService.get_school_by_public_id(db, public_id)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="SCHOOL",
        action_name="RESET_SCHOOL_ADMIN_PASSWORD",
        school_id=school.id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"npsn": school.npsn, "admin_username": admin_username},
    )

    return {
        "message": "Kata sandi Admin Sekolah berhasil diperbarui.",
        "username": admin_username,
        "new_password": new_password,
    }


@router.post(
    "/{public_id}/toggle-subscription",
    response_model=SchoolResponse,
)
def toggle_school_subscription(
    request: Request,
    public_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_superadmin()),
):
    school, new_status = SchoolService.toggle_school_subscription(db, public_id)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="SCHOOL",
        action_name="TOGGLE_SCHOOL_SUBSCRIPTION",
        school_id=school.id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"npsn": school.npsn, "new_subscription_status": new_status},
    )

    return school
