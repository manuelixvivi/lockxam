from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.exceptions.base import BusinessException
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.academic.class_repository import class_repository
from app.repositories.academic.class_subject_teacher_repository import (
    class_subject_teacher_repository,
)
from app.repositories.academic.exam_schedule_repository import exam_schedule_repository
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.academic.teacher_subject_repository import teacher_subject_repository
from app.repositories.school.school_repository import school_repository
from app.repositories.security.auth_repository import auth_repository
from app.repositories.teacher.question_package_repository import question_package_repository
from app.repositories.teacher.question_repository import question_repository


class SchoolStaffService:

    @staticmethod
    def _get_school_domain(db: Session, school_id: int) -> str:
        """Return domain slug for the school via repository."""
        school = school_repository.get_by_id(db, school_id)
        if not school or not school.domain:
            raise BusinessException("Domain sekolah belum dikonfigurasi.", status_code=400)
        return school.domain

    @staticmethod
    def list_teachers(db: Session, school_id: int) -> list[AuthAccount]:
        """List teachers and project relational assignments onto compatibility arrays."""
        teachers = auth_repository.list_teachers_by_school(db, school_id)

        active_classes = [c for c in class_repository.list_by_school(db, school_id) if c.is_active]
        active_class_names = {c.name for c in active_classes}

        active_subjects = subject_repository.list_by_school(db, school_id)
        active_subject_dict = {}
        for s in active_subjects:
            active_subject_dict[s.id] = s.name
            active_subject_dict[s.name.strip().lower()] = s.name
            if s.code:
                active_subject_dict[s.code.strip().lower()] = s.name

        for t in teachers:
            # 1. Sync classes_taught
            assigned_csts = class_subject_teacher_repository.list_by_teacher(db, t.id)
            assigned_class_ids = [cst.class_id for cst in assigned_csts]
            cst_class_names = []
            if assigned_class_ids:
                cst_classes = class_repository.get_by_ids(db, assigned_class_ids)
                cst_class_names = [c.name for c in cst_classes if c.is_active]

            existing_taught_classes = list(t.classes_taught or [])
            valid_taught_classes = [
                c_name for c_name in existing_taught_classes if c_name in active_class_names
            ]

            combined_class_names = list(dict.fromkeys(valid_taught_classes + cst_class_names))

            if t.classes_taught != combined_class_names:
                t.classes_taught = combined_class_names

            # 2. Sync subjects_taught (Read-only compatibility projection)
            assigned_ts = teacher_subject_repository.list_by_teacher(db, t.id)

            subject_ids_from_cst = [cst.subject_id for cst in assigned_csts if cst.subject_id]
            subject_ids_from_ts = [ts.subject_id for ts in assigned_ts if ts.subject_id]
            combined_subject_ids = list(dict.fromkeys(subject_ids_from_cst + subject_ids_from_ts))

            relational_subject_names = []
            if combined_subject_ids:
                relational_subjects = subject_repository.get_by_ids(db, combined_subject_ids)
                relational_subject_names = [
                    s.name for s in relational_subjects if s.school_id == school_id
                ]

            combined_subject_names = list(dict.fromkeys(relational_subject_names))

            if t.subjects_taught != combined_subject_names:
                t.subjects_taught = combined_subject_names

        db.flush()
        return teachers

    @staticmethod
    def create_teacher(
        db: Session,
        school_id: int,
        name: str,
        nip: str,
        gender: str,
        registered_year: int,
        classes_taught: list[str],
        teacher_code: str | None = None,
    ) -> tuple[AuthAccount, str]:
        """
        Buat akun guru baru dengan format:
          Username : {NIP}@guru.{domain}
          Password : eQu!6r4d3{NIP}  (wajib ganti setelah login pertama)

        subjects_taught is NOT accepted here.
        Competency (TeacherSubject) must be assigned via SubjectService.assign_teacher_competency().
        """
        domain = SchoolStaffService._get_school_domain(db, school_id)

        username = f"{nip}@guru.{domain}"
        default_password = f"eQu!6r4d3{nip}"

        # Check username uniqueness via repository
        existing = auth_repository.get_by_username(db, username)
        if existing:
            raise BusinessException(
                f"NIP '{nip}' sudah terdaftar sebagai guru di sekolah ini.",
                status_code=409,
            )

        # Check / generate teacher_code via repository
        if not teacher_code or not teacher_code.strip():
            teacher_code = f"T-{nip}"
        else:
            teacher_code = teacher_code.strip().upper()

        existing_code = auth_repository.get_teacher_by_code(db, school_id, teacher_code)
        if existing_code:
            raise BusinessException(
                f"Kode Guru '{teacher_code}' sudah digunakan oleh guru lain.",
                status_code=409,
            )

        account = AuthAccount(
            school_id=school_id,
            username=username,
            password_hash=hash_password(default_password),
            role=UserRole.TEACHER,
            is_active=True,
            must_change_password=True,
            name=name,
            nip=nip,
            teacher_code=teacher_code,
            gender=gender,
            registered_year=registered_year,
            classes_taught=classes_taught,
            # subjects_taught intentionally omitted: derived from TeacherSubject only.
        )
        auth_repository.create(db, account)
        db.flush()
        return account, default_password

    @staticmethod
    def update_teacher(
        db: Session,
        school_id: int,
        teacher_public_id: str,
        name: str | None = None,
        nip: str | None = None,
        teacher_code: str | None = None,
        gender: str | None = None,
        registered_year: int | None = None,
        classes_taught: list[str] | None = None,
        is_active: bool | None = None,
        update_fields: set[str] | None = None,
        # subjects_taught intentionally absent: competency is managed via TeacherSubject only.
        # Any caller passing subjects_taught is ignored at this boundary.
    ) -> AuthAccount:
        teacher = auth_repository.get_by_public_id_and_school(
            db, school_id, teacher_public_id, role="TEACHER"
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        if update_fields is None or "teacher_code" in update_fields:
            if teacher_code is not None and teacher_code.strip():
                new_code = teacher_code.strip().upper()
                if new_code != teacher.teacher_code:
                    existing_code = auth_repository.get_teacher_by_code(db, school_id, new_code)
                    if existing_code and existing_code.id != teacher.id:
                        raise BusinessException(
                            f"Kode Guru '{new_code}' sudah digunakan oleh guru lain.",
                            status_code=409,
                        )
                    teacher.teacher_code = new_code

        if update_fields is None or "name" in update_fields:
            if name is not None:
                teacher.name = name
        if update_fields is None or "nip" in update_fields:
            if nip is not None:
                teacher.nip = nip
        if update_fields is None or "gender" in update_fields:
            if gender is not None:
                teacher.gender = gender
        if update_fields is None or "registered_year" in update_fields:
            if registered_year is not None:
                teacher.registered_year = registered_year
        if update_fields is None or "classes_taught" in update_fields:
            if classes_taught is not None:
                teacher.classes_taught = classes_taught
        # subjects_taught block intentionally removed.
        # Writing teacher.subjects_taught here would bypass TeacherSubject authority.
        if update_fields is None or "is_active" in update_fields:
            if is_active is not None:
                teacher.is_active = is_active

        auth_repository.update(db, teacher)
        db.flush()
        return teacher

    @staticmethod
    def delete_teacher(db: Session, school_id: int, teacher_public_id: str) -> None:
        teacher = auth_repository.get_by_public_id_and_school(
            db, school_id, teacher_public_id, role="TEACHER"
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        # Invariant check: Cannot delete teacher if assigned to active exam schedules
        schedules = exam_schedule_repository.list_by_teacher(db, teacher.id)
        if schedules:
            raise BusinessException(
                f"Guru ini masih terdaftar sebagai pengampu pada {len(schedules)} jadwal ujian. "
                "Hapus atau perbarui jadwal ujian tersebut terlebih dahulu sebelum menghapus akun guru.",
                status_code=409,
            )

        # Hapus assignments & competency via repositories
        teacher_subject_repository.delete_by_teacher(db, teacher.id)
        class_subject_teacher_repository.delete_by_teacher(db, teacher.id)

        # Unlink packages & questions safely via repositories
        question_package_repository.delete_by_owner(db, teacher.id)
        question_repository.delete_by_owner(db, teacher.id)

        auth_repository.delete(db, teacher)
        db.flush()

    @staticmethod
    def toggle_teacher_active(db: Session, school_id: int, teacher_public_id: str) -> AuthAccount:
        """Toggle active status while preserving historical data."""
        teacher = auth_repository.get_by_public_id_and_school(
            db, school_id, teacher_public_id, role="TEACHER"
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        teacher.is_active = not teacher.is_active
        auth_repository.update(db, teacher)
        db.flush()
        return teacher

    @staticmethod
    def reset_teacher_password(
        db: Session, school_id: int, teacher_public_id: str
    ) -> tuple[AuthAccount, str]:
        """Reset password guru ke default."""
        teacher = auth_repository.get_by_public_id_and_school(
            db, school_id, teacher_public_id, role="TEACHER"
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        nip = teacher.nip or teacher.username.split("@")[0]
        new_password = f"eQu!6r4d3{nip}"

        teacher.password_hash = hash_password(new_password)
        teacher.must_change_password = True
        auth_repository.update(db, teacher)
        db.flush()
        return teacher, new_password

    @staticmethod
    def import_teachers_xlsx(
        db: Session,
        school_id: int,
        teachers_data: list[dict],
    ) -> tuple[bool, list[AuthAccount], list[dict]]:
        errors = []
        validated_batch_data = []

        seen_usernames = set()
        seen_nips = set()
        seen_teacher_codes = set()

        domain = SchoolStaffService._get_school_domain(db, school_id)

        # First Pass: Validate ALL teachers before persistence
        for idx, item in enumerate(teachers_data):
            row_num = item.get("row_num") or (idx + 2)
            name = str(item.get("name") or "").strip()
            nip = str(item.get("nip") or "").strip().replace(" ", "")
            teacher_code = str(item.get("teacher_code") or "").strip()
            gender = str(item.get("gender") or "").strip().upper()
            registered_year_raw = item.get("registered_year")

            if not name:
                errors.append(
                    {
                        "row": row_num,
                        "field": "name",
                        "value": "",
                        "code": "TEACHER_NAME_REQUIRED",
                        "message": "Nama Lengkap Guru wajib diisi.",
                    }
                )
                continue

            if not gender:
                errors.append(
                    {
                        "row": row_num,
                        "field": "gender",
                        "value": "",
                        "code": "TEACHER_GENDER_REQUIRED",
                        "message": "Jenis Kelamin wajib diisi.",
                    }
                )
                continue

            if gender not in ["L", "P"]:
                errors.append(
                    {
                        "row": row_num,
                        "field": "gender",
                        "value": gender,
                        "code": "INVALID_GENDER",
                        "message": "Jenis Kelamin harus bernilai 'L' (Laki-laki) atau 'P' (Perempuan).",
                    }
                )
                continue

            if not nip:
                errors.append(
                    {
                        "row": row_num,
                        "field": "nip",
                        "value": "",
                        "code": "TEACHER_NIP_REQUIRED",
                        "message": "NIP wajib diisi.",
                    }
                )
                continue

            if not nip.isdigit() or len(nip) < 4 or len(nip) > 20:
                errors.append(
                    {
                        "row": row_num,
                        "field": "nip",
                        "value": nip,
                        "code": "INVALID_NIP",
                        "message": "NIP harus berupa angka antara 4 sampai 20 digit.",
                    }
                )
                continue

            if nip in seen_nips:
                errors.append(
                    {
                        "row": row_num,
                        "field": "nip",
                        "value": nip,
                        "code": "DUPLICATE_NIP_IN_FILE",
                        "message": f"NIP '{nip}' ganda di dalam file Excel.",
                    }
                )
                continue
            seen_nips.add(nip)

            # Check duplicate username
            username = f"{nip}@guru.{domain}"
            if username in seen_usernames:
                errors.append(
                    {
                        "row": row_num,
                        "field": "username",
                        "value": username,
                        "code": "DUPLICATE_USERNAME_IN_FILE",
                        "message": f"Username '{username}' ganda di dalam file Excel.",
                    }
                )
                continue
            seen_usernames.add(username)

            existing_uname = auth_repository.get_by_username(db, username)
            if existing_uname:
                errors.append(
                    {
                        "row": row_num,
                        "field": "nip",
                        "value": nip,
                        "code": "DUPLICATE_USERNAME_IN_DB",
                        "message": f"NIP '{nip}' sudah terdaftar sebagai guru di sekolah ini.",
                    }
                )
                continue

            # Check teacher code
            if not teacher_code:
                t_code_clean = f"T-{nip}"
            else:
                t_code_clean = teacher_code.strip().upper()

            if t_code_clean in seen_teacher_codes:
                errors.append(
                    {
                        "row": row_num,
                        "field": "teacher_code",
                        "value": t_code_clean,
                        "code": "DUPLICATE_TEACHER_CODE_IN_FILE",
                        "message": f"Kode Guru '{t_code_clean}' ganda di dalam file Excel.",
                    }
                )
                continue
            seen_teacher_codes.add(t_code_clean)

            existing_code = auth_repository.get_teacher_by_code(db, school_id, t_code_clean)
            if existing_code:
                errors.append(
                    {
                        "row": row_num,
                        "field": "teacher_code",
                        "value": t_code_clean,
                        "code": "DUPLICATE_TEACHER_CODE_IN_DB",
                        "message": f"Kode Guru '{t_code_clean}' sudah digunakan oleh guru lain.",
                    }
                )
                continue

            # Validate registered_year
            registered_year_val = None
            if registered_year_raw is not None and str(registered_year_raw).strip() != "":
                try:
                    registered_year_val = int(float(str(registered_year_raw).strip()))
                    if registered_year_val <= 1900 or registered_year_val >= 2100:
                        raise ValueError()
                except ValueError:
                    errors.append(
                        {
                            "row": row_num,
                            "field": "registered_year",
                            "value": str(registered_year_raw),
                            "code": "INVALID_REGISTERED_YEAR",
                            "message": "Tahun terdaftar harus berupa angka tahun yang valid (antara 1901 dan 2099).",
                        }
                    )
                    continue
            else:
                registered_year_val = datetime.now().year

            validated_batch_data.append(
                {
                    "name": name,
                    "nip": nip,
                    "username": username,
                    "teacher_code": t_code_clean,
                    "gender": gender,
                    "registered_year": registered_year_val,
                }
            )

        if errors:
            return False, [], errors

        # Second Pass: Atomic Persistence under transaction/savepoint
        created_teachers = []
        try:
            savepoint = db.begin_nested()
            for teacher_info in validated_batch_data:
                default_password = f"eQu!6r4d3{teacher_info['nip']}"
                account = AuthAccount(
                    school_id=school_id,
                    username=teacher_info["username"],
                    password_hash=hash_password(default_password),
                    role=UserRole.TEACHER,
                    is_active=True,
                    must_change_password=True,
                    name=teacher_info["name"],
                    nip=teacher_info["nip"],
                    teacher_code=teacher_info["teacher_code"],
                    gender=teacher_info["gender"],
                    registered_year=teacher_info["registered_year"],
                    classes_taught=[],
                )
                auth_repository.create(db, account)
                created_teachers.append(account)

            db.flush()
            savepoint.commit()
            return True, created_teachers, []

        except Exception as e:
            savepoint.rollback()
            db.rollback()
            from app.logging.logger import logger

            logger.error(f"Teacher bulk import persistence failure: {str(e)}", exc_info=True)
            raise BusinessException(
                "Gagal melakukan penyimpanan data ke database. Terjadi kesalahan internal pada server.",
                status_code=500,
            )
