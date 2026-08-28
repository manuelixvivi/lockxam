import copy
from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.enums import ExamScheduleStatus
from app.models.academic.exam_snapshot import ExamSnapshot
from app.models.teacher.enums import PackageStatus
from app.repositories.academic.exam_schedule_repository import (
    exam_schedule_repository,
)
from app.repositories.academic.exam_snapshot_repository import (
    exam_snapshot_repository,
)
from app.repositories.teacher.question_package_repository import (
    question_package_repository,
)


class ExamSnapshotService:
    @staticmethod
    def create_immutable_snapshot(
        db: Session,
        school_id: int,
        teacher_id: int,
        schedule_public_id: UUID,
        package_public_id: UUID,
    ) -> ExamSnapshot:
        """
        Creates an atomic, immutable ExamSnapshot when a teacher finalizes/selects
        their QuestionPackage for an ExamSchedule.
        Enforces EXAM-HISTORY-001, EXAM-HISTORY-002, and EXAM-HISTORY-003.
        """
        schedule = exam_schedule_repository.get_by_public_id(db, schedule_public_id)
        if not schedule or schedule.school_id != school_id:
            raise BusinessException("Jadwal ujian tidak ditemukan.", status_code=404)

        if schedule.teacher_id != teacher_id:
            raise BusinessException(
                "Hanya guru pengampu yang berhak menentukan paket soal untuk jadwal ujian ini.",
                status_code=403,
            )

        # Check if snapshot already created — IMMUTABILITY ENFORCEMENT
        existing_snapshot = exam_snapshot_repository.get_by_schedule_id(db, schedule.id)
        if existing_snapshot:
            raise BusinessException(
                "Snapshot paket soal untuk jadwal ini telah dikunci (IMMUTABLE) dan tidak dapat diubah atau ditimpa.",
                status_code=400,
            )

        # Validate Question Package
        pkg = question_package_repository.get_by_public_id(db, package_public_id)
        if not pkg:
            raise BusinessException("Paket soal tidak ditemukan.", status_code=404)

        if pkg.owner_teacher_account_id != teacher_id:
            raise BusinessException("Paket soal bukan milik guru bersangkutan.", status_code=403)

        # Accept READY or COMPLETE
        pkg_status_val = pkg.status.value if hasattr(pkg.status, "value") else str(pkg.status)
        if pkg_status_val not in (PackageStatus.READY.value, "COMPLETE", "READY"):
            raise BusinessException(
                "Paket soal belum berstatus READY/COMPLETE dan belum siap digunakan untuk ujian.",
                status_code=400,
            )

        if not pkg.items or len(pkg.items) == 0:
            raise BusinessException(
                "Paket soal tidak memiliki butir soal.", status_code=400
            )

        # Deep-copy all questions, options, answer keys, rubrics, and scores into frozen JSON
        frozen_questions = []
        total_points = 0.0

        # Sort items by canonical order
        sorted_items = sorted(pkg.items, key=lambda it: it.canonical_order)

        for it in sorted_items:
            q = it.question
            if not q:
                continue

            frozen_item = {
                "question_id": q.id,
                "order": it.canonical_order,
                "score": float(it.score),
                "type": str(q.type.value if hasattr(q.type, "value") else q.type),
                "content": str(q.content),
                "options": copy.deepcopy(q.options) if q.options else [],
                "answer_key": str(q.answer_key),
                "rubrics": copy.deepcopy(q.rubrics) if q.rubrics else [],
                "ai_grading": bool(q.ai_grading),
                "subject": str(q.subject) if q.subject else None,
            }
            frozen_questions.append(frozen_item)
            total_points += float(it.score)

        snapshot_payload = {
            "package_id": pkg.id,
            "package_public_id": str(pkg.public_id),
            "package_name": pkg.name,
            "package_subject": pkg.subject,
            "total_items": len(frozen_questions),
            "questions": frozen_questions,
            "rules_config": {
                "lock_browser": getattr(schedule, "lock_browser", True),
                "eyd_language_evaluation": getattr(schedule, "eyd_language_evaluation", False),
                "randomize_per_type": getattr(schedule, "randomize_per_type", True),
            },
        }

        # Create immutable ExamSnapshot
        snapshot = ExamSnapshot(
            school_id=school_id,
            exam_schedule_id=schedule.id,
            question_package_id=pkg.id,
            teacher_id=teacher_id,
            class_id=schedule.class_id,
            subject_id=schedule.subject_id,
            academic_year_id=schedule.academic_year_id,
            academic_semester_id=schedule.academic_semester_id,
            snapshot_data=snapshot_payload,
            total_questions=len(frozen_questions),
            total_points=int(total_points) if total_points > 0 else 100,
            duration_minutes=schedule.duration_minutes,
            is_locked=True,
        )
        created_snapshot = exam_snapshot_repository.create(db, snapshot)

        # Advance Schedule status to READY
        schedule.status = ExamScheduleStatus.READY.value
        db.flush()

        return created_snapshot

    @staticmethod
    def get_snapshot_by_schedule(
        db: Session, schedule_id: int
    ) -> ExamSnapshot | None:
        return exam_snapshot_repository.get_by_schedule_id(db, schedule_id)
