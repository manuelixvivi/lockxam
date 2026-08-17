from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.academic.admin_academic import (
    ExamScheduleCreateRequest,
    ExamScheduleUpdateRequest,
    ExamScheduleProctorAssignRequest,
    ExamScheduleResponse,
    ExamSchedulePackageCreateRequest,
    ExamSchedulePackageResponse,
)
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/admin/exam-schedules", tags=["School Admin — Exam Schedules"])


def _get_school_id(current_user: dict) -> int:
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException(
            "Akun admin tidak terikat dengan sekolah manapun.", status_code=400
        )
    return school_id


def _enrich_schedule_response(db: Session, s) -> ExamScheduleResponse:
    from app.repositories.academic.academic_semester_repository import academic_semester_repository
    from app.repositories.academic.academic_year_repository import academic_year_repository
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.academic.subject_repository import subject_repository
    from app.repositories.security.auth_repository import auth_repository

    year = academic_year_repository.get_by_id(db, s.academic_year_id)
    sem = academic_semester_repository.get_by_id(db, s.academic_semester_id)
    cls = class_repository.get_by_id(db, s.class_id)
    subj = subject_repository.get_by_id(db, s.subject_id)
    teacher = auth_repository.get_by_id(db, s.teacher_id)
    proctor = auth_repository.get_by_id(db, s.proctor_id) if s.proctor_id else None

    return ExamScheduleResponse(
        id=s.id,
        public_id=s.public_id,
        school_id=s.school_id,
        package_id=s.package_id,
        academic_year_id=s.academic_year_id,
        academic_semester_id=s.academic_semester_id,
        class_id=s.class_id,
        subject_id=s.subject_id,
        teacher_id=s.teacher_id,
        proctor_id=s.proctor_id,
        title=s.title,
        name=s.title,
        start_time=s.start_time,
        end_time=s.end_time,
        duration_minutes=s.duration_minutes,
        status=s.status,
        target_type=getattr(s, "target_type", "ALL_CLASS") or "ALL_CLASS",
        allowed_student_ids=getattr(s, "allowed_student_ids", None),
        created_at=s.created_at,
        updated_at=s.updated_at,
        class_name=cls.name if cls else None,
        subject_name=subj.name if subj else None,
        teacher_name=teacher.name or teacher.username if teacher else None,
        proctor_name=proctor.name or proctor.username if proctor else None,
        proctor_code=proctor.teacher_code if proctor else None,
        academic_year_name=year.name if year else None,
        academic_semester_name=sem.display_name if sem else None,
    )


@router.post("", response_model=ExamScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_exam_schedule(
    data: ExamScheduleCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    title_val = data.title or data.name
    if not title_val or not title_val.strip():
        raise BusinessException("Judul jadwal ujian wajib diisi.", status_code=400)

    schedule = ExamScheduleService.create_exam_schedule(
        db=db,
        school_id=school_id,
        academic_year_id=data.academic_year_id,
        academic_semester_id=data.academic_semester_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        title=title_val,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=data.duration_minutes,
        proctor_id=data.proctor_id,
        package_id=data.package_id,
        target_type=data.target_type,
        allowed_student_ids=data.allowed_student_ids,
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="EXAM_SCHEDULE",
        action_name="CREATE_EXAM_SCHEDULE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"schedule_id": schedule.id, "title": schedule.title},
    )
    db.commit()

    return _enrich_schedule_response(db, schedule)


@router.get("", response_model=list[ExamScheduleResponse])
def list_exam_schedules(
    academic_year_id: int | None = None,
    academic_semester_id: int | None = None,
    class_id: int | None = None,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    schedules = ExamScheduleService.list_schedules(
        db=db,
        school_id=school_id,
        academic_year_id=academic_year_id,
        academic_semester_id=academic_semester_id,
        class_id=class_id,
    )
    return [_enrich_schedule_response(db, s) for s in schedules]


def _enrich_package_response(db: Session, p) -> ExamSchedulePackageResponse:
    from app.repositories.academic.academic_year_repository import academic_year_repository
    year = academic_year_repository.get_by_id(db, p.academic_year_id)
    
    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository
    schedules = exam_schedule_repository.list_by_package(db, p.id)
    enriched_schedules = [_enrich_schedule_response(db, s) for s in schedules]
    
    return ExamSchedulePackageResponse(
        id=p.id,
        public_id=p.public_id,
        school_id=p.school_id,
        academic_year_id=p.academic_year_id,
        title=p.title,
        created_at=p.created_at,
        updated_at=p.updated_at,
        academic_year_name=year.name if year else None,
        schedules=enriched_schedules,
    )


@router.post("/packages", response_model=ExamSchedulePackageResponse, status_code=status.HTTP_201_CREATED)
def create_exam_schedule_package(
    data: ExamSchedulePackageCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    package = ExamScheduleService.create_schedule_package(
        db=db, school_id=school_id, title=data.title, academic_year_id=data.academic_year_id
    )
    db.commit()
    return _enrich_package_response(db, package)


@router.get("/packages", response_model=list[ExamSchedulePackageResponse])
def list_exam_schedule_packages(
    academic_year_id: int | None = None,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    packages = ExamScheduleService.list_schedule_packages(db, school_id, academic_year_id)
    return [_enrich_package_response(db, p) for p in packages]


@router.get("/packages/{public_id}", response_model=ExamSchedulePackageResponse)
def get_exam_schedule_package(
    public_id: UUID,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    package = ExamScheduleService.get_schedule_package(db, school_id, public_id)
    return _enrich_package_response(db, package)


@router.delete("/packages/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam_schedule_package(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    
    ExamScheduleService.delete_schedule_package(db, school_id, public_id)
    db.commit()


@router.post("/packages/{public_id}/import", response_model=list[ExamScheduleResponse])
def import_schedules_xlsx(
    public_id: UUID,
    rows: list[dict],
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    package = ExamScheduleService.get_schedule_package(db, school_id, public_id)
    schedules = ExamScheduleService.import_schedules_xlsx(db, school_id, package.id, rows)
    db.commit()
    return [_enrich_schedule_response(db, s) for s in schedules]


@router.get("/{public_id}", response_model=ExamScheduleResponse)
def get_exam_schedule(
    public_id: UUID,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository
    schedule = exam_schedule_repository.get_by_public_id(db, public_id)
    if not schedule or schedule.school_id != school_id:
        raise BusinessException("Jadwal ujian tidak ditemukan.", status_code=404)
    return _enrich_schedule_response(db, schedule)


@router.put("/{public_id}", response_model=ExamScheduleResponse)
def update_exam_schedule(
    public_id: UUID,
    data: ExamScheduleUpdateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    title_val = data.title or data.name

    schedule = ExamScheduleService.update_exam_schedule(
        db=db,
        school_id=school_id,
        public_id=public_id,
        academic_semester_id=data.academic_semester_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        title=title_val,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=data.duration_minutes,
        proctor_id=data.proctor_id,
        status=data.status,
        target_type=data.target_type,
        allowed_student_ids=data.allowed_student_ids,
        lock_browser=data.lock_browser,
        eyd_language_evaluation=data.eyd_language_evaluation,
        randomize_per_type=data.randomize_per_type,
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="EXAM_SCHEDULE",
        action_name="UPDATE_EXAM_SCHEDULE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"schedule_id": schedule.id, "title": schedule.title},
    )
    db.commit()

    return _enrich_schedule_response(db, schedule)


@router.put("/{public_id}/proctor", response_model=ExamScheduleResponse)
def assign_proctor(
    public_id: UUID,
    data: ExamScheduleProctorAssignRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    schedule = ExamScheduleService.assign_proctor(
        db=db, school_id=school_id, public_id=public_id, proctor_id=data.proctor_id
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="EXAM_SCHEDULE",
        action_name="ASSIGN_PROCTOR",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"schedule_id": schedule.id, "proctor_id": data.proctor_id},
    )
    db.commit()

    return _enrich_schedule_response(db, schedule)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam_schedule(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    ExamScheduleService.delete_exam_schedule(db=db, school_id=school_id, public_id=public_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="EXAM_SCHEDULE",
        action_name="DELETE_EXAM_SCHEDULE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"schedule_public_id": str(public_id)},
    )
    db.commit()
