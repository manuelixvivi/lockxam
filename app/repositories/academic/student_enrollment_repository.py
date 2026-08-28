from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.enums import EnrollmentStatus
from app.models.academic.student_class_enrollment import StudentClassEnrollment
from app.repositories.base_repository import BaseRepository


class StudentEnrollmentRepository(BaseRepository[StudentClassEnrollment]):
    def __init__(self):
        super().__init__(StudentClassEnrollment)

    def get_by_public_id(
        self, db: Session, public_id: UUID
    ) -> StudentClassEnrollment | None:
        return db.scalar(
            select(StudentClassEnrollment).where(
                StudentClassEnrollment.public_id == public_id
            )
        )

    def get_active_enrollment(
        self, db: Session, student_id: int, academic_year_id: int
    ) -> StudentClassEnrollment | None:
        return db.scalar(
            select(StudentClassEnrollment).where(
                StudentClassEnrollment.student_id == student_id,
                StudentClassEnrollment.academic_year_id == academic_year_id,
                StudentClassEnrollment.status == EnrollmentStatus.ACTIVE.value,
            )
        )

    def get_active_by_student(self, db: Session, student_id: int) -> StudentClassEnrollment | None:
        return db.scalar(
            select(StudentClassEnrollment).where(
                StudentClassEnrollment.student_id == student_id,
                StudentClassEnrollment.status == EnrollmentStatus.ACTIVE.value,
            )
        )

    def list_active_by_student(self, db: Session, student_id: int) -> list[StudentClassEnrollment]:
        return list(
            db.scalars(
                select(StudentClassEnrollment).where(
                    StudentClassEnrollment.student_id == student_id,
                    StudentClassEnrollment.status == EnrollmentStatus.ACTIVE.value,
                )
            ).all()
        )

    def list_by_class(
        self, db: Session, class_id: int, status: str | list[str] | None = None
    ) -> list[StudentClassEnrollment]:
        query = select(StudentClassEnrollment).where(
            StudentClassEnrollment.class_id == class_id
        )
        if status is not None:
            if isinstance(status, list):
                query = query.where(StudentClassEnrollment.status.in_(status))
            else:
                query = query.where(StudentClassEnrollment.status == status)
        else:
            query = query.where(StudentClassEnrollment.status != EnrollmentStatus.DROPPED.value)
        query = query.order_by(StudentClassEnrollment.created_at.asc())
        return list(db.scalars(query).all())

    def list_history_by_student(
        self, db: Session, student_id: int
    ) -> list[StudentClassEnrollment]:
        return list(
            db.scalars(
                select(StudentClassEnrollment)
                .where(StudentClassEnrollment.student_id == student_id)
                .order_by(StudentClassEnrollment.created_at.desc())
            ).all()
        )


student_enrollment_repository = StudentEnrollmentRepository()
