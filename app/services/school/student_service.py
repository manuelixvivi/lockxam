from datetime import date, datetime
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.exceptions.base import BusinessException
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.security.auth_repository import auth_repository


class SchoolStudentService:

    @staticmethod
    def _get_school_domain(db: Session, school_id: int) -> str:
        """Return domain slug for the school."""
        school = db.query(School).filter(School.id == school_id).first()
        if not school or not school.domain:
            raise BusinessException("Domain sekolah belum dikonfigurasi.", status_code=400)
        return school.domain

    @staticmethod
    def list_students(db: Session, school_id: int) -> list[AuthAccount]:
        return (
            db.query(AuthAccount)
            .filter(
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
            )
            .order_by(AuthAccount.created_at.desc())
            .all()
        )

    @staticmethod
    def create_student(
        db: Session,
        school_id: int,
        name: str,
        nisn: str,
        nis: str | None = None,
        birth_date: date | None = None,
        gender: str | None = None,
        class_name: str | None = None,
        registered_year: int | None = None,
    ) -> tuple[AuthAccount, str]:
        """
        Buat akun siswa baru dengan format:
          Username : {NIS atau NISN}@siswa.{domain}
          Password : eQu!6r4d3{NIS atau NISN}  (wajib ganti setelah login pertama)
        """
        domain = SchoolStudentService._get_school_domain(db, school_id)

        identifier = nis.strip() if (nis and nis.strip()) else nisn.strip()
        username = f"{identifier}@siswa.{domain}"
        default_password = f"eQu!6r4d3{identifier}"

        # Check username uniqueness
        existing = auth_repository.get_by_username(db, username)
        if existing:
            raise BusinessException(
                f"Siswa dengan NIS/NISN '{identifier}' sudah terdaftar di sekolah ini.",
                status_code=409,
            )

        account = AuthAccount(
            school_id=school_id,
            username=username,
            password_hash=hash_password(default_password),
            role=UserRole.STUDENT,
            is_active=True,
            must_change_password=True,  # Wajib ganti password setelah login pertama
            name=name,
            nis=nis,
            nisn=nisn,
            birth_date=birth_date,
            gender=gender,
            class_name=class_name,
            registered_year=registered_year,
        )
        db.add(account)
        db.flush()
        return account, default_password

    @staticmethod
    def update_student(
        db: Session,
        school_id: int,
        student_public_id: str,
        name: str | None = None,
        nisn: str | None = None,
        nis: str | None = None,
        birth_date: date | None = None,
        gender: str | None = None,
        class_name: str | None = None,
        registered_year: int | None = None,
        is_active: bool | None = None,
        update_fields: set[str] | None = None,
    ) -> AuthAccount:
        student = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(student_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
            )
            .first()
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        if update_fields is None or "name" in update_fields:
            if name is not None:
                student.name = name
        if update_fields is None or "nisn" in update_fields:
            if nisn is not None:
                student.nisn = nisn
        if update_fields is None or "nis" in update_fields:
            student.nis = nis.strip() if (nis and nis.strip()) else None
        if update_fields is None or "birth_date" in update_fields:
            student.birth_date = birth_date
        if update_fields is None or "gender" in update_fields:
            if gender is not None:
                student.gender = gender
        if update_fields is None or "class_name" in update_fields:
            student.class_name = class_name.strip() if (class_name and class_name.strip()) else None
        if update_fields is None or "registered_year" in update_fields:
            student.registered_year = registered_year
        if update_fields is None or "is_active" in update_fields:
            if is_active is not None:
                student.is_active = is_active

        db.flush()
        return student

    @staticmethod
    def delete_student(db: Session, school_id: int, student_public_id: str) -> None:
        student = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(student_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
            )
            .first()
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        db.delete(student)
        db.flush()

    @staticmethod
    def toggle_student_active(
        db: Session, school_id: int, student_public_id: str
    ) -> AuthAccount:
        student = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(student_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
            )
            .first()
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        student.is_active = not student.is_active
        db.flush()
        return student

    @staticmethod
    def reset_student_password(
        db: Session, school_id: int, student_public_id: str
    ) -> tuple[AuthAccount, str]:
        """
        Reset password siswa ke password default berdasarkan NIS/NISN.
        Identitas diambil dari bagian username sebelum '@'.
        """
        student = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(student_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
            )
            .first()
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        identifier = student.username.split("@")[0]
        new_password = f"eQu!6r4d3{identifier}"

        student.password_hash = hash_password(new_password)
        student.must_change_password = True  # Wajib ganti password setelah reset
        db.flush()
        return student, new_password
