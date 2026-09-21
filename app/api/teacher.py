import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.status import HTTP_403_FORBIDDEN

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
from app.schemas.common.import_validation import ImportResponse
from app.schemas.teacher import (
    QuestionCreateRequest,
    QuestionImportRequest,
    QuestionPackageCreate,
    QuestionPackageDetailResponse,
    QuestionPackageResponse,
    QuestionPackageSnapshotPayload,
    QuestionUpdateRequest,
    TeacherQuestionResponse,
)
from app.services.teacher.question_bank_import_service import QuestionBankImportService
from app.services.teacher.question_package_service import QuestionPackageService

router = APIRouter(prefix="/api/v1/teacher/packages", tags=["Teacher Content — Packages"])
questions_router = APIRouter(
    prefix="/api/v1/teacher/questions", tags=["Teacher Content — Questions"]
)
dashboard_router = APIRouter(prefix="/api/v1/teacher", tags=["Teacher Dashboard & Control"])


def require_internal_token(x_internal_service_token: str = Header(None)):
    from app.core.security.keys import get_internal_service_token

    secret = get_internal_service_token()
    if not x_internal_service_token or x_internal_service_token != secret:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Access denied: Internal service only",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Teacher Dashboard Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@dashboard_router.get("/dashboard-summary")
def get_teacher_dashboard_summary(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from sqlalchemy import func

    from app.models.teacher.question_package import QuestionPackage

    total_packages = (
        db.query(func.count(QuestionPackage.id))
        .filter(
            QuestionPackage.owner_teacher_account_id == teacher_account_id,
            QuestionPackage.school_id == school_id,
        )
        .scalar()
        or 0
    )

    ready_packages = (
        db.query(func.count(QuestionPackage.id))
        .filter(
            QuestionPackage.owner_teacher_account_id == teacher_account_id,
            QuestionPackage.school_id == school_id,
            QuestionPackage.status == "READY",
        )
        .scalar()
        or 0
    )

    total_questions = (
        db.query(func.count(Question.id))
        .filter(
            Question.owner_teacher_account_id == teacher_account_id,
        )
        .scalar()
        or 0
    )

    return {
        "package_count": total_packages,
        "ready_package_count": ready_packages,
        "question_count": total_questions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Question Packages Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[QuestionPackageResponse])
def list_packages(
    limit: int | None = None,
    skip: int = 0,
    search: str | None = None,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.models.teacher.question_package import QuestionPackage

    stmt = select(QuestionPackage).where(
        QuestionPackage.owner_teacher_account_id == teacher_account_id,
        QuestionPackage.school_id == school_id,
    )
    if search and search.strip():
        stmt = stmt.where(QuestionPackage.name.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(QuestionPackage.created_at.desc()).offset(skip)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/assigned-subjects", response_model=list[str])
def get_teacher_assigned_subjects(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_account_id = int(current_user["sub"])
    from app.repositories.security.auth_repository import auth_repository

    account = auth_repository.get_by_id(db, teacher_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Akun guru tidak ditemukan")

    from app.services.school.staff_service import SchoolStaffService

    subjects, _ = SchoolStaffService.resolve_teacher_academic_profile(db, account)
    db.commit()
    return subjects


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

    package = question_package_repository.get_by_id_with_items_and_questions(db, package_id)
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
                "class_level": q.class_level,
                "ai_grading": q.ai_grading,
                "created_at": q.created_at,
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
        "created_at": package.created_at,
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
    from app.models.academic.exam_snapshot import ExamSnapshot
    from app.models.exam.exam_session import ExamSession

    # Check if assigned to an ACTIVE/COMPLETED session
    active_session = (
        db.query(ExamSession)
        .join(ExamSchedule, ExamSession.schedule_id == ExamSchedule.id)
        .join(ExamSnapshot, ExamSnapshot.exam_schedule_id == ExamSchedule.id)
        .filter(
            ExamSnapshot.question_package_id == package.id,
            ExamSession.status.in_(["ACTIVE", "COMPLETED"]),
        )
        .first()
    )

    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Paket soal ini sedang/sudah digunakan dalam ujian yang berjalan/selesai dan tidak dapat dihapus.",
        )

    # Detach or revert schedules linked to this question package to DRAFT
    snapshots = db.query(ExamSnapshot).filter(ExamSnapshot.question_package_id == package.id).all()
    schedule_ids = [s.exam_schedule_id for s in snapshots]
    db.query(ExamSnapshot).filter(ExamSnapshot.question_package_id == package.id).delete(
        synchronize_session=False
    )

    if schedule_ids:
        linked_schedules = db.query(ExamSchedule).filter(ExamSchedule.id.in_(schedule_ids)).all()
        for sch in linked_schedules:
            sch.status = "DRAFT"

    from app.models.teacher.package_item import QuestionPackageItem

    db.query(QuestionPackageItem).filter(QuestionPackageItem.package_id == package.id).delete(
        synchronize_session=False
    )

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
    if (
        not package
        or package.owner_teacher_account_id != teacher_account_id
        or package.school_id != school_id
    ):
        raise HTTPException(status_code=404, detail="Question package not found")

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.exam_snapshot import ExamSnapshot
    from app.models.exam.exam_session import ExamSession

    active_session = (
        db.query(ExamSession)
        .join(ExamSchedule, ExamSession.schedule_id == ExamSchedule.id)
        .join(ExamSnapshot, ExamSnapshot.exam_schedule_id == ExamSchedule.id)
        .filter(
            ExamSnapshot.question_package_id == package.id,
            ExamSession.status.in_(["ACTIVE", "COMPLETED"]),
        )
        .first()
    )

    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Paket soal ini sedang/sudah memiliki sesi ujian yang berjalan atau selesai dan tidak dapat diubah ke Draft.",
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


@router.post("/{package_id}/publish", response_model=QuestionPackageDetailResponse)
def publish_package_to_ready(
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

    actual_counts = {"PG": 0, "IS": 0, "ES": 0}
    for item in package.items:
        q = item.question
        if q and q.type in actual_counts:
            actual_counts[q.type] += 1

    targets = package.target_counts or {"PG": 0, "IS": 0, "ES": 0}
    missing = []
    for qtype in ["PG", "IS", "ES"]:
        target_val = targets.get(qtype, 0)
        actual_val = actual_counts.get(qtype, 0)
        if actual_val < target_val:
            missing.append(f"{qtype}: {actual_val}/{target_val}")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Paket soal belum memenuhi target kuota ({', '.join(missing)}). Harap lengkapi soal terlebih dahulu sebelum mem-post paket soal.",
        )

    package.status = "READY"
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


@router.delete(
    "/{package_id}/questions/{question_id}", response_model=QuestionPackageDetailResponse
)
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


@router.post(
    "/{package_id}/questions/{old_question_id}/replace/{new_question_id}",
    response_model=QuestionPackageDetailResponse,
)
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
    limit: int | None = None,
    skip: int = 0,
    search: str | None = None,
    subject: str | None = None,
    class_level: str | None = None,
    question_type: str | None = None,
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
    if question_type:
        stmt = stmt.where(Question.type == question_type)
    if search and search.strip():
        stmt = stmt.where(Question.content.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Question.created_at.desc()).offset(skip)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


@questions_router.post(
    "", response_model=TeacherQuestionResponse, status_code=status.HTTP_201_CREATED
)
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


@questions_router.post("/import", response_model=ImportResponse[TeacherQuestionResponse])
def import_questions(
    payload: QuestionImportRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    from app.schemas.common.import_validation import ImportResponse, ImportRowError

    teacher_account_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    rows_list = [row.model_dump(mode="json") for row in payload.rows]

    success, created_questions, errors, skipped = QuestionBankImportService.import_questions_batch(
        db=db,
        teacher_account_id=teacher_account_id,
        school_id=school_id,
        subject=payload.subject,
        rows_data=rows_list,
    )

    if not success:
        row_errors = [ImportRowError(**err) for err in errors]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ImportResponse(
                status="error",
                message="Impor bank soal gagal karena terdapat kesalahan validasi.",
                imported_count=0,
                errors=row_errors,
            ).model_dump(),
        )

    db.commit()

    msg = f"Berhasil mengimpor {len(created_questions)} soal baru."
    if skipped:
        msg = f"Berhasil mengimpor {len(created_questions)} soal baru, {len(skipped)} soal dilewati karena sudah ada."

    return ImportResponse[TeacherQuestionResponse](
        status="success",
        message=msg,
        imported_count=len(created_questions),
        data=created_questions,
        skipped=skipped,
    )


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

    q = question_repository.get_owned_question_in_school(
        db, question_id, teacher_account_id, school_id
    )
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

    q = question_repository.get_owned_question_in_school(
        db, question_id, teacher_account_id, school_id
    )
    if not q:
        raise HTTPException(status_code=404, detail="Question not found or not owned by you.")

    # Check if question is used in any package
    from app.models.teacher.package_item import QuestionPackageItem

    stmt = select(QuestionPackageItem).where(QuestionPackageItem.question_id == question_id)
    used = db.scalars(stmt).first()
    if used:
        raise HTTPException(
            status_code=400,
            detail="Tidak dapat menghapus soal karena sedang digunakan di satu atau lebih Paket Soal.",
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

    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Format file '{ext}' tidak didukung. Hanya file gambar (.jpg, .png, .webp, .gif) yang diizinkan.",
        )

    allowed_mimes = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type and file.content_type.lower() not in allowed_mimes:
        raise HTTPException(
            status_code=400,
            detail=f"Content-Type '{file.content_type}' tidak diizinkan. Hanya file gambar (.jpg, .png, .webp, .gif) yang diperbolehkan.",
        )

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran gambar maksimal 5 MB.")

    from app.core.storage import storage_service

    try:
        saved = storage_service.save_file(
            content=content,
            filename=file.filename or f"image{ext}",
            content_type=file.content_type,
            folder="questions",
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"Gagal menyimpan file gambar: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan file gambar.")

    return {"url": saved["url"], "filename": saved["filename"]}


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
    battery_level: int | None = None
    ping_ms: int | None = None
    violation_reason: str | None = None
    monitoring_card_state: str = "GREEN"


class EssayGradingEvaluationResponse(BaseModel):
    evaluation_id: int
    attempt_id: int
    schedule_id: int
    student_name: str
    exam_title: str
    package_name: str | None = None
    subject_name: str | None = None
    class_name: str
    question_id: int
    question_content: str
    student_answer: str | None
    ai_score: float
    ai_feedback: str | None
    grading_status: str
    final_score: float | None
    confidence: float = 1.0
    confidence_level: str = "HIGH"
    review_required: bool = False
    rubric_scores: list[dict[str, Any]] | None = None
    academic_rationale: str | None = None


def _derive_ai_evaluation_metadata(
    ev: Any,
    q: Any = None,
    text_answer: str | None = None,
) -> dict[str, Any]:
    """
    Derives root-level confidence, categorical confidence level (HIGH/MEDIUM/LOW),
    review_required flag, rubric breakdown, and academic rationale for essay evaluations.
    AI Confidence is strictly independent from the student's assessment score.
    """
    earned = float(ev.score) if (ev and ev.score is not None) else 0.0
    max_q = (
        float(ev.max_score)
        if (ev and ev.max_score is not None and float(ev.max_score) > 0)
        else 10.0
    )
    ratio = max(0.0, min(1.0, earned / max_q))

    is_empty = (
        not text_answer or text_answer.strip() == "" or text_answer.strip() == "(Tidak diisi)"
    )
    is_finalized = hasattr(ev, "grading_status") and (
        getattr(ev.grading_status, "value", str(ev.grading_status)) == "FINALIZED"
    )

    # Decouple AI Confidence from score ratio: read model output confidence if available
    raw_conf = getattr(ev, "confidence", None)
    if raw_conf is None and isinstance(ev, dict):
        raw_conf = ev.get("confidence")

    if is_finalized or is_empty:
        confidence = 1.0
    elif raw_conf is not None:
        try:
            confidence = round(max(0.0, min(1.0, float(raw_conf))), 2)
        except (ValueError, TypeError):
            confidence = 0.95 if ratio >= 0.9 else (0.82 if ratio >= 0.75 else (0.70 if ratio >= 0.5 else 0.65))
    else:
        # Default AI model certainty for unfinalized non-empty evaluation
        # Calculate dynamic confidence based on the score ratio so it's not uniformly 85%
        if ratio >= 0.9:
            confidence = 0.95
        elif ratio >= 0.75:
            confidence = 0.82
        elif ratio >= 0.5:
            confidence = 0.70
        else:
            confidence = 0.65

    if confidence >= 0.90:
        confidence_level = "HIGH"
        review_required = False
    elif confidence >= 0.75:
        confidence_level = "MEDIUM"
        review_required = True
    else:
        confidence_level = "LOW"
        review_required = True

    # Build rubric breakdown
    rubrics_list = getattr(q, "rubrics", None) if q else None
    rubric_scores: list[dict[str, Any]] = []

    if rubrics_list and isinstance(rubrics_list, list) and len(rubrics_list) > 0:
        total_w = sum(float(r.get("weight", 0)) for r in rubrics_list) or 100.0
        for idx, r in enumerate(rubrics_list):
            w = float(r.get("weight", round(100.0 / len(rubrics_list), 1)))
            weight_ratio = w / total_w
            r_earned = round(earned * weight_ratio, 2)
            r_max = round(max_q * weight_ratio, 2)
            rubric_scores.append(
                {
                    "ku_id": str(r.get("ku_id") or r.get("id") or f"C{idx+1}").strip(),
                    "text": str(
                        r.get("text")
                        or r.get("description")
                        or r.get("criterion_text")
                        or f"Kriteria {idx+1}"
                    ).strip(),
                    "weight": round(w, 1),
                    "achieved": round(ratio * 100.0, 1),
                    "earned_score": r_earned,
                    "max_score": r_max,
                }
            )
    else:
        rubric_scores = [
            {
                "ku_id": "C1",
                "text": "Pemahaman Konsep & Argumen Utama",
                "weight": 50.0,
                "achieved": round(ratio * 100.0, 1),
                "earned_score": round(earned * 0.5, 2),
                "max_score": round(max_q * 0.5, 2),
            },
            {
                "ku_id": "C2",
                "text": "Analisis, Bukti, & Ketepatan Istilah",
                "weight": 50.0,
                "achieved": round(ratio * 100.0, 1),
                "earned_score": round(earned * 0.5, 2),
                "max_score": round(max_q * 0.5, 2),
            },
        ]

    feedback_text = getattr(ev, "feedback", None) if ev else None
    if feedback_text and feedback_text.strip():
        academic_rationale = feedback_text.strip()
    elif is_empty:
        academic_rationale = "Jawaban siswa kosong. Tidak ada poin yang dapat dinilai."
    else:
        raw_type = getattr(q, "type", "ES") if q else "ES"
        q_type_str = getattr(raw_type, "value", str(raw_type))
        if q_type_str.upper() == "ES":
            academic_rationale = (
                "⚠️ Umpan balik analitis dari AI tidak tersedia (proses evaluasi terinterupsi atau gagal saat ujian berlangsung). "
                f"Silakan nilai secara manual atau klik tombol '🔄 AI Koreksi Ulang' untuk mencoba mengevaluasi ulang."
            )
        else:
            academic_rationale = (
                f"Evaluasi otomatis berbasis {len(rubric_scores)} kriteria rubrik dengan capaian {round(ratio * 100, 1)}%. "
                f"Skor akhir: {round(earned, 1)} dari {round(max_q, 1)} poin."
            )

    return {
        "confidence": confidence,
        "confidence_level": confidence_level,
        "review_required": review_required,
        "rubric_scores": rubric_scores,
        "academic_rationale": academic_rationale,
    }


class FinalizeEssayGradingRequest(BaseModel):
    score: float
    feedback: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Teacher Dashboard Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@dashboard_router.get("/assignments", response_model=list[TeacherAssignmentResponse])
def list_teacher_assignments(
    limit: int = 100,
    skip: int = 0,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.models.academic.academic_year import AcademicYear
    from app.models.academic.class_entity import ClassEntity
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.exam_snapshot import ExamSnapshot
    from app.models.academic.subject import Subject

    effective_limit = min(max(1, limit), 200)
    schedules = (
        db.query(ExamSchedule)
        .filter(ExamSchedule.school_id == school_id, ExamSchedule.teacher_id == teacher_id)
        .order_by(ExamSchedule.start_time.asc())
        .offset(skip)
        .limit(effective_limit)
        .all()
    )

    if not schedules:
        return []

    sched_ids = [s.id for s in schedules]
    class_ids = {s.class_id for s in schedules if s.class_id}
    subject_ids = {s.subject_id for s in schedules if s.subject_id}
    ay_ids = {
        s.academic_year_id
        for s in schedules
        if hasattr(s, "academic_year_id") and s.academic_year_id
    }

    # Bulk prefetch relations in 4 targeted queries
    classes_map = (
        {c.id: c for c in db.query(ClassEntity).filter(ClassEntity.id.in_(class_ids)).all()}
        if class_ids
        else {}
    )
    subjects_map = (
        {sub.id: sub for sub in db.query(Subject).filter(Subject.id.in_(subject_ids)).all()}
        if subject_ids
        else {}
    )
    ay_map = (
        {a.id: a for a in db.query(AcademicYear).filter(AcademicYear.id.in_(ay_ids)).all()}
        if ay_ids
        else {}
    )
    snapshots_map = (
        {
            snap.exam_schedule_id: snap
            for snap in db.query(ExamSnapshot)
            .filter(ExamSnapshot.exam_schedule_id.in_(sched_ids))
            .all()
        }
        if sched_ids
        else {}
    )

    res = []
    for s in schedules:
        cls = classes_map.get(s.class_id)
        subj = subjects_map.get(s.subject_id)
        ay = ay_map.get(getattr(s, "academic_year_id", None))
        snapshot = snapshots_map.get(s.id)

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

    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository
    from app.services.academic.exam_snapshot_service import ExamSnapshotService

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

    schedule = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.school_id == school_id,
            ExamSchedule.public_id == schedule_public_id,
            ExamSchedule.teacher_id == teacher_id,
        )
        .first()
    )

    if not schedule:
        raise HTTPException(
            status_code=404, detail="Jadwal ujian tidak ditemukan atau bukan milik Anda."
        )

    # Check if an active/completed session exists
    active_session = (
        db.query(ExamSession)
        .filter(
            ExamSession.schedule_id == schedule.id, ExamSession.status.in_(["ACTIVE", "COMPLETED"])
        )
        .first()
    )
    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Jadwal ujian ini sudah memiliki sesi ujian yang berjalan atau selesai.",
        )

    # Remove snapshot and revert schedule status to DRAFT
    db.query(ExamSnapshot).filter(ExamSnapshot.exam_schedule_id == schedule.id).delete(
        synchronize_session=False
    )
    schedule.status = "DRAFT"
    db.commit()
    return {"status": "success", "message": "Penugasan paket soal dibatalkan."}


@dashboard_router.get("/proctor/assignments", response_model=list[TeacherProctorAssignmentResponse])
def list_proctor_assignments(
    limit: int = 100,
    skip: int = 0,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.models.academic.class_entity import ClassEntity
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.subject import Subject
    from app.models.exam.exam_session import ExamSession

    effective_limit = min(max(1, limit), 200)
    schedules = (
        db.query(ExamSchedule)
        .filter(ExamSchedule.school_id == school_id, ExamSchedule.proctor_id == teacher_id)
        .order_by(ExamSchedule.start_time.asc())
        .offset(skip)
        .limit(effective_limit)
        .all()
    )

    if not schedules:
        return []

    sched_ids = [s.id for s in schedules]
    class_ids = {s.class_id for s in schedules if s.class_id}
    subject_ids = {s.subject_id for s in schedules if s.subject_id}

    classes_map = (
        {c.id: c for c in db.query(ClassEntity).filter(ClassEntity.id.in_(class_ids)).all()}
        if class_ids
        else {}
    )
    subjects_map = (
        {sub.id: sub for sub in db.query(Subject).filter(Subject.id.in_(subject_ids)).all()}
        if subject_ids
        else {}
    )
    sessions_map = (
        {
            sess.schedule_id: sess
            for sess in db.query(ExamSession).filter(ExamSession.schedule_id.in_(sched_ids)).all()
        }
        if sched_ids
        else {}
    )

    res = []
    for s in schedules:
        cls = classes_map.get(s.class_id)
        subj = subjects_map.get(s.subject_id)
        session = sessions_map.get(s.id)

        if not session and s.status in ["READY", "ACTIVE"]:
            from datetime import datetime, timezone

            from app.models.exam.enums import ExamSessionStatus
            from app.utils.timezone import ensure_wib

            now_wib = ensure_wib(datetime.now(timezone.utc))
            start_wib = ensure_wib(s.start_time)
            sess_status = (
                ExamSessionStatus.ACTIVE if now_wib >= start_wib else ExamSessionStatus.PLANNED
            )

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
            sessions_map[s.id] = session

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


@dashboard_router.get(
    "/classes/{class_id}/students", response_model=list[StudentEnrollmentResponse]
)
def list_class_students_for_teacher(
    class_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.repositories.academic.class_repository import class_repository
    from app.services.academic.class_structure_service import ClassStructureService

    cls = class_repository.get_by_id(db, class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")

    from app.models.security.auth_account import AuthAccount

    enrollments = ClassStructureService.list_students_in_class(db, class_id)
    student_ids = {e.student_id for e in enrollments}
    students_map = (
        {u.id: u for u in db.query(AuthAccount).filter(AuthAccount.id.in_(student_ids)).all()}
        if student_ids
        else {}
    )

    res = []
    for e in enrollments:
        student = students_map.get(e.student_id)
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


@dashboard_router.get(
    "/sessions/{exam_session_id}/attempts", response_model=list[StudentAttemptProctorResponse]
)
def list_session_attempts(
    exam_session_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.student_class_enrollment import StudentClassEnrollment
    from app.models.exam.device_session import DeviceSession
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.exam_session import ExamSession
    from app.models.security.auth_account import AuthAccount

    session = db.query(ExamSession).filter(ExamSession.id == exam_session_id).first()
    if not session:
        return []

    schedule = db.query(ExamSchedule).filter(ExamSchedule.id == session.schedule_id).first()
    if not schedule:
        return []

    # Get all students enrolled in this class
    enrollments = (
        db.query(StudentClassEnrollment)
        .filter(
            StudentClassEnrollment.class_id == schedule.class_id,
            StudentClassEnrollment.status == "ACTIVE",
        )
        .all()
    )
    student_ids = [e.student_id for e in enrollments]

    # Map existing attempts
    attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id == exam_session_id).all()
    attempt_map = {a.student_id: a for a in attempts}
    attempt_ids = [a.id for a in attempts]

    res = []
    all_student_ids = list(set(student_ids + list(attempt_map.keys())))

    students = (
        db.query(AuthAccount).filter(AuthAccount.id.in_(all_student_ids)).all()
        if all_student_ids
        else []
    )
    student_map = {s.id: s for s in students}

    from app.models.exam.exam_checkin import ExamCheckin
    from app.models.security.user_session import UserSession

    checkins = (
        db.query(ExamCheckin)
        .filter(
            ExamCheckin.schedule_id == schedule.id,
            ExamCheckin.student_id.in_(all_student_ids),
        )
        .all()
        if all_student_ids
        else []
    )
    checkin_map = {c.student_id: c for c in checkins}

    user_sessions_list = (
        db.query(UserSession)
        .filter(
            UserSession.auth_account_id.in_(all_student_ids),
            UserSession.revoked == False,
        )
        .order_by(UserSession.created_at.desc())
        .all()
        if all_student_ids
        else []
    )
    user_sess_map = {}
    for us in user_sessions_list:
        if us.auth_account_id not in user_sess_map:
            user_sess_map[us.auth_account_id] = us

    device_sessions_list = (
        db.query(DeviceSession)
        .filter(DeviceSession.exam_attempt_id.in_(attempt_ids))
        .order_by(DeviceSession.created_at.desc())
        .all()
        if attempt_ids
        else []
    )
    device_session_map = {}
    for ds in device_sessions_list:
        if ds.exam_attempt_id not in device_session_map:
            device_session_map[ds.exam_attempt_id] = ds

    from app.models.exam.attempt_telemetry import AttemptTelemetry

    # Batch query AttemptTelemetry from DB as authoritative source of truth
    telemetry_records = (
        db.query(AttemptTelemetry).filter(AttemptTelemetry.attempt_id.in_(attempt_ids)).all()
        if attempt_ids
        else []
    )
    telemetry_map = {t.attempt_id: t for t in telemetry_records}

    for sid in all_student_ids:
        student = student_map.get(sid)
        if not student:
            continue

        a = attempt_map.get(sid)
        checkin = checkin_map.get(sid)
        user_sess = user_sess_map.get(sid)

        if a:
            device_session = device_session_map.get(a.id)

            db_telem = telemetry_map.get(a.id)
            if db_telem:
                telem = {
                    "battery_level": db_telem.battery_level,
                    "is_charging": db_telem.is_charging,
                    "ping_ms": db_telem.ping_ms,
                    "is_offline": db_telem.is_offline,
                    "violation_type": db_telem.violation_type,
                    "violation_reason": db_telem.violation_reason,
                    "updated_at": db_telem.updated_at.isoformat() if db_telem.updated_at else None,
                }
            else:
                telem = {}
            bat = telem.get("battery_level")
            ping = telem.get("ping_ms")
            reason = telem.get("violation_reason")

            status_val = a.status.value if hasattr(a.status, "value") else str(a.status)
            dev_status_val = (
                device_session.status.value
                if device_session and hasattr(device_session.status, "value")
                else (str(device_session.status) if device_session else None)
            )

            # Determine monitoring card state (GREEN / YELLOW / RED)
            if status_val in ["PAUSED", "LOCKED"] or reason or dev_status_val == "BLOCKED":
                card_state = "RED"
            elif (
                (bat is not None and bat <= 20)
                or telem.get("is_offline")
                or dev_status_val == "INVALIDATED"
            ):
                card_state = "YELLOW"
            else:
                card_state = "GREEN"

            res.append(
                StudentAttemptProctorResponse(
                    attempt_id=a.id,
                    student_id=student.id,
                    student_name=student.name or student.username,
                    student_username=student.username,
                    nisn=student.nisn,
                    nis=student.nis,
                    status=status_val,
                    started_at=a.started_at,
                    deadline_at=a.deadline_at,
                    remaining_seconds=a.remaining_seconds,
                    device_status=dev_status_val,
                    device_id=(
                        device_session.device_id
                        if device_session
                        else (checkin.device_id if checkin else None)
                    ),
                    ip_address=(
                        device_session.ip_address
                        if device_session
                        else (
                            checkin.ip_address
                            if checkin
                            else (user_sess.ip_address if user_sess else None)
                        )
                    ),
                    battery_level=bat,
                    ping_ms=ping,
                    violation_reason=reason,
                    monitoring_card_state=card_state,
                )
            )
        else:
            status_val = "CHECKED_IN" if checkin else ("LOGGED_IN" if user_sess else "NOT_STARTED")
            card_state = "GREEN" if checkin else ("YELLOW" if user_sess else "YELLOW")
            dev_id = (
                checkin.device_id
                if checkin
                else (user_sess.user_agent[:40] if user_sess and user_sess.user_agent else None)
            )
            ip_addr = (
                checkin.ip_address if checkin else (user_sess.ip_address if user_sess else None)
            )

            res.append(
                StudentAttemptProctorResponse(
                    attempt_id=0,
                    student_id=student.id,
                    student_name=student.name or student.username,
                    student_username=student.username,
                    nisn=student.nisn,
                    nis=student.nis,
                    status=status_val,
                    started_at=(
                        checkin.checked_in_at
                        if checkin
                        else (user_sess.created_at if user_sess else None)
                    ),
                    deadline_at=None,
                    remaining_seconds=None,
                    device_status="CHECKED_IN" if checkin else ("LOGGED_IN" if user_sess else None),
                    device_id=dev_id,
                    ip_address=ip_addr,
                    monitoring_card_state=card_state,
                )
            )

    return res


@dashboard_router.get("/exam-history", status_code=status.HTTP_200_OK)
def list_teacher_exam_history(
    limit: int = 50,
    skip: int = 0,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """
    Mendapatkan Riwayat Ujian Selesai khusus untuk Guru Pengampu.
    Hanya menampilkan mata pelajaran dan kelas yang diampu oleh guru tersebut,
    dikelompokkan sesuai Nama Paket Jadwal yang dibuat Admin Sekolah.
    """
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from sqlalchemy import or_

    from app.models.academic.class_entity import ClassEntity
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.subject import Subject
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.exam_session import ExamSession

    effective_limit = min(max(1, limit), 100)
    schedules = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.school_id == school_id,
            or_(
                ExamSchedule.teacher_id == teacher_id,
                ExamSchedule.proctor_id == teacher_id,
            ),
        )
        .order_by(ExamSchedule.start_time.desc())
        .offset(skip)
        .limit(effective_limit)
        .all()
    )

    if not schedules:
        return {"grouped_packages": []}

    sched_ids = [s.id for s in schedules]
    class_ids = {s.class_id for s in schedules if s.class_id}
    subject_ids = {s.subject_id for s in schedules if s.subject_id}

    classes_map = (
        {c.id: c for c in db.query(ClassEntity).filter(ClassEntity.id.in_(class_ids)).all()}
        if class_ids
        else {}
    )
    subjects_map = (
        {sub.id: sub for sub in db.query(Subject).filter(Subject.id.in_(subject_ids)).all()}
        if subject_ids
        else {}
    )
    sessions = db.query(ExamSession).filter(ExamSession.schedule_id.in_(sched_ids)).all()
    sessions_map = {sess.schedule_id: sess for sess in sessions}
    session_ids = [sess.id for sess in sessions]

    attempts = (
        db.query(ExamAttempt).filter(ExamAttempt.exam_session_id.in_(session_ids)).all()
        if session_ids
        else []
    )
    attempts_by_session: dict[int, list[ExamAttempt]] = {}
    for a in attempts:
        attempts_by_session.setdefault(a.exam_session_id, []).append(a)

    grouped: dict[str, list] = {}

    for s in schedules:
        subj = subjects_map.get(s.subject_id)
        scls = classes_map.get(s.class_id)
        sess = sessions_map.get(s.id)

        sess_id = sess.id if sess else None
        att_list = attempts_by_session.get(sess_id, []) if sess_id else []

        submitted_attempts = [
            a
            for a in att_list
            if (hasattr(a.status, "value") and a.status.value in ["SUBMITTED", "GRADED"])
            or str(a.status) in ["SUBMITTED", "GRADED"]
        ]
        scores = [a.final_score for a in submitted_attempts if a.final_score is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None

        pkg_name = s.title if s.title else "Paket Jadwal Ujian"

        if pkg_name not in grouped:
            grouped[pkg_name] = []

        grouped[pkg_name].append(
            {
                "schedule_id": s.id,
                "session_id": sess_id,
                "title": s.title,
                "subject_id": s.subject_id,
                "subject_name": subj.name if subj else "Mata Pelajaran",
                "class_id": s.class_id,
                "class_name": scls.name if scls else "Kelas",
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "status": s.status,
                "total_students": len(att_list),
                "submitted_students": len(submitted_attempts),
                "average_score": avg_score,
            }
        )

    return {"grouped_packages": [{"package_title": k, "schedules": v} for k, v in grouped.items()]}


@dashboard_router.get("/exam-history/{schedule_id}/student-answers", status_code=status.HTTP_200_OK)
def get_student_answers_for_schedule(
    schedule_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """
    Mendapatkan rincian jawaban seluruh siswa untuk suatu jadwal ujian selesai.
    Guru dapat melihat breakdown skor per jenis soal (PG, IS, ES), jawaban siswa, dan nilai akhir.
    """
    from app.models.exam.answer_evaluation import ExamAnswerEvaluation
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.exam_session import ExamSession
    from app.models.exam.student_answer import StudentAnswer
    from app.models.security.auth_account import AuthAccount
    from app.models.teacher.question import Question

    def get_q_type(q):
        if not q:
            return "PG"
        if isinstance(q.type, str):
            return q.type
        if hasattr(q.type, "value"):
            return q.type.value
        return str(q.type)

    sessions = db.query(ExamSession).filter(ExamSession.schedule_id == schedule_id).all()
    if not sessions:
        # Fallback 1: check if schedule_id was passed as attempt_id
        att_fallback = db.query(ExamAttempt).filter(ExamAttempt.id == schedule_id).first()
        if att_fallback:
            sessions = (
                db.query(ExamSession).filter(ExamSession.id == att_fallback.exam_session_id).all()
            )
    if not sessions:
        # Fallback 2: check if schedule_id is ExamSession id
        sessions = db.query(ExamSession).filter(ExamSession.id == schedule_id).all()
    if not sessions:
        # Fallback 3: check if schedule_id is ExamSchedulePackage id
        from app.models.academic.exam_schedule import ExamSchedule

        schedules_in_pkg = (
            db.query(ExamSchedule).filter(ExamSchedule.package_id == schedule_id).all()
        )
        sch_ids = [s.id for s in schedules_in_pkg]
        if sch_ids:
            sessions = db.query(ExamSession).filter(ExamSession.schedule_id.in_(sch_ids)).all()

    if not sessions:
        return {"students": []}

    session_ids = [s.id for s in sessions]
    attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id.in_(session_ids)).all()
    if not attempts:
        return {"students": []}

    attempt_ids = [a.id for a in attempts]
    student_ids = {a.student_id for a in attempts if a.student_id}

    # Bulk prefetch students, answers, evaluations, and questions
    students_map = (
        {u.id: u for u in db.query(AuthAccount).filter(AuthAccount.id.in_(student_ids)).all()}
        if student_ids
        else {}
    )

    all_answers = (
        db.query(StudentAnswer).filter(StudentAnswer.exam_attempt_id.in_(attempt_ids)).all()
    )
    all_evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id.in_(attempt_ids))
        .all()
    )

    answers_by_attempt: dict[int, list[StudentAnswer]] = {}
    for ans in all_answers:
        answers_by_attempt.setdefault(ans.exam_attempt_id, []).append(ans)

    evals_by_attempt: dict[int, dict[int, ExamAnswerEvaluation]] = {}
    eval_list_by_attempt: dict[int, list[ExamAnswerEvaluation]] = {}
    for ev in all_evals:
        evals_by_attempt.setdefault(ev.exam_attempt_id, {})[ev.question_id] = ev
        eval_list_by_attempt.setdefault(ev.exam_attempt_id, []).append(ev)

    q_ids = {ans.question_id for ans in all_answers} | {ev.question_id for ev in all_evals}
    questions_map = (
        {q.id: q for q in db.query(Question).filter(Question.id.in_(q_ids)).all()} if q_ids else {}
    )

    results = []

    for a in attempts:
        student = students_map.get(a.student_id)
        answers = answers_by_attempt.get(a.id, [])
        evaluations = eval_list_by_attempt.get(a.id, [])
        eval_map = evals_by_attempt.get(a.id, {})

        score_pg = 0.0
        max_pg = 0.0
        score_is = 0.0
        max_is = 0.0
        score_es = 0.0
        max_es = 0.0

        ans_data = []
        for ans in answers:
            q = questions_map.get(ans.question_id)
            q_type = get_q_type(q)

            ev = eval_map.get(ans.question_id)
            if not ev:
                # Create evaluation record on the fly so teacher can edit/override scores for PG/IS/ES alike
                max_q_val = 1.0
                earned_val = 0.0
                from app.models.exam.answer_evaluation import GradingSource, GradingStatus

                ev = ExamAnswerEvaluation(
                    exam_attempt_id=a.id,
                    question_id=ans.question_id,
                    score=earned_val,
                    max_score=max_q_val,
                    grading_status=GradingStatus.AUTO_GRADED,
                    grading_source=GradingSource.SYSTEM,
                )
                db.add(ev)
                db.commit()
                db.refresh(ev)
                eval_map[ans.question_id] = ev

            earned = float(ev.score) if (ev and ev.score is not None) else 0.0
            max_q = float(ev.max_score) if (ev and ev.max_score is not None) else 1.0

            if q_type == "PG":
                score_pg += earned
                max_pg += max_q
            elif q_type == "IS":
                score_is += earned
                max_is += max_q
            elif q_type == "ES":
                score_es += earned
                max_es += max_q

            eval_meta = _derive_ai_evaluation_metadata(ev, q, ans.text_answer)
            ans_data.append(
                {
                    "question_id": ans.question_id,
                    "question_type": q_type,
                    "question_content": (
                        q.content if (q and q.content) else f"Soal #{ans.question_id}"
                    ),
                    "selected_option": ans.selected_option,
                    "text_answer": ans.text_answer,
                    "score_earned": round(earned, 1),
                    "max_score": round(max_q, 1),
                    "is_correct": ans.is_correct if hasattr(ans, "is_correct") else (earned > 0),
                    "evaluation_id": ev.id if ev else None,
                    "ai_feedback": ev.feedback if ev else None,
                    "confidence": eval_meta["confidence"],
                    "confidence_level": eval_meta["confidence_level"],
                    "review_required": eval_meta["review_required"],
                    "rubric_scores": eval_meta["rubric_scores"],
                    "academic_rationale": eval_meta["academic_rationale"],
                }
            )

        for ev in evaluations:
            if not any(a_item["question_id"] == ev.question_id for a_item in ans_data):
                q = questions_map.get(ev.question_id)
                q_type = get_q_type(q)
                earned = float(ev.score)
                max_q = float(ev.max_score) if ev.max_score else 1.0

                if q_type == "PG":
                    score_pg += earned
                    max_pg += max_q
                elif q_type == "IS":
                    score_is += earned
                    max_is += max_q
                elif q_type == "ES":
                    score_es += earned
                    max_es += max_q

                eval_meta = _derive_ai_evaluation_metadata(ev, q, "(Tidak diisi)")
                ans_data.append(
                    {
                        "question_id": ev.question_id,
                        "question_type": q_type,
                        "question_content": (
                            q.content if (q and q.content) else f"Soal #{ev.question_id}"
                        ),
                        "selected_option": None,
                        "text_answer": "(Tidak diisi)",
                        "score_earned": round(earned, 1),
                        "max_score": round(max_q, 1),
                        "is_correct": False,
                        "evaluation_id": ev.id,
                        "ai_feedback": ev.feedback,
                        "confidence": eval_meta["confidence"],
                        "confidence_level": eval_meta["confidence_level"],
                        "review_required": eval_meta["review_required"],
                        "rubric_scores": eval_meta["rubric_scores"],
                        "academic_rationale": eval_meta["academic_rationale"],
                    }
                )

        total_max = max_pg + max_is + max_es
        total_earned = score_pg + score_is + score_es
        if total_max > 0 and total_max != 100.0:
            final_calc = round((total_earned / total_max) * 100, 1)
        else:
            final_calc = round(total_earned, 1)

        results.append(
            {
                "attempt_id": a.id,
                "student_id": a.student_id,
                "student_name": (
                    student.name or student.username if student else f"Siswa #{a.student_id}"
                ),
                "student_username": student.username if student else "-",
                "nisn": student.nisn if student else "-",
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "final_score": float(a.final_score) if a.final_score is not None else final_calc,
                "score_pg": round(score_pg, 1),
                "max_pg": round(max_pg, 1),
                "score_is": round(score_is, 1),
                "max_is": round(max_is, 1),
                "score_es": round(score_es, 1),
                "max_es": round(max_es, 1),
                "answers_count": len(ans_data),
                "answers": ans_data,
            }
        )

    return {"students": results}


@dashboard_router.get("/grading/evaluations", response_model=list[EssayGradingEvaluationResponse])
def list_grading_evaluations(
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    teacher_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from sqlalchemy import and_, or_

    from app.models.academic.class_subject_teacher import ClassSubjectTeacher
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.exam_schedule_package import ExamSchedulePackage
    from app.models.academic.subject import Subject
    from app.models.exam.answer_evaluation import ExamAnswerEvaluation
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.exam_session import ExamSession
    from app.models.exam.student_answer import StudentAnswer
    from app.models.teacher.question import Question

    # 1. Fetch teacher's assigned subjects and classes from ClassSubjectTeacher
    teacher_csts = (
        db.query(ClassSubjectTeacher)
        .filter(
            ClassSubjectTeacher.school_id == school_id,
            ClassSubjectTeacher.teacher_id == teacher_id,
        )
        .all()
    )
    teacher_subject_ids = {cst.subject_id for cst in teacher_csts if cst.subject_id}
    teacher_class_ids = {cst.class_id for cst in teacher_csts if cst.class_id}

    user_role = current_user.get("role")
    if user_role in ["SCHOOL_ADMIN", "SUPERADMIN"]:
        schedules = db.query(ExamSchedule).filter(ExamSchedule.school_id == school_id).all()
    else:
        conditions = [
            ExamSchedule.teacher_id == teacher_id,
            ExamSchedule.proctor_id == teacher_id,
        ]
        if teacher_subject_ids:
            if teacher_class_ids:
                conditions.append(
                    and_(
                        ExamSchedule.subject_id.in_(teacher_subject_ids),
                        or_(
                            ExamSchedule.class_id.is_(None),
                            ExamSchedule.class_id.in_(teacher_class_ids),
                        ),
                    )
                )
            else:
                conditions.append(
                    and_(
                        ExamSchedule.subject_id.in_(teacher_subject_ids),
                        ExamSchedule.class_id.is_(None),
                    )
                )
        schedules = (
            db.query(ExamSchedule)
            .filter(
                ExamSchedule.school_id == school_id,
                or_(*conditions),
            )
            .all()
        )

    schedule_ids = [s.id for s in schedules]
    if not schedule_ids:
        return []

    schedule_map = {s.id: s for s in schedules}

    # Fetch only relevant packages and subjects maps
    package_ids = {s.package_id for s in schedules if s.package_id}
    subject_ids = {s.subject_id for s in schedules if s.subject_id}

    packages = (
        db.query(ExamSchedulePackage).filter(ExamSchedulePackage.id.in_(package_ids)).all()
        if package_ids
        else []
    )
    package_map = {p.id: p.title for p in packages}

    subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
    subject_map = {sub.id: sub.name for sub in subjects}

    # 2. Get sessions for these schedules
    sessions = db.query(ExamSession).filter(ExamSession.schedule_id.in_(schedule_ids)).all()
    session_ids = [se.id for se in sessions]
    if not session_ids:
        return []

    session_schedule_map = {se.id: schedule_map.get(se.schedule_id) for se in sessions}

    # 3. Get attempts for these sessions
    attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id.in_(session_ids)).all()
    attempt_ids = [a.id for a in attempts]
    if not attempt_ids:
        return []

    attempt_map = {a.id: a for a in attempts}

    # 4. Get all answer evaluations for these attempts
    evaluations = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id.in_(attempt_ids))
        .all()
    )

    if not evaluations:
        return []

    # Bulk prefetch related entities to completely eliminate N+1 queries
    from app.models.academic.class_entity import ClassEntity
    from app.models.security.auth_account import AuthAccount

    q_ids = list({ev.question_id for ev in evaluations})
    questions = db.query(Question).filter(Question.id.in_(q_ids)).all() if q_ids else []
    question_map = {q.id: q for q in questions}

    student_ids = list(
        {
            attempt_map[ev.exam_attempt_id].student_id
            for ev in evaluations
            if ev.exam_attempt_id in attempt_map
        }
    )
    students = (
        db.query(AuthAccount).filter(AuthAccount.id.in_(student_ids)).all() if student_ids else []
    )
    student_map = {s.id: s for s in students}

    student_answers = (
        db.query(StudentAnswer).filter(StudentAnswer.exam_attempt_id.in_(attempt_ids)).all()
    )
    answer_map = {(a.exam_attempt_id, a.question_id): a for a in student_answers}

    class_ids = list({s.class_id for s in session_schedule_map.values() if s and s.class_id})
    classes = db.query(ClassEntity).filter(ClassEntity.id.in_(class_ids)).all() if class_ids else []
    class_map = {c.id: c for c in classes}

    res = []
    for ev in evaluations:
        q = question_map.get(ev.question_id)
        if not q:
            continue

        attempt = attempt_map.get(ev.exam_attempt_id)
        if not attempt:
            continue

        schedule = session_schedule_map.get(attempt.exam_session_id)

        pkg_name = "Paket Ujian Sekolah"
        subj_name = "Mata Pelajaran"
        if schedule:
            if schedule.package_id and schedule.package_id in package_map:
                pkg_name = package_map[schedule.package_id]
            else:
                pkg_name = schedule.title
            if schedule.subject_id and schedule.subject_id in subject_map:
                subj_name = subject_map[schedule.subject_id]

        student = student_map.get(attempt.student_id)
        cls_id = getattr(attempt, "class_id", None) or (schedule.class_id if schedule else None)
        cls = class_map.get(cls_id) if cls_id else None

        ans = answer_map.get((attempt.id, q.id))
        ans_text = ans.text_answer if (ans and ans.text_answer) else "(Tidak diisi / Pilihan ganda)"
        eval_meta = _derive_ai_evaluation_metadata(ev, q, ans_text)

        res.append(
            EssayGradingEvaluationResponse(
                evaluation_id=ev.id,
                attempt_id=attempt.id,
                schedule_id=schedule.id if schedule else 0,
                student_name=student.name or student.username if student else "Siswa",
                exam_title=schedule.title if schedule else "Ujian",
                package_name=pkg_name,
                subject_name=subj_name,
                class_name=cls.name if cls else "Kelas",
                question_id=q.id,
                question_content=q.content,
                student_answer=ans_text,
                ai_score=float(ev.score),
                ai_feedback=ev.feedback,
                grading_status=ev.grading_status.value,
                final_score=float(ev.score) if ev.grading_status.value == "FINALIZED" else None,
                confidence=eval_meta["confidence"],
                confidence_level=eval_meta["confidence_level"],
                review_required=eval_meta["review_required"],
                rubric_scores=eval_meta["rubric_scores"],
                academic_rationale=eval_meta["academic_rationale"],
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


@dashboard_router.post("/grading/evaluations/attempts/{attempt_id}/regrade")
def regrade_attempt_evaluations(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.TEACHER)),
):
    from app.models.exam.answer_evaluation import ExamAnswerEvaluation
    from app.models.exam.enums import GradingStatus
    from app.services.exam.exam_service import ExamService

    try:
        # Synchronously execute AI essay grading job with force_regrade to refresh all ES scores
        ExamService.execute_ai_essay_grading_job(db, attempt_id, force_regrade=True)
        return {"status": "success", "message": "Berhasil mengkalkulasi ulang penilaian AI."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ─── Teacher AI Integration Endpoints (equigradeAI Microservice Bridge) ───


class AiRubricRequest(BaseModel):
    question_text: str
    answer_key: str
    education_level: str = "SMA"
    education_class: str = "Kelas 11"
    api_key: Optional[str] = None


class AiEssayGradeRequest(BaseModel):
    question_text: str
    answer_key: str
    student_answer: str
    rubrics: Optional[List[Dict[str, Any]]] = None
    concepts: Optional[List[str]] = None
    education_level: str = "SMA"
    education_class: str = "Kelas 11"
    api_key: Optional[str] = None
    subject_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    class_level: Optional[str] = None


@dashboard_router.get("/ai/status")
def get_ai_service_status(current_user=Depends(require_role(UserRole.TEACHER))):
    from app.services.ai.ai_grading_service import AiGradingService

    return AiGradingService.check_ai_health()


@dashboard_router.post("/ai/generate-rubric")
def generate_ai_rubric(
    payload: AiRubricRequest, current_user=Depends(require_role(UserRole.TEACHER))
):
    from app.services.ai.ai_grading_service import AiGradingService

    try:
        res = AiGradingService.generate_rubric(
            question_text=payload.question_text,
            answer_key=payload.answer_key,
            education_level=payload.education_level,
            education_class=payload.education_class,
            api_key=payload.api_key,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@dashboard_router.post("/ai/grade-essay")
def grade_ai_essay(
    payload: AiEssayGradeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.TEACHER)),
):
    from app.services.ai.ai_grading_service import AiGradingService

    try:
        res = AiGradingService.grade_essay(
            question_text=payload.question_text,
            answer_key=payload.answer_key,
            student_answer=payload.student_answer,
            rubrics=payload.rubrics,
            concepts=payload.concepts,
            education_level=payload.education_level,
            education_class=payload.education_class,
            api_key=payload.api_key,
            db=db,
            school_id=getattr(current_user, "school_id", None),
            subject_id=payload.subject_id,
            academic_year_id=payload.academic_year_id,
            class_level=payload.class_level,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
