from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.subject import Subject
from app.models.academic.teacher_subject import TeacherSubject
from app.models.security.auth_account import AuthAccount
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.academic.teacher_subject_repository import (
    teacher_subject_repository,
)
from app.repositories.security.auth_repository import (
    auth_repository,
)


class SubjectService:
    @staticmethod
    def create_subject(
        db: Session,
        school_id: int,
        code: str,
        name: str,
        description: str | None = None,
    ) -> Subject:
        code_clean = code.strip().upper()
        name_clean = name.strip()
        if not code_clean or not name_clean:
            raise BusinessException("Kode dan Nama Mata Pelajaran wajib diisi.", status_code=400)

        existing = subject_repository.get_by_code(db, school_id, code_clean)
        if existing:
            raise BusinessException(
                f"Mata pelajaran dengan kode '{code_clean}' sudah terdaftar di sekolah ini.",
                status_code=400,
            )

        subj = Subject(
            school_id=school_id,
            code=code_clean,
            name=name_clean,
            description=description.strip() if description else None,
            is_active=True,
        )
        return subject_repository.create(db, subj)

    @staticmethod
    def update_subject(
        db: Session,
        school_id: int,
        public_id: UUID,
        code: str,
        name: str,
        description: str | None = None,
        is_active: bool = True,
    ) -> Subject:
        subj = subject_repository.get_by_public_id(db, public_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        code_clean = code.strip().upper()
        name_clean = name.strip()
        if not code_clean or not name_clean:
            raise BusinessException("Kode dan Nama Mata Pelajaran wajib diisi.", status_code=400)

        if code_clean != subj.code:
            raise BusinessException(
                f"Kode mata pelajaran ('{subj.code}') bersifat IMMUTABLE dan tidak dapat diubah setelah dibuat.",
                status_code=400,
            )

        subj.name = name_clean
        subj.description = description.strip() if description else None
        subj.is_active = is_active
        return subject_repository.update(db, subj)

    @staticmethod
    def delete_subject(db: Session, school_id: int, public_id: UUID) -> None:
        subj = subject_repository.get_by_public_id(db, public_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        if subject_repository.is_subject_in_use(db, subj.id):
            # Non-destructive deactivation (preserves all historical relationships)
            subj.is_active = False
            db.flush()
        else:
            # Safe hard delete for unused master record only
            subject_repository.delete(db, subj)
            db.flush()

    @staticmethod
    def list_subjects(db: Session, school_id: int, is_active: bool | None = None) -> list[Subject]:
        return subject_repository.list_by_school(db, school_id, is_active=is_active)

    @staticmethod
    def assign_teacher_competency(
        db: Session, school_id: int, teacher_id: int, subject_id: int
    ) -> TeacherSubject:
        teacher = auth_repository.get_by_id(db, teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        # TeacherSubject is the ONLY authority for competency.
        # Do NOT write teacher.subjects_taught here.
        # The derived projection is computed at read-time in SchoolStaffService.list_teachers().
        return teacher_subject_repository.assign(db, school_id, teacher_id, subject_id)

    @staticmethod
    def unassign_teacher_competency(db: Session, teacher_id: int, subject_id: int) -> bool:
        # TeacherSubject DELETE is the ONLY authority for removing competency.
        # Do NOT write teacher.subjects_taught here.
        # The derived projection is computed at read-time in SchoolStaffService.list_teachers().
        return teacher_subject_repository.unassign(db, teacher_id, subject_id)

    @staticmethod
    def list_qualified_teachers_for_subject(
        db: Session, school_id: int, subject_id: int
    ) -> list[AuthAccount]:
        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id or not subj.is_active:
            return []

        teacher_ids = teacher_subject_repository.list_teacher_ids_by_subject(
            db, school_id, subject_id
        )
        return [
            t
            for t in [auth_repository.get_by_id(db, tid) for tid in teacher_ids]
            if t and t.is_active and t.school_id == school_id
        ]

    @staticmethod
    def import_subjects_xlsx(
        db: Session,
        school_id: int,
        subjects_data: list[dict],
    ) -> tuple[bool, list[Subject], list[dict]]:
        errors = []
        validated_batch_data = []
        seen_codes = set()

        # First Pass: Validate ALL subjects before persistence
        for idx, item in enumerate(subjects_data):
            row_num = item.get("row_num") or (idx + 2)
            code = str(item.get("code") or "").strip()
            name = str(item.get("name") or "").strip()
            description = item.get("description")

            if not code:
                errors.append(
                    {
                        "row": row_num,
                        "field": "code",
                        "value": "",
                        "code": "SUBJECT_CODE_REQUIRED",
                        "message": "Kode Mata Pelajaran wajib diisi.",
                    }
                )
                continue

            code_clean = code.upper()

            if code_clean in seen_codes:
                errors.append(
                    {
                        "row": row_num,
                        "field": "code",
                        "value": code,
                        "code": "DUPLICATE_SUBJECT_CODE_IN_FILE",
                        "message": f"Kode mata pelajaran '{code_clean}' ganda di dalam file Excel.",
                    }
                )
                continue
            seen_codes.add(code_clean)

            existing = subject_repository.get_by_code(db, school_id, code_clean)
            if existing:
                errors.append(
                    {
                        "row": row_num,
                        "field": "code",
                        "value": code,
                        "code": "DUPLICATE_SUBJECT_CODE_IN_DB",
                        "message": f"Mata pelajaran dengan kode '{code_clean}' sudah terdaftar di sekolah ini.",
                    }
                )
                continue

            if not name:
                errors.append(
                    {
                        "row": row_num,
                        "field": "name",
                        "value": "",
                        "code": "SUBJECT_NAME_REQUIRED",
                        "message": "Nama Mata Pelajaran wajib diisi.",
                    }
                )
                continue

            validated_batch_data.append(
                {
                    "code": code_clean,
                    "name": name,
                    "description": description.strip() if description else None,
                }
            )

        if errors:
            return False, [], errors

        # Second Pass: Atomic Persistence under transaction/savepoint
        created_subjects = []
        try:
            savepoint = db.begin_nested()
            for subject_info in validated_batch_data:
                subj = Subject(
                    school_id=school_id,
                    code=subject_info["code"],
                    name=subject_info["name"],
                    description=subject_info["description"],
                    is_active=True,
                )
                subject_repository.create(db, subj)
                created_subjects.append(subj)

            db.flush()
            savepoint.commit()
            return True, created_subjects, []

        except Exception as e:
            savepoint.rollback()
            db.rollback()
            from app.logging.logger import logger

            logger.error(f"Subject bulk import persistence failure: {str(e)}", exc_info=True)
            raise BusinessException(
                "Gagal melakukan penyimpanan data ke database. Terjadi kesalahan internal pada server.",
                status_code=500,
            )
