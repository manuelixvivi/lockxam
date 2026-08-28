from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.common.import_validation import ImportResponse
from app.schemas.school.staff import (
    ResetPasswordResponse,
    StaffAccountResponse,
    TeacherCreateRequest,
    TeacherCreateResponse,
    TeacherImportRequest,
    TeacherUpdateRequest,
)
from app.services.school.staff_service import SchoolStaffService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/admin/teachers", tags=["School Admin — Teachers"])


def _get_school_id(current_user: dict) -> int:
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Admin account is not associated with any school.", status_code=400)
    return school_id


@router.get("", response_model=list[StaffAccountResponse])
def list_teachers(
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    return SchoolStaffService.list_teachers(db, school_id)


@router.post("", response_model=TeacherCreateResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    request: Request,
    data: TeacherCreateRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    teacher, default_password = SchoolStaffService.create_teacher(
        db=db,
        school_id=school_id,
        name=data.name,
        nip=data.nip,
        gender=data.gender,
        registered_year=data.registered_year,
        classes_taught=data.classes_taught,
        # subjects_taught intentionally omitted: assign competency via TeacherSubject endpoint.
        teacher_code=data.teacher_code,
    )
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STAFF",
        action_name="CREATE_TEACHER",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"username": teacher.username},
    )
    db.commit()
    return TeacherCreateResponse(account=teacher, default_password=default_password)


@router.put("/{public_id}", response_model=StaffAccountResponse)
def update_teacher(
    request: Request,
    public_id: str,
    data: TeacherUpdateRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    teacher = SchoolStaffService.update_teacher(
        db=db,
        school_id=school_id,
        teacher_public_id=public_id,
        name=data.name,
        nip=data.nip,
        gender=data.gender,
        registered_year=data.registered_year,
        classes_taught=data.classes_taught,
        # subjects_taught intentionally omitted: competency managed via TeacherSubject endpoint only.
        is_active=data.is_active,
        teacher_code=data.teacher_code,
    )
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STAFF",
        action_name="UPDATE_TEACHER",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"teacher_public_id": public_id},
    )
    db.commit()
    return teacher


@router.post("/{public_id}/toggle-active", response_model=StaffAccountResponse)
def toggle_teacher_active(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    teacher = SchoolStaffService.toggle_teacher_active(db, school_id, public_id)
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STAFF",
        action_name="TOGGLE_TEACHER_ACTIVE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"teacher_public_id": public_id, "is_active": teacher.is_active},
    )
    db.commit()
    return teacher


@router.post("/{public_id}/reset-password", response_model=ResetPasswordResponse)
def reset_teacher_password(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    teacher, new_password = SchoolStaffService.reset_teacher_password(db, school_id, public_id)
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STAFF",
        action_name="RESET_TEACHER_PASSWORD",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"teacher_public_id": public_id},
    )
    db.commit()
    return ResetPasswordResponse(
        message="Kata sandi guru berhasil direset.",
        username=teacher.username,
        new_password=new_password,
    )


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    SchoolStaffService.delete_teacher(db=db, school_id=school_id, teacher_public_id=public_id)
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STAFF",
        action_name="DELETE_TEACHER",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"teacher_public_id": public_id},
    )
    db.commit()


@router.post("/import", response_model=ImportResponse[StaffAccountResponse])
def import_teachers(
    request: Request,
    data: TeacherImportRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    from app.schemas.common.import_validation import ImportResponse, ImportRowError

    school_id = _get_school_id(current_user)

    teachers_list = [teacher.model_dump() for teacher in data.teachers]

    success, created_teachers, errors = SchoolStaffService.import_teachers_xlsx(
        db=db,
        school_id=school_id,
        teachers_data=teachers_list,
    )

    if not success:
        row_errors = [ImportRowError(**err) for err in errors]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ImportResponse(
                status="error",
                message="Impor guru gagal karena terdapat kesalahan validasi.",
                imported_count=0,
                errors=row_errors,
            ).model_dump(),
        )

    # Logging activity
    user_id = int(current_user["sub"])
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="STAFF",
        action_name="IMPORT_TEACHER",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"teachers_count": len(created_teachers)},
    )

    db.commit()

    return ImportResponse[StaffAccountResponse](
        status="success",
        message=f"Berhasil menyinkronkan {len(created_teachers)} guru secara massal.",
        imported_count=len(created_teachers),
        data=created_teachers,
    )
