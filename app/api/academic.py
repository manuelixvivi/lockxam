from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_academic_staff, require_admin
from app.exceptions.base import BusinessException
from app.repositories.academic.academic_semester_repository import academic_semester_repository
from app.repositories.academic.academic_year_repository import academic_year_repository
from app.schemas.academic.academic import (
    AcademicSemesterCreateRequest,
    AcademicSemesterResponse,
    AcademicYearCreateRequest,
    AcademicYearResponse,
)
from app.services.academic.academic_service import AcademicService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/academic", tags=["Academic Periods"])


@router.post("/years", response_model=AcademicYearResponse, status_code=status.HTTP_201_CREATED)
def create_academic_year(
    data: AcademicYearCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])
    year = AcademicService.create_academic_year(
        db=db,
        school_id=school_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.flush()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="CREATE_ACADEMIC_YEAR",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"academic_year_id": year.id},
    )
    db.commit()

    return year


@router.delete("/years/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_academic_year(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])

    # Check that it belongs to the school
    year = academic_year_repository.get_by_public_id(db, public_id)
    if not year or year.school_id != school_id:
        raise BusinessException("Academic Year not found", status_code=404)

    AcademicService.delete_academic_year(db=db, public_id=public_id)

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="DELETE_ACADEMIC_YEAR",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"academic_year_public_id": str(public_id)},
    )
    db.commit()


@router.post("/years/{public_id}/close", response_model=AcademicYearResponse)
def close_academic_year(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])
    year = academic_year_repository.get_by_public_id(db, public_id)
    if not year or year.school_id != school_id:
        raise BusinessException("Academic Year not found", status_code=404)

    closed = AcademicService.close_academic_year(db=db, public_id=public_id)
    db.flush()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="CLOSE_ACADEMIC_YEAR",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"academic_year_id": closed.id},
    )
    db.commit()

    return closed


@router.post("/years/{public_id}/finalize", response_model=AcademicYearResponse)
def finalize_archive(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])
    year = academic_year_repository.get_by_public_id(db, public_id)
    if not year or year.school_id != school_id:
        raise BusinessException("Academic Year not found", status_code=404)

    finalized = AcademicService.finalize_archive(db=db, public_id=public_id)
    db.flush()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="FINALIZE_ARCHIVE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"academic_year_id": finalized.id},
    )
    db.commit()

    return finalized


@router.post("/years/{public_id}/rollover", response_model=AcademicYearResponse)
def rollover_academic_year(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])
    active_year = AcademicService.rollover_academic_year(
        db=db, school_id=school_id, new_year_public_id=public_id
    )
    db.flush()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="ROLLOVER_ACADEMIC_YEAR",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"new_academic_year_id": active_year.id},
    )
    db.commit()

    return active_year


@router.post(
    "/semesters", response_model=AcademicSemesterResponse, status_code=status.HTTP_201_CREATED
)
def create_academic_semester(
    data: AcademicSemesterCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])

    # Check parent year belongs to this school
    year = academic_year_repository.get_by_id(db, data.academic_year_id)
    if not year or year.school_id != school_id:
        raise BusinessException("Academic Year not found", status_code=404)

    semester = AcademicService.create_academic_semester(
        db=db,
        academic_year_id=data.academic_year_id,
        code=data.code,
        display_name=data.display_name,
    )
    db.flush()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="CREATE_ACADEMIC_SEMESTER",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"academic_semester_id": semester.id},
    )
    db.commit()

    return semester


@router.post("/semesters/{public_id}/activate", response_model=AcademicSemesterResponse)
def activate_semester(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school", status_code=400)

    user_id = int(current_user["sub"])

    # Check semester belongs to this school (Refactor 4: Moved db.query join out of API to Repository)
    sem = academic_semester_repository.get_by_public_id_and_school(
        db=db, public_id=public_id, school_id=school_id
    )
    if not sem:
        raise BusinessException("Academic Semester not found", status_code=404)

    activated = AcademicService.activate_semester(db=db, public_id=public_id)
    db.flush()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ACADEMIC",
        action_name="ACTIVATE_SEMESTER",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"academic_semester_id": activated.id},
    )
    db.commit()

    return activated


@router.get("/periods", response_model=list[AcademicYearResponse])
def list_academic_periods(
    current_user=Depends(require_academic_staff()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("User account is not associated with any school", status_code=400)
    return academic_year_repository.get_years_by_school(db=db, school_id=school_id)
