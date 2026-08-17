import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status, UploadFile, File
from starlette.status import HTTP_403_FORBIDDEN
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.security.enums import UserRole
from app.models.teacher.question import Question
from app.repositories.teacher.question_package_repository import (
    question_package_repository,
)
from app.repositories.teacher.question_repository import (
    question_repository,
)
from app.schemas.teacher import (
    QuestionPackageCreate,
    QuestionPackageResponse,
    QuestionPackageSnapshotPayload,
    QuestionCreateRequest,
    QuestionUpdateRequest,
    TeacherQuestionResponse,
    QuestionPackageDetailResponse,
)
from app.services.teacher.question_package_service import QuestionPackageService

router = APIRouter(prefix="/api/v1/teacher/packages", tags=["Teacher Content — Packages"])
questions_router = APIRouter(prefix="/api/v1/teacher/questions", tags=["Teacher Content — Questions"])
dashboard_router = APIRouter(prefix="/api/v1/teacher", tags=["Teacher Dashboard & Control"])


def require_internal_token(x_internal_service_token: str = Header(None)):
    secret = os.getenv("INTERNAL_SERVICE_TOKEN", "equigrade-internal-secret-token")
    if x_internal_service_token != secret:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Access denied: Internal service only",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Question Packages Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[QuestionPackageResponse])
def list_packages(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
    return question_package_repository.get_by_owner_and_tenant(db, teacher_account_id, school_id)


@router.post("", response_model=QuestionPackageResponse, status_code=status.HTTP_201_CREATED)
def create_package(
    payload: QuestionPackageCreate,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    return QuestionPackageService.create_package(
        db=db,
        name=payload.name,
        class_level=payload.class_level,
        target_counts=payload.target_counts,
        teacher_account_id=teacher_account_id,
        school_id=school_id,
        subject=payload.subject,
    )


@router.get("/{package_id}", response_model=QuestionPackageDetailResponse)
def get_package_detail(
    package_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    package = question_package_repository.get_by_id(db, package_id)
    if (
        not package
        or package.owner_teacher_account_id != teacher_account_id
        or package.school_id != school_id
    ):
        raise HTTPException(status_code=404, detail="Question package not found")

    sorted_items = sorted(package.items, key=lambda x: x.canonical_order)
    questions_payload = []
    for item in sorted_items:
        q = item.question
        questions_payload.append(
            {
                "id": q.id,
                "type": q.type,
                "content": q.content,
                "options": q.options,
                "answer_key": q.answer_key,
                "rubrics": q.rubrics,
                "canonical_order": item.canonical_order,
                "score": item.score,
                "subject": q.subject,
                "ai_grading": q.ai_grading,
            }
        )

    return {
        "id": package.id,
        "school_id": package.school_id,
        "name": package.name,
        "class_level": package.class_level,
        "subject": package.subject,
        "target_counts": package.target_counts,
        "status": package.status,
        "owner_teacher_account_id": package.owner_teacher_account_id,
        "questions": questions_payload,
    }


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(
    package_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    package = question_package_repository.get_by_id(db, package_id)
    if (
        not package
        or package.owner_teacher_account_id != teacher_account_id
        or package.school_id != school_id
    ):
        raise HTTPException(status_code=404, detail="Question package not found")

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_session import ExamSession
    from app.models.academic.exam_snapshot import ExamSnapshot

    # Check if assigned to an ACTIVE/COMPLETED session
    active_session = db.query(ExamSession).join(ExamSchedule).join(ExamSnapshot, ExamSnapshot.exam_schedule_id == ExamSchedule.id).filter(
        ExamSnapshot.question_package_id == package.id,
        ExamSession.status.in_(["ACTIVE", "COMPLETED"])
    ).first()

    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Paket soal ini sedang/sudah digunakan dalam ujian yang berjalan/selesai dan tidak dapat dihapus."
        )

    # Detach or revert schedules linked to this question package to DRAFT
    snapshots = db.query(ExamSnapshot).filter(ExamSnapshot.question_package_id == package.id).all()
    schedule_ids = [s.exam_schedule_id for s in snapshots]
    db.query(ExamSnapshot).filter(ExamSnapshot.question_package_id == package.id).delete(synchronize_session=False)

    if schedule_ids:
        linked_schedules = db.query(ExamSchedule).filter(ExamSchedule.id.in_(schedule_ids)).all()
        for sch in linked_schedules:
            sch.status = "DRAFT"

    from app.models.teacher.question_package import QuestionPackageItem
    db.query(QuestionPackageItem).filter(QuestionPackageItem.package_id == package.id).delete(synchronize_session=False)

    db.delete(package)
    db.commit()


@router.post("/{package_id}/revert-draft", response_model=QuestionPackageDetailResponse)
def revert_package_to_draft(
    package_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    package = question_package_repository.get_by_id(db, package_id)
    if not package or package.owner_teacher_account_id != teacher_account_id or package.school_id != school_id:
        raise HTTPException(status_code=404, detail="Question package not found")

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_session import ExamSession
    from app.models.academic.exam_snapshot import ExamSnapshot

    active_session = db.query(ExamSession).join(ExamSchedule).join(ExamSnapshot, ExamSnapshot.exam_schedule_id == ExamSchedule.id).filter(
        ExamSnapshot.question_package_id == package.id,
        ExamSession.status.in_(["ACTIVE", "COMPLETED"])
    ).first()

    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Paket soal ini sedang/sudah memiliki sesi ujian yang berjalan atau selesai dan tidak dapat diubah ke Draft."
        )

    # Revert package status and linked schedules to DRAFT
    package.status = "INCOMPLETE"
    snapshots = db.query(ExamSnapshot).filter(ExamSnapshot.question_package_id == package.id).all()
    schedule_ids = [s.exam_schedule_id for s in snapshots]
    if schedule_ids:
        linked_schedules = db.query(ExamSchedule).filter(ExamSchedule.id.in_(schedule_ids)).all()
        for sch in linked_schedules:
            sch.status = "DRAFT"

    db.commit()
    return get_package_detail(package_id=package_id, current_user=current_user, db=db)


@router.post("/{package_id}/questions/{question_id}", response_model=QuestionPackageDetailResponse)
def add_question(
    package_id: int,
    question_id: int,
    score: float = 0.0,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    # Add question using service
    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package_id,
        question_id=question_id,
        teacher_account_id=teacher_account_id,
        school_id=school_id,
        score=score,
    )
    
    # Return updated package detail
    return get_package_detail(package_id=package_id, current_user=current_user, db=db)


@router.post("/{package_id}/reorder", response_model=QuestionPackageDetailResponse)
def reorder_questions(
    package_id: int,
    order_map: dict[int, int],
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    QuestionPackageService.reorder_questions(
        db=db,
        package_id=package_id,
        order_map=order_map,
        teacher_account_id=teacher_account_id,
    )
    return get_package_detail(package_id=package_id, current_user=current_user, db=db)


@router.delete("/{package_id}/questions/{question_id}", response_model=QuestionPackageDetailResponse)
def remove_question_from_package(
    package_id: int,
    question_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    QuestionPackageService.remove_question_from_package(
        db=db,
        package_id=package_id,
        question_id=question_id,
        teacher_account_id=teacher_account_id,
        school_id=school_id,
    )
    return get_package_detail(package_id=package_id, current_user=current_user, db=db)


@router.post("/{package_id}/questions/{old_question_id}/replace/{new_question_id}", response_model=QuestionPackageDetailResponse)
def replace_question_in_package(
    package_id: int,
    old_question_id: int,
    new_question_id: int,
    score: float | None = None,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    QuestionPackageService.replace_question_in_package(
        db=db,
        package_id=package_id,
        old_question_id=old_question_id,
        new_question_id=new_question_id,
        teacher_account_id=teacher_account_id,
        school_id=school_id,
        score=score,
    )
    return get_package_detail(package_id=package_id, current_user=current_user, db=db)


@router.get(
    "/{package_id}/snapshot-payload",
    response_model=QuestionPackageSnapshotPayload,
)
def get_snapshot_payload(
    package_id: int,
    _token=Depends(require_internal_token),
    db: Session = Depends(get_db),
):
    package = question_package_repository.get_by_id(db, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Question package not found")

    sorted_items = sorted(package.items, key=lambda x: x.canonical_order)

    questions_payload = []
    for item in sorted_items:
        q = item.question
        questions_payload.append(
            {
                "id": q.id,
                "type": q.type,
                "content": q.content,
                "options": q.options,
                "answer_key": q.answer_key,
                "rubrics": q.rubrics,
                "canonical_order": item.canonical_order,
            }
        )

    return {
        "package_id": package.id,
        "name": package.name,
        "class_level": package.class_level,
        "questions": questions_payload,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Question Bank (Questions) Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@questions_router.get("", response_model=list[TeacherQuestionResponse])
def list_questions(
    subject: str | None = None,
    class_level: str | None = None,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    stmt = select(Question).where(Question.owner_teacher_account_id == teacher_account_id)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if class_level:
        stmt = stmt.where(Question.class_level == class_level)
    return list(db.scalars(stmt).all())


@questions_router.post("", response_model=TeacherQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreateRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    new_q = Question(
        owner_teacher_account_id=teacher_account_id,
        type=payload.type,
        content=payload.content,
        options=payload.options,
        answer_key=payload.answer_key,
        rubrics=payload.rubrics,
        subject=payload.subject,
        class_level=payload.class_level,
        ai_grading=payload.ai_grading,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return new_q


@questions_router.put("/{question_id}", response_model=TeacherQuestionResponse)
def update_question(
    question_id: int,
    payload: QuestionUpdateRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    q = question_repository.get_owned_question_in_school(db, question_id, teacher_account_id, school_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found or not owned by you.")

    if payload.content is not None:
        q.content = payload.content
    if payload.options is not None:
        q.options = payload.options
    if payload.answer_key is not None:
        q.answer_key = payload.answer_key
    if payload.rubrics is not None:
        q.rubrics = payload.rubrics
    if payload.subject is not None:
        q.subject = payload.subject
    if payload.class_level is not None:
        q.class_level = payload.class_level
    if payload.ai_grading is not None:
        q.ai_grading = payload.ai_grading

    db.commit()
    db.refresh(q)
    return q


@questions_router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    q = question_repository.get_owned_question_in_school(db, question_id, teacher_account_id, school_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found or not owned by you.")

    # Check if question is used in any package
    from app.models.teacher.package_item import QuestionPackageItem
    stmt = select(QuestionPackageItem).where(QuestionPackageItem.question_id == question_id)
    used = db.scalars(stmt).first()
    if used:
        raise HTTPException(
            status_code=400,
            detail="Tidak dapat menghapus soal karena sedang digunakan di satu atau lebih Paket Soal."
        )

    db.delete(q)
    db.commit()


@questions_router.post("/upload-image")
async def upload_question_image(
    file: UploadFile = File(...),
    current_user=Depends(require_role(UserRole.TEACHER)),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Format file '{ext}' tidak didukung. Hanya file gambar (.jpg, .png, .webp, .svg, .gif) yang diizinkan."
        )

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran gambar maksimal 5 MB.")

    filename = f"q_img_{uuid.uuid4().hex}{ext}"
    target_dir = os.path.join("uploads", "questions")
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    url = f"/uploads/questions/{filename}"
    return {"url": url, "filename": filename}


# ─────────────────────────────────────────────────────────────────────────────
# Teacher Dashboard Schemas
# ─────────────────────────────────────────────────────────────────────────────

from app.schemas.academic.admin_academic import StudentEnrollmentResponse

class TeacherAssignmentResponse(BaseModel):
    id: int
    public_id: UUID
    title: str
    class_id: int
    class_name: str | None
    grade_level: str | None = None
    academic_year_name: str | None = None
    subject_id: int
    subject_name: str | None
    start_time: datetime
    end_time: datetime
    status: str
    has_snapshot: bool
    snapshot_id: int | None = None
    snapshot_package_name: str | None = None
    assigned_package_public_id: UUID | None = None

class FinalizeAssignmentRequest(BaseModel):
    package_public_id: UUID
    lock_browser: bool | None = True
    eyd_language_evaluation: bool | None = False
    randomize_per_type: bool | None = True

class TeacherProctorAssignmentResponse(BaseModel):
    id: int
    public_id: UUID
    title: str
    class_id: int
    class_name: str | None
    subject_id: int
    subject_name: str | None
    start_time: datetime
    end_time: datetime
    status: str
    exam_session_id: int | None = None
    exam_session_status: str | None = None

class StudentAttemptProctorResponse(BaseModel):
    attempt_id: int
    student_id: int
    student_name: str
    student_username: str
    nisn: str | None
    nis: str | None
    status: str
    started_at: datetime | None
    deadline_at: datetime | None
    remaining_seconds: int | None
    device_status: str | None
    device_id: str | None
    ip_address: str | None

class EssayGradingEvaluationResponse(BaseModel):
    evaluation_id: int
    attempt_id: int
    student_name: str
    exam_title: str
    class_name: str
    question_id: int
    question_content: str
    student_answer: str | None
    ai_score: float
    ai_feedback: str | None
    grading_status: str
    final_score: float | None

class FinalizeEssayGradingRequest(BaseModel):
    score: float
    feedback: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Teacher Dashboard Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_router.get("/assignments", response_model=list[TeacherAssignmentResponse])
def list_teacher_assignments(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
    
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.exam_snapshot import ExamSnapshot
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.academic.subject_repository import subject_repository
    
    from app.repositories.academic.academic_year_repository import academic_year_repository

    schedules = db.query(ExamSchedule).filter(
        ExamSchedule.school_id == school_id,
        ExamSchedule.teacher_id == teacher_id
    ).order_by(ExamSchedule.start_time.asc()).all()
    
    res = []
    for s in schedules:
        cls = class_repository.get_by_id(db, s.class_id)
        subj = subject_repository.get_by_id(db, s.subject_id)
        ay = academic_year_repository.get_by_id(db, s.academic_year_id) if hasattr(s, "academic_year_id") and s.academic_year_id else None
        snapshot = db.query(ExamSnapshot).filter(ExamSnapshot.exam_schedule_id == s.id).first()
        
        package_name = None
        assigned_pkg_pub_id = None
        if snapshot and isinstance(snapshot.snapshot_data, dict):
            package_name = snapshot.snapshot_data.get("package_name")
            pkg_pub_str = snapshot.snapshot_data.get("package_public_id")
            if pkg_pub_str:
                try:
                    assigned_pkg_pub_id = UUID(pkg_pub_str)
                except Exception:
                    pass
            
        res.append(
            TeacherAssignmentResponse(
                id=s.id,
                public_id=s.public_id,
                title=s.title,
                class_id=s.class_id,
                class_name=cls.name if cls else None,
                grade_level=cls.grade_level if cls else None,
                academic_year_name=ay.name if ay else None,
                subject_id=s.subject_id,
                subject_name=subj.name if subj else None,
                start_time=s.start_time,
                end_time=s.end_time,
                status=s.status,
                has_snapshot=snapshot is not None,
                snapshot_id=snapshot.id if snapshot else None,
                snapshot_package_name=package_name,
                assigned_package_public_id=assigned_pkg_pub_id,
            )
        )
    return res


@dashboard_router.post("/assignments/{schedule_public_id}/finalize")
def finalize_teacher_assignment(
    schedule_public_id: UUID,
    payload: FinalizeAssignmentRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
    
    from app.services.academic.exam_snapshot_service import ExamSnapshotService
    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository

    schedule = exam_schedule_repository.get_by_public_id(db, schedule_public_id)
    if schedule:
        if payload.lock_browser is not None:
            schedule.lock_browser = payload.lock_browser
        if payload.eyd_language_evaluation is not None:
            schedule.eyd_language_evaluation = payload.eyd_language_evaluation
        if payload.randomize_per_type is not None:
            schedule.randomize_per_type = payload.randomize_per_type
        db.flush()

    snapshot = ExamSnapshotService.create_immutable_snapshot(
        db=db,
        school_id=school_id,
        teacher_id=teacher_id,
        schedule_public_id=schedule_public_id,
        package_public_id=payload.package_public_id,
    )
    db.commit()
    return {"status": "success", "snapshot_id": snapshot.id}


@dashboard_router.post("/assignments/{schedule_public_id}/unassign")
def unassign_teacher_assignment(
    schedule_public_id: UUID,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.exam_snapshot import ExamSnapshot
    from app.models.exam.exam_session import ExamSession

    schedule = db.query(ExamSchedule).filter(
        ExamSchedule.school_id == school_id,
        ExamSchedule.public_id == schedule_public_id,
        ExamSchedule.teacher_id == teacher_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal ujian tidak ditemukan atau bukan milik Anda.")

    # Check if an active/completed session exists
    active_session = db.query(ExamSession).filter(
        ExamSession.schedule_id == schedule.id,
        ExamSession.status.in_(["ACTIVE", "COMPLETED"])
    ).first()
    if active_session:
        raise HTTPException(status_code=400, detail="Jadwal ujian ini sudah memiliki sesi ujian yang berjalan atau selesai.")

    # Remove snapshot and revert schedule status to DRAFT
    db.query(ExamSnapshot).filter(ExamSnapshot.exam_schedule_id == schedule.id).delete(synchronize_session=False)
    schedule.status = "DRAFT"
    db.commit()
    return {"status": "success", "message": "Penugasan paket soal dibatalkan."}


@dashboard_router.get("/proctor/assignments", response_model=list[TeacherProctorAssignmentResponse])
def list_proctor_assignments(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
    
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_session import ExamSession
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.academic.subject_repository import subject_repository
    
    schedules = db.query(ExamSchedule).filter(
        ExamSchedule.school_id == school_id,
        ExamSchedule.proctor_id == teacher_id
    ).order_by(ExamSchedule.start_time.asc()).all()
    
    res = []
    for s in schedules:
        cls = class_repository.get_by_id(db, s.class_id)
        subj = subject_repository.get_by_id(db, s.subject_id)
        session = db.query(ExamSession).filter(ExamSession.schedule_id == s.id).first()
        if not session and s.status in ["READY", "ACTIVE"]:
            from app.models.exam.enums import ExamSessionStatus
            from app.utils.timezone import ensure_wib
            from datetime import datetime, timezone

            now_wib = ensure_wib(datetime.now(timezone.utc))
            start_wib = ensure_wib(s.start_time)
            sess_status = ExamSessionStatus.ACTIVE if now_wib >= start_wib else ExamSessionStatus.PLANNED
            
            session = ExamSession(
                schedule_id=s.id,
                package_id=s.package_id or 0,
                scheduled_start_at=s.start_time,
                scheduled_end_at=s.end_time,
                duration_minutes=s.duration_minutes,
                status=sess_status,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        res.append(
            TeacherProctorAssignmentResponse(
                id=s.id,
                public_id=s.public_id,
                title=s.title,
                class_id=s.class_id,
                class_name=cls.name if cls else None,
                subject_id=s.subject_id,
                subject_name=subj.name if subj else None,
                start_time=s.start_time,
                end_time=s.end_time,
                status=s.status,
                exam_session_id=session.id if session else None,
                exam_session_status=session.status.value if session else None,
            )
        )
    return res


@dashboard_router.get("/classes/{class_id}/students", response_model=list[StudentEnrollmentResponse])
def list_class_students_for_teacher(
    class_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
    
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.security.auth_repository import auth_repository
    from app.services.academic.class_structure_service import ClassStructureService
    
    cls = class_repository.get_by_id(db, class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
        
    enrollments = ClassStructureService.list_students_in_class(db, class_id)
    res = []
    for e in enrollments:
        student = auth_repository.get_by_id(db, e.student_id)
        res.append(
            StudentEnrollmentResponse(
                id=e.id,
                public_id=e.public_id,
                school_id=e.school_id,
                student_id=e.student_id,
                class_id=e.class_id,
                academic_year_id=e.academic_year_id,
                status=e.status,
                start_date=e.start_date,
                end_date=e.end_date,
                student_name=student.name if student else None,
                student_username=student.username if student else None,
                nisn=student.nisn if student else None,
                nis=student.nis if student else None,
                class_name=cls.name,
            )
        )
    return res


@dashboard_router.get("/sessions/{exam_session_id}/attempts", response_model=list[StudentAttemptProctorResponse])
def list_session_attempts(
    exam_session_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.models.exam.exam_session import ExamSession
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.student_class_enrollment import StudentClassEnrollment
    from app.models.security.auth_account import AuthAccount
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.device_session import DeviceSession

    session = db.query(ExamSession).filter(ExamSession.id == exam_session_id).first()
    if not session:
        return []

    schedule = db.query(ExamSchedule).filter(ExamSchedule.id == session.schedule_id).first()
    if not schedule:
        return []

    # Get all students enrolled in this class
    enrollments = db.query(StudentClassEnrollment).filter(
        StudentClassEnrollment.class_id == schedule.class_id,
        StudentClassEnrollment.status == "ACTIVE"
    ).all()
    student_ids = [e.student_id for e in enrollments]

    # Map existing attempts
    attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id == exam_session_id).all()
    attempt_map = {a.student_id: a for a in attempts}

    res = []
    all_student_ids = list(set(student_ids + list(attempt_map.keys())))

    students = db.query(AuthAccount).filter(AuthAccount.id.in_(all_student_ids)).all() if all_student_ids else []
    student_map = {s.id: s for s in students}

    for sid in all_student_ids:
        student = student_map.get(sid)
        if not student:
            continue

        a = attempt_map.get(sid)
        if a:
            device_session = db.query(DeviceSession).filter(
                DeviceSession.exam_attempt_id == a.id
            ).order_by(DeviceSession.created_at.desc()).first()

            res.append(
                StudentAttemptProctorResponse(
                    attempt_id=a.id,
                    student_id=student.id,
                    student_name=student.name or student.username,
                    student_username=student.username,
                    nisn=student.nisn,
                    nis=student.nis,
                    status=a.status.value,
                    started_at=a.started_at,
                    deadline_at=a.deadline_at,
                    remaining_seconds=a.remaining_seconds,
                    device_status=device_session.status.value if device_session else None,
                    device_id=device_session.device_id if device_session else None,
                    ip_address=device_session.ip_address if device_session else None,
                )
            )
        else:
            res.append(
                StudentAttemptProctorResponse(
                    attempt_id=0,
                    student_id=student.id,
                    student_name=student.name or student.username,
                    student_username=student.username,
                    nisn=student.nisn,
                    nis=student.nis,
                    status="NOT_STARTED",
                    started_at=None,
                    deadline_at=None,
                    remaining_seconds=None,
                    device_status=None,
                    device_id=None,
                    ip_address=None,
                )
            )

    return res


@dashboard_router.get("/grading/evaluations", response_model=list[EssayGradingEvaluationResponse])
def list_grading_evaluations(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
        
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_session import ExamSession
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.answer_evaluation import ExamAnswerEvaluation
    from app.models.exam.student_answer import StudentAnswer
    from app.models.teacher.question import Question
    from app.repositories.security.auth_repository import auth_repository
    from app.repositories.academic.class_repository import class_repository
    
    # Get all schedules where this teacher is the subject teacher
    schedules = db.query(ExamSchedule).filter(
        ExamSchedule.school_id == school_id,
        ExamSchedule.teacher_id == teacher_id
    ).all()
    
    schedule_ids = [s.id for s in schedules]
    if not schedule_ids:
        return []
        
    # Get sessions for these schedules
    sessions = db.query(ExamSession).filter(ExamSession.schedule_id.in_(schedule_ids)).all()
    session_ids = [se.id for se in sessions]
    if not session_ids:
        return []
        
    # Map session_id to schedule
    session_schedule_map = {se.id: next(s for s in schedules if s.id == se.schedule_id) for se in sessions}
    
    # Get attempts for these sessions
    attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id.in_(session_ids)).all()
    attempt_ids = [a.id for a in attempts]
    if not attempt_ids:
        return []
        
    # Map attempt to session & schedule
    attempt_map = {a.id: a for a in attempts}
    
    # Get all essay evaluations for these attempts
    evaluations = db.query(ExamAnswerEvaluation).filter(
        ExamAnswerEvaluation.exam_attempt_id.in_(attempt_ids)
    ).all()
    
    res = []
    for ev in evaluations:
        q = db.query(Question).filter(Question.id == ev.question_id).first()
        if not q or q.type.value != "ES": # Only essay evaluations
            continue
            
        attempt = attempt_map[ev.exam_attempt_id]
        session = session_schedule_map[attempt.exam_session_id]
        student = auth_repository.get_by_id(db, attempt.student_id)
        cls = class_repository.get_by_id(db, attempt.class_id) if hasattr(attempt, "class_id") else class_repository.get_by_id(db, session.class_id)
        
        # Get student answer text
        ans = db.query(StudentAnswer).filter(
            StudentAnswer.exam_attempt_id == attempt.id,
            StudentAnswer.question_id == q.id
        ).first()
        
        res.append(
            EssayGradingEvaluationResponse(
                evaluation_id=ev.id,
                attempt_id=attempt.id,
                student_name=student.name or student.username if student else "Siswa",
                exam_title=session.title,
                class_name=cls.name if cls else "Kelas",
                question_id=q.id,
                question_content=q.content,
                student_answer=ans.text_answer if ans else None,
                ai_score=float(ev.score),
                ai_feedback=ev.feedback,
                grading_status=ev.grading_status.value,
                final_score=float(ev.score) if ev.grading_status.value == "FINALIZED" else None,
            )
        )
    return res


@dashboard_router.post("/grading/evaluations/{evaluation_id}/finalize")
def finalize_evaluation_score(
    evaluation_id: int,
    payload: FinalizeEssayGradingRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")
    
    from app.services.exam.exam_service import ExamService
    
    eval_res = ExamService.finalize_evaluation(
        db=db,
        evaluation_id=evaluation_id,
        score=payload.score,
        feedback=payload.feedback,
        teacher_account_id=teacher_id,
    )
    db.commit()
    return {"status": "success", "score": float(eval_res.score)}
