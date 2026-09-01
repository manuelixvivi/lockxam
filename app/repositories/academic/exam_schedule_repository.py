from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.exam_schedule import ExamSchedule
from app.repositories.base_repository import BaseRepository


class ExamScheduleRepository(BaseRepository[ExamSchedule]):
    def __init__(self):
        super().__init__(ExamSchedule)

    def get_by_public_id(self, db: Session, public_id: UUID) -> ExamSchedule | None:
        return db.scalar(select(ExamSchedule).where(ExamSchedule.public_id == public_id))

    def list_by_school(
        self,
        db: Session,
        school_id: int,
        academic_year_id: int | None = None,
        academic_semester_id: int | None = None,
        class_id: int | None = None,
    ) -> list[ExamSchedule]:
        query = select(ExamSchedule).where(ExamSchedule.school_id == school_id)
        if academic_year_id is not None:
            query = query.where(ExamSchedule.academic_year_id == academic_year_id)
        if academic_semester_id is not None:
            query = query.where(ExamSchedule.academic_semester_id == academic_semester_id)
        if class_id is not None:
            query = query.where(ExamSchedule.class_id == class_id)
        query = query.order_by(ExamSchedule.start_time.asc())
        return list(db.scalars(query).all())

    def list_active_for_classes(
        self, db: Session, school_id: int, class_ids: list[int]
    ) -> list[ExamSchedule]:
        if not class_ids:
            return []
        stmt = select(ExamSchedule).where(
            ExamSchedule.school_id == school_id,
            ExamSchedule.class_id.in_(class_ids),
            ExamSchedule.status.in_(["READY", "ACTIVE"]),
        )
        return list(db.scalars(stmt).all())

    def list_eligible_for_classes(
        self, db: Session, school_id: int, class_ids: list[int]
    ) -> list[ExamSchedule]:
        """
        Mengambil semua jadwal ujian yang relevan untuk siswa:
        - READY/ACTIVE   : Ujian akan datang atau sedang berlangsung
        - CLOSED/FINISHED/EXPIRED : Ujian sudah berakhir — perlu untuk mendeteksi
          ujian yang dilewatkan (MISSED) jika siswa tidak pernah berpartisipasi.
        CANCELLED dikecualikan.
        """
        if not class_ids:
            return []
        stmt = (
            select(ExamSchedule)
            .where(
                ExamSchedule.school_id == school_id,
                ExamSchedule.class_id.in_(class_ids),
                ExamSchedule.status.notin_(["CANCELLED"]),
            )
            .order_by(ExamSchedule.start_time.desc())
        )
        return list(db.scalars(stmt).all())

    def get_by_ids(self, db: Session, schedule_ids: list[int]) -> list[ExamSchedule]:
        if not schedule_ids:
            return []
        stmt = select(ExamSchedule).where(ExamSchedule.id.in_(schedule_ids))
        return list(db.scalars(stmt).all())

    def find_class_schedule_overlap(
        self,
        db: Session,
        school_id: int,
        class_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_id: int | None = None,
    ) -> ExamSchedule | None:
        stmt = select(ExamSchedule).where(
            ExamSchedule.school_id == school_id,
            ExamSchedule.class_id == class_id,
            ExamSchedule.status.notin_(["CANCELLED"]),
            ExamSchedule.start_time < end_time,
            ExamSchedule.end_time > start_time,
        )
        if exclude_id is not None:
            stmt = stmt.where(ExamSchedule.id != exclude_id)
        return db.scalar(stmt)

    def list_by_teacher(self, db: Session, teacher_id: int) -> list[ExamSchedule]:
        return list(
            db.scalars(
                select(ExamSchedule)
                .where(ExamSchedule.teacher_id == teacher_id)
                .order_by(ExamSchedule.start_time.asc())
            ).all()
        )

    def list_by_proctor(self, db: Session, proctor_id: int) -> list[ExamSchedule]:
        return list(
            db.scalars(
                select(ExamSchedule)
                .where(ExamSchedule.proctor_id == proctor_id)
                .order_by(ExamSchedule.start_time.asc())
            ).all()
        )

    def list_by_package(self, db: Session, package_id: int) -> list[ExamSchedule]:
        return list(
            db.scalars(
                select(ExamSchedule)
                .where(ExamSchedule.package_id == package_id)
                .order_by(ExamSchedule.start_time.asc())
            ).all()
        )


exam_schedule_repository = ExamScheduleRepository()
