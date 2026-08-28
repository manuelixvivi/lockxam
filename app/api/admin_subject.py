from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.academic.admin_academic import (
    SubjectBulkDeactivateRequest,
    SubjectBulkDeleteRequest,
    SubjectCreateRequest,
    SubjectImportRequest,
    SubjectResponse,
    SubjectUpdateRequest,
    TeacherCandidateResponse,
    TeacherSubjectResponse,
)
from app.schemas.common.import_validation import ImportResponse
from app.services.academic.subject_service import SubjectService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/admin/subjects", tags=["School Admin — Subjects"])


def _get_school_id(current_user: dict) -> int:
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Akun admin tidak terikat dengan sekolah manapun.", status_code=400)
    return school_id


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    data: SubjectCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    subj = SubjectService.create_subject(
        db=db,
        school_id=school_id,
        code=data.code,
        name=data.name,
        description=data.description,
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SUBJECT",
        action_name="CREATE_SUBJECT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"subject_id": subj.id, "code": subj.code, "name": subj.name},
    )
    db.commit()
    return subj


@router.get("", response_model=list[SubjectResponse])
def list_subjects(
    is_active: bool | None = None,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    return SubjectService.list_subjects(db=db, school_id=school_id, is_active=is_active)


@router.get("/{public_id}", response_model=SubjectResponse)
def get_subject(
    public_id: UUID,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.subject_repository import subject_repository

    subj = subject_repository.get_by_public_id(db, public_id)
    if not subj or subj.school_id != school_id:
        raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)
    return subj


@router.put("/{public_id}", response_model=SubjectResponse)
def update_subject(
    public_id: UUID,
    data: SubjectUpdateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    subj = SubjectService.update_subject(
        db=db,
        school_id=school_id,
        public_id=public_id,
        code=data.code,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SUBJECT",
        action_name="UPDATE_SUBJECT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"subject_id": subj.id, "code": subj.code, "name": subj.name},
    )
    db.commit()
    return subj


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    SubjectService.delete_subject(db=db, school_id=school_id, public_id=public_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SUBJECT",
        action_name="DELETE_SUBJECT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"subject_public_id": str(public_id)},
    )
    db.commit()


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
def bulk_delete_subjects(
    data: SubjectBulkDeleteRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.subject_repository import subject_repository

    for sid in data.subject_ids:
        subj = subject_repository.get_by_id(db, sid)
        if subj and subj.school_id == school_id:
            SubjectService.delete_subject(db=db, school_id=school_id, public_id=subj.public_id)
    db.commit()


@router.post("/bulk-deactivate", status_code=status.HTTP_204_NO_CONTENT)
def bulk_deactivate_subjects(
    data: SubjectBulkDeactivateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.subject_repository import subject_repository

    for sid in data.subject_ids:
        subj = subject_repository.get_by_id(db, sid)
        if subj and subj.school_id == school_id:
            subj.is_active = False
    db.commit()


@router.post("/bulk-activate", status_code=status.HTTP_204_NO_CONTENT)
def bulk_activate_subjects(
    data: SubjectBulkDeactivateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.subject_repository import subject_repository

    for sid in data.subject_ids:
        subj = subject_repository.get_by_id(db, sid)
        if subj and subj.school_id == school_id:
            subj.is_active = True
    db.commit()


# ── Teacher Subject Competency Mapping ──


@router.post("/{subject_id}/teachers/{teacher_id}", response_model=TeacherSubjectResponse)
def assign_teacher_competency(
    subject_id: int,
    teacher_id: int,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    ts = SubjectService.assign_teacher_competency(
        db=db, school_id=school_id, teacher_id=teacher_id, subject_id=subject_id
    )

    from app.repositories.academic.subject_repository import subject_repository
    from app.repositories.security.auth_repository import auth_repository

    teacher = auth_repository.get_by_id(db, teacher_id)
    subj = subject_repository.get_by_id(db, subject_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SUBJECT",
        action_name="ASSIGN_TEACHER_COMPETENCY",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"subject_id": subject_id, "teacher_id": teacher_id},
    )
    db.commit()

    return TeacherSubjectResponse(
        id=ts.id,
        school_id=ts.school_id,
        teacher_id=ts.teacher_id,
        subject_id=ts.subject_id,
        created_at=ts.created_at,
        teacher_name=teacher.name if teacher else None,
        teacher_username=teacher.username if teacher else None,
        subject_code=subj.code if subj else None,
        subject_name=subj.name if subj else None,
    )


@router.delete("/{subject_id}/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_teacher_competency(
    subject_id: int,
    teacher_id: int,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    from app.repositories.academic.subject_repository import subject_repository
    from app.repositories.security.auth_repository import auth_repository

    teacher = auth_repository.get_by_id(db, teacher_id)
    subj = subject_repository.get_by_id(db, subject_id)
    if not teacher or teacher.school_id != school_id:
        raise BusinessException("Guru tidak ditemukan.", status_code=404)
    if not subj or subj.school_id != school_id:
        raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

    SubjectService.unassign_teacher_competency(db=db, teacher_id=teacher_id, subject_id=subject_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SUBJECT",
        action_name="UNASSIGN_TEACHER_COMPETENCY",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"subject_id": subject_id, "teacher_id": teacher_id},
    )
    db.commit()


@router.get("/{subject_id}/teachers", response_model=list[TeacherCandidateResponse])
def list_qualified_teachers(
    subject_id: int,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    teachers = SubjectService.list_qualified_teachers_for_subject(
        db=db, school_id=school_id, subject_id=subject_id
    )
    return [
        TeacherCandidateResponse(
            teacher_id=t.id,
            public_id=t.public_id,
            name=t.name or t.username,
            username=t.username,
            nip=t.nip,
            is_active=t.is_active,
            status="ACTIVE" if t.is_active else "INACTIVE",
        )
        for t in teachers
    ]


@router.post("/import", response_model=ImportResponse[SubjectResponse])
def import_subjects(
    request: Request,
    data: SubjectImportRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    from app.schemas.common.import_validation import ImportResponse, ImportRowError

    school_id = _get_school_id(current_user)

    subjects_list = [subj.model_dump() for subj in data.subjects]

    success, created_subjects, errors = SubjectService.import_subjects_xlsx(
        db=db,
        school_id=school_id,
        subjects_data=subjects_list,
    )

    if not success:
        row_errors = [ImportRowError(**err) for err in errors]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ImportResponse(
                status="error",
                message="Impor mata pelajaran gagal karena terdapat kesalahan validasi.",
                imported_count=0,
                errors=row_errors,
            ).model_dump(),
        )

    # Logging activity
    user_id = int(current_user["sub"])
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SUBJECT",
        action_name="IMPORT_SUBJECT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"subjects_count": len(created_subjects)},
    )

    db.commit()

    return ImportResponse[SubjectResponse](
        status="success",
        message=f"Berhasil menyinkronkan {len(created_subjects)} mata pelajaran secara massal.",
        imported_count=len(created_subjects),
        data=created_subjects,
    )

# Batch 3 Bulk Import Remediation Verified

