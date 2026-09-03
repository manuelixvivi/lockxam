from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.common.import_validation import ImportResponse
from app.schemas.school.student import (
    StudentAccountResponse,
    StudentBulkImportRequest,
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
        raise BusinessException("Admin account is not associated with any school.", status_code=400)
    return school_id


@router.get("", response_model=list[StudentAccountResponse])
def list_students(
    limit: int | None = None,
    skip: int = 0,
    search: str | None = None,
    class_name: str | None = None,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    return SchoolStudentService.list_students(
        db, school_id, limit=limit, skip=skip, search=search, class_name=class_name
    )


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
    student, new_password = SchoolStudentService.reset_student_password(db, school_id, public_id)
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


@router.post("/{public_id}/clear-sessions", status_code=status.HTTP_200_OK)
def clear_student_sessions(
    request: Request,
    public_id: str,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from datetime import datetime, timezone
    from uuid import UUID

    from app.models.exam.device_session import DeviceSession
    from app.models.exam.enums import DeviceSessionStatus
    from app.models.exam.exam_checkin import ExamCheckin
    from app.models.security.auth_account import AuthAccount
    from app.models.security.enums import UserRole
    from app.models.security.user_session import UserSession

    try:
        student_uuid = UUID(public_id)
    except ValueError:
        raise BusinessException("Format ID siswa tidak valid.", status_code=400)

    student_acc = (
        db.query(AuthAccount)
        .filter(
            AuthAccount.public_id == student_uuid,
            AuthAccount.school_id == school_id,
            AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
        )
        .first()
    )
    if not student_acc:
        raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

    now = datetime.now(timezone.utc)

    # 1. Revoke User Sessions (Auth)
    sessions = (
        db.query(UserSession)
        .filter(
            UserSession.auth_account_id == student_acc.id,
            UserSession.revoked == False,
        )
        .all()
    )
    for s in sessions:
        s.revoked = True
        s.revoked_at = now
        s.revoked_reason = "ADMIN_CLEAR_SESSIONS"

    # 2. Invalidate Device Sessions (Exam)
    from app.models.exam.exam_attempt import ExamAttempt

    attempt_ids = [
        a.id
        for a in db.query(ExamAttempt.id).filter(ExamAttempt.student_id == student_acc.id).all()
    ]
    if attempt_ids:
        devices = (
            db.query(DeviceSession)
            .filter(
                DeviceSession.exam_attempt_id.in_(attempt_ids),
                DeviceSession.status != DeviceSessionStatus.INVALIDATED,
            )
            .all()
        )
        for d in devices:
            d.status = DeviceSessionStatus.INVALIDATED

    # 3. Clear Exam Checkins
    db.query(ExamCheckin).filter(ExamCheckin.student_id == student_acc.id).delete()

    db.commit()

    return {
        "message": f"Riwayat login & pendaftaran perangkat untuk siswa '{student_acc.name or student_acc.username}' berhasil dihapus. Siswa dapat login kembali di HP/perangkat baru.",
        "username": student_acc.username,
    }


@router.post("/import", response_model=ImportResponse[StudentAccountResponse])
def import_students(
    request: Request,
    data: StudentBulkImportRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    from app.schemas.common.import_validation import ImportResponse, ImportRowError

    school_id = _get_school_id(current_user)

    success, students, errors = SchoolStudentService.import_students_xlsx(
        db=db,
        school_id=school_id,
        academic_year_id=data.academic_year_id,
        rows=[row.model_dump() for row in data.rows],
    )

    if not success:
        row_errors = [ImportRowError(**err) for err in errors]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ImportResponse[StudentAccountResponse](
                status="error",
                message="Impor data siswa gagal karena terdapat kesalahan validasi.",
                imported_count=0,
                errors=row_errors,
            ).model_dump(),
        )

    # Successful import: log activity for each student
    for s in students:
        ActivityService.log_activity(
            db=db,
            auth_account_id=int(current_user["sub"]),
            action_type="STUDENT",
            action_name="IMPORT_STUDENT",
            school_id=school_id,
            endpoint=str(request.url.path),
            method=request.method,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"username": s.username},
        )

    db.commit()
    return ImportResponse[StudentAccountResponse](
        status="success",
        message=f"Berhasil mengimpor {len(students)} siswa secara massal.",
        imported_count=len(students),
        data=[StudentAccountResponse.model_validate(s) for s in students],
    )
