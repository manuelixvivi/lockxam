from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.academic.admin_academic import (
    ExamScheduleCreateRequest,
    ExamSchedulePackageCreateRequest,
    ExamSchedulePackageResponse,
    ExamScheduleProctorAssignRequest,
    ExamScheduleResponse,
    ExamScheduleUpdateRequest,
)
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/admin/exam-schedules", tags=["School Admin — Exam Schedules"])


def _get_school_id(current_user: dict) -> int:
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException("Akun admin tidak terikat dengan sekolah manapun.", status_code=400)
    return school_id


def _bulk_enrich_schedules(db: Session, schedules: list) -> list[ExamScheduleResponse]:
    if not schedules:
        return []

    from app.models.academic.academic_semester import AcademicSemester
    from app.models.academic.academic_year import AcademicYear
    from app.models.academic.class_entity import ClassEntity
    from app.models.academic.subject import Subject
    from app.models.security.auth_account import AuthAccount

    year_ids = {s.academic_year_id for s in schedules if s.academic_year_id}
    sem_ids = {s.academic_semester_id for s in schedules if s.academic_semester_id}
    class_ids = {s.class_id for s in schedules if s.class_id}
    subj_ids = {s.subject_id for s in schedules if s.subject_id}
    user_ids = {s.teacher_id for s in schedules if s.teacher_id} | {
        s.proctor_id for s in schedules if s.proctor_id
    }

    years = (
        {y.id: y for y in db.query(AcademicYear).filter(AcademicYear.id.in_(year_ids)).all()}
        if year_ids
        else {}
    )
    sems = (
        {
            sem.id: sem
            for sem in db.query(AcademicSemester).filter(AcademicSemester.id.in_(sem_ids)).all()
        }
        if sem_ids
        else {}
    )
    classes = (
        {c.id: c for c in db.query(ClassEntity).filter(ClassEntity.id.in_(class_ids)).all()}
        if class_ids
        else {}
    )
    subjects = (
        {sub.id: sub for sub in db.query(Subject).filter(Subject.id.in_(subj_ids)).all()}
        if subj_ids
        else {}
    )
    users = (
        {u.id: u for u in db.query(AuthAccount).filter(AuthAccount.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    res = []
    for s in schedules:
        year = years.get(s.academic_year_id)
        sem = sems.get(s.academic_semester_id)
        cls = classes.get(s.class_id)
        subj = subjects.get(s.subject_id)
        teacher = users.get(s.teacher_id)
        proctor = users.get(s.proctor_id) if s.proctor_id else None

        res.append(
            ExamScheduleResponse(
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
        )
    return res


def _enrich_schedule_response(db: Session, s) -> ExamScheduleResponse:
    return _bulk_enrich_schedules(db, [s])[0]


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
    if academic_year_id is None:
        from app.repositories.academic.academic_year_repository import academic_year_repository

        active_year = academic_year_repository.get_active_year(db, school_id)
        if active_year:
            academic_year_id = active_year.id

    schedules = ExamScheduleService.list_schedules(
        db=db,
        school_id=school_id,
        academic_year_id=academic_year_id,
        academic_semester_id=academic_semester_id,
        class_id=class_id,
    )
    return _bulk_enrich_schedules(db, schedules)


def _enrich_package_response(db: Session, p) -> ExamSchedulePackageResponse:
    from app.repositories.academic.academic_year_repository import academic_year_repository

    year = academic_year_repository.get_by_id(db, p.academic_year_id)

    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository

    schedules = exam_schedule_repository.list_by_package(db, p.id)
    enriched_schedules = _bulk_enrich_schedules(db, schedules)

    is_closed_val = bool(getattr(p, "is_closed", False))
    if not is_closed_val and schedules:
        is_closed_val = all(
            s.status in ["COMPLETED", "CLOSED", "ARCHIVED", "CANCELLED", "FINISHED"]
            for s in schedules
        )

    now_utc = datetime.now(timezone.utc)
    return ExamSchedulePackageResponse(
        id=p.id,
        public_id=p.public_id,
        school_id=p.school_id,
        academic_year_id=p.academic_year_id,
        title=p.title,
        is_closed=is_closed_val,
        created_at=p.created_at or now_utc,
        updated_at=p.updated_at or now_utc,
        academic_year_name=year.name if year else None,
        schedules=enriched_schedules,
    )


@router.post(
    "/packages", response_model=ExamSchedulePackageResponse, status_code=status.HTTP_201_CREATED
)
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
    db.refresh(package)
    return _enrich_package_response(db, package)


@router.get("/packages", response_model=list[ExamSchedulePackageResponse])
def list_exam_schedule_packages(
    academic_year_id: int | None = None,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    if academic_year_id is None:
        from app.repositories.academic.academic_year_repository import academic_year_repository

        active_year = academic_year_repository.get_active_year(db, school_id)
        if active_year:
            academic_year_id = active_year.id

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


@router.post("/packages/{public_id}/close", response_model=ExamSchedulePackageResponse)
def close_exam_schedule_package(
    public_id: UUID,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    package = ExamScheduleService.get_schedule_package(db, school_id, public_id)
    package.is_closed = True

    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository

    schedules = exam_schedule_repository.list_by_package(db, package.id)
    for sch in schedules:
        if sch.status != "CANCELLED":
            sch.status = "COMPLETED"
    db.commit()
    return _enrich_package_response(db, package)


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
