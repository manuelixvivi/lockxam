from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.school.student import (
    StudentAccountResponse,
    StudentCreateRequest,
    StudentCreateResponse,
    StudentResetPasswordResponse,
    StudentUpdateRequest,
)
from app.services.school.student_service import SchoolStudentService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/admin/students", tags=["School Admin — Students"])


def _get_school_id(current_user: dict) -> int:
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException(
            "Admin account is not associated with any school.", status_code=400
        )
    return school_id


@router.get("", response_model=list[StudentAccountResponse])
def list_students(
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    return SchoolStudentService.list_students(db, school_id)


@router.post("", response_model=StudentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    request: Request,
    data: StudentCreateRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    student, default_password = SchoolStudentService.create_student(
        db=db,
        school_id=school_id,
        nis=data.nis,
        name=data.name,
        nisn=data.nisn,
        birth_date=data.birth_date,
        gender=data.gender,
        class_name=data.class_name,
        registered_year=data.registered_year,
    )
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STUDENT",
        action_name="CREATE_STUDENT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"username": student.username},
    )
    db.commit()
    return StudentCreateResponse(account=student, default_password=default_password)


@router.put("/{public_id}", response_model=StudentAccountResponse)
def update_student(
    request: Request,
    public_id: str,
    data: StudentUpdateRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    update_fields = set(data.model_fields_set)
    student = SchoolStudentService.update_student(
        db=db,
        school_id=school_id,
        student_public_id=public_id,
        name=data.name,
        nisn=data.nisn,
        nis=data.nis,
        birth_date=data.birth_date,
        gender=data.gender,
        class_name=data.class_name,
        registered_year=data.registered_year,
        is_active=data.is_active,
        update_fields=update_fields,
    )
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STUDENT",
        action_name="UPDATE_STUDENT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"student_public_id": public_id},
    )
    db.commit()
    return student


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    SchoolStudentService.delete_student(db=db, school_id=school_id, student_public_id=public_id)
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STUDENT",
        action_name="DELETE_STUDENT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"student_public_id": public_id},
    )
    db.commit()


@router.post("/{public_id}/toggle-active", response_model=StudentAccountResponse)
def toggle_student_active(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    student = SchoolStudentService.toggle_student_active(db, school_id, public_id)
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STUDENT",
        action_name="TOGGLE_STUDENT_ACTIVE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"student_public_id": public_id, "is_active": student.is_active},
    )
    db.commit()
    return student


@router.post("/{public_id}/reset-password", response_model=StudentResetPasswordResponse)
def reset_student_password(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    student, new_password = SchoolStudentService.reset_student_password(
        db, school_id, public_id
    )
    ActivityService.log_activity(
        db=db,
        auth_account_id=int(current_user["sub"]),
        action_type="STUDENT",
        action_name="RESET_STUDENT_PASSWORD",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"student_public_id": public_id},
    )
    db.commit()
    return StudentResetPasswordResponse(
        message="Kata sandi siswa berhasil direset.",
        username=student.username,
        new_password=new_password,
    )
