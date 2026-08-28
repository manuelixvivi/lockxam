from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.class_entity import ClassEntity
from app.repositories.academic.academic_year_repository import (
    academic_year_repository,
)
from app.repositories.academic.class_repository import class_repository


class ClassService:
    @staticmethod
    def create_class(
        db: Session,
        school_id: int,
        academic_year_id: int,
        name: str,
        grade_level: str | None = None,
    ) -> ClassEntity:
        name_clean = name.strip()
        if not name_clean:
            raise BusinessException("Nama kelas wajib diisi.", status_code=400)

        year = academic_year_repository.get_by_id(db, academic_year_id)
        if not year or year.school_id != school_id:
            raise BusinessException("Tahun Ajaran tidak ditemukan.", status_code=404)

        # Invariant ACADEMIC-CLASS-001: Unique Class Name per (school_id, academic_year_id)
        existing = class_repository.get_by_name(db, school_id, academic_year_id, name_clean)
        if existing:
            raise BusinessException(
                f"Kelas '{name_clean}' sudah ada pada tahun ajaran '{year.name}'.",
                status_code=400,
            )

        new_class = ClassEntity(
            school_id=school_id,
            academic_year_id=academic_year_id,
            name=name_clean,
            grade_level=grade_level.strip() if grade_level else None,
            is_active=True,
        )
        return class_repository.create(db, new_class)

    @staticmethod
    def update_class(
        db: Session,
        school_id: int,
        public_id: UUID,
        name: str,
        grade_level: str | None = None,
        is_active: bool = True,
    ) -> ClassEntity:
        cls = class_repository.get_by_public_id(db, public_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        name_clean = name.strip()
        if not name_clean:
            raise BusinessException("Nama kelas wajib diisi.", status_code=400)

        if name_clean != cls.name:
            existing = class_repository.get_by_name(db, school_id, cls.academic_year_id, name_clean)
            if existing and existing.id != cls.id:
                raise BusinessException(
                    f"Kelas '{name_clean}' sudah ada pada tahun ajaran ini.",
                    status_code=400,
                )

        cls.name = name_clean
        cls.grade_level = grade_level.strip() if grade_level else None
        cls.is_active = is_active
        return class_repository.update(db, cls)

    @staticmethod
    def delete_class(db: Session, school_id: int, public_id: UUID) -> None:
        cls = class_repository.get_by_public_id(db, public_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        if class_repository.has_historical_records(db, cls.id):
            # Soft delete class so historical records and student enrollment logs stay 100% intact
            cls.is_active = False
            db.flush()
        else:
            class_repository.delete(db, cls)

    @staticmethod
    def list_classes_by_year(
        db: Session,
        school_id: int,
        academic_year_id: int,
        is_active: bool | None = None,
    ) -> list[ClassEntity]:
        return class_repository.list_by_academic_year(
            db, school_id, academic_year_id, is_active=is_active
        )
