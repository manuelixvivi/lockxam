from datetime import date

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.exceptions.base import BusinessException
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.academic.academic_year_repository import academic_year_repository
from app.repositories.academic.class_repository import class_repository
from app.repositories.exam.attempt_repository import attempt_repository
from app.repositories.exam.checkin_repository import checkin_repository
from app.repositories.school.school_repository import school_repository
from app.repositories.security.auth_repository import auth_repository


class SchoolStudentService:

    @staticmethod
    def _get_school_domain(db: Session, school_id: int) -> str:
        """Return domain slug for the school via repository."""
        school = school_repository.get_by_id(db, school_id)
        if not school or not school.domain:
            raise BusinessException("Domain sekolah belum dikonfigurasi.", status_code=400)
        return school.domain

    @staticmethod
    def list_students(
        db: Session, school_id: int, limit: int | None = None, skip: int = 0
    ) -> list[AuthAccount]:
        """List student accounts for a school with optional pagination."""
        return auth_repository.list_students_by_school(db, school_id, limit=limit, skip=skip)

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

        Jika class_name diberikan:
          - Kelas wajib ada di sekolah dan tahun ajaran aktif sekolah.
          - Pembuatan akun + enrollment adalah SATU transaksi atomik.
            Jika kelas tidak ditemukan, seluruh operasi ditolak (tidak ada akun yang terbuat).
        """
        # ── 1. Resolve class BEFORE creating account (fail-fast) ─────────────────
        class_entity = None
        if class_name and class_name.strip():
            # Resolve active academic year for this school
            active_year = academic_year_repository.get_active_year(db, school_id)
            if not active_year:
                raise BusinessException(
                    "Tidak ada tahun ajaran aktif untuk sekolah ini. "
                    "Atur tahun ajaran aktif sebelum mendaftarkan siswa ke kelas.",
                    status_code=400,
                )
            class_entity = class_repository.get_by_name(
                db, school_id, active_year.id, class_name.strip()
            )
            if not class_entity:
                raise BusinessException(
                    f"Kelas '{class_name.strip()}' tidak ditemukan pada tahun ajaran aktif "
                    f"'{active_year.name}'. Pastikan nama kelas sesuai dan kelas sudah dibuat "
                    f"untuk tahun ajaran yang sedang berjalan.",
                    status_code=400,
                )

        # ── 2. Build credentials ──────────────────────────────────────────────────
        domain = SchoolStudentService._get_school_domain(db, school_id)
        identifier = nis.strip() if (nis and nis.strip()) else nisn.strip()
        username = f"{identifier}@siswa.{domain}"
        default_password = f"eQu!6r4d3{identifier}"

        # Check username uniqueness via repository
        existing = auth_repository.get_by_username(db, username)
        if existing:
            raise BusinessException(
                f"Siswa dengan NIS/NISN '{identifier}' sudah terdaftar di sekolah ini.",
                status_code=409,
            )

        # ── 3. Create AuthAccount ─────────────────────────────────────────────────
        account = AuthAccount(
            school_id=school_id,
            username=username,
            password_hash=hash_password(default_password),
            role=UserRole.STUDENT,
            is_active=True,
            must_change_password=True,
            name=name,
            nis=nis,
            nisn=nisn,
            birth_date=birth_date,
            gender=gender,
            class_name=class_name.strip() if class_name else None,
            registered_year=registered_year,
        )
        auth_repository.create(db, account)
        db.flush()  # Assign account.id without committing

        # ── 4. Create ACTIVE enrollment (atomic with account creation) ────────────
        if class_entity:
            # enroll_student_to_class also updates student.class_name to the canonical class name
            from app.services.academic.class_structure_service import ClassStructureService

            ClassStructureService.enroll_student_to_class(
                db=db,
                school_id=school_id,
                student_id=account.id,
                class_id=class_entity.id,
            )

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
        """
        Update profil siswa.

        Jika class_name berubah (ada di update_fields dan berbeda dari nilai saat ini):
          - Kelas target wajib ada di sekolah dan tahun ajaran aktif.
          - Enrollment lama menjadi TRANSFERRED.
          - Enrollment baru menjadi ACTIVE.
          - Seluruh operasi adalah atomik — jika kelas tidak valid, profil tidak berubah.

        AuthAccount.class_name adalah projection saja; sumber kebenaran enrollment ada di
        tabel student_class_enrollments yang dikelola oleh ClassStructureService.
        """
        student = auth_repository.get_by_public_id_and_school(
            db, school_id, student_public_id, role="STUDENT"
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        # ── Resolve enrollment transfer BEFORE mutating profile (fail-fast) ──────
        new_class_entity = None
        should_transfer = False
        if update_fields is None or "class_name" in update_fields:
            new_name = class_name.strip() if (class_name and class_name.strip()) else None
            current_name = student.class_name.strip() if student.class_name else None
            if new_name != current_name:
                if new_name:
                    # Must resolve against active academic year — never accept by name alone
                    active_year = academic_year_repository.get_active_year(db, school_id)
                    if not active_year:
                        raise BusinessException(
                            "Tidak ada tahun ajaran aktif untuk sekolah ini. "
                            "Tidak dapat memindahkan siswa ke kelas yang berbeda.",
                            status_code=400,
                        )
                    new_class_entity = class_repository.get_by_name(
                        db, school_id, active_year.id, new_name
                    )
                    if not new_class_entity:
                        raise BusinessException(
                            f"Kelas '{new_name}' tidak ditemukan pada tahun ajaran aktif "
                            f"'{active_year.name}'. Pastikan nama kelas sesuai dan kelas sudah "
                            f"dibuat untuk tahun ajaran yang sedang berjalan.",
                            status_code=400,
                        )
                    should_transfer = True
                else:
                    # class_name cleared — just clear the field, no enrollment mutation
                    student.class_name = None

        # ── Mutate non-enrollment profile fields ──────────────────────────────────
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
        if update_fields is None or "registered_year" in update_fields:
            student.registered_year = registered_year
        if update_fields is None or "is_active" in update_fields:
            if is_active is not None:
                student.is_active = is_active

        auth_repository.update(db, student)
        db.flush()

        # ── Perform enrollment transfer AFTER profile flush ───────────────────────
        if should_transfer and new_class_entity:
            # enroll_student_to_class marks old enrollment TRANSFERRED and creates new ACTIVE row.
            # It also sets student.class_name = new_class_entity.name (canonical sync).
            from app.services.academic.class_structure_service import ClassStructureService

            ClassStructureService.enroll_student_to_class(
                db=db,
                school_id=school_id,
                student_id=student.id,
                class_id=new_class_entity.id,
            )

        return student

    @staticmethod
    def delete_student(db: Session, school_id: int, student_public_id: str) -> None:
        """
        HISTORICAL INTEGRITY INVARIANT:
        Students with historical exam attempts or check-ins MUST NEVER BE DELETED.
        They must be deactivated instead to preserve historical exam records.
        """
        student = auth_repository.get_by_public_id_and_school(
            db, school_id, student_public_id, role="STUDENT"
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        has_attempts = attempt_repository.get_by_student(db, student.id)
        has_checkins = checkin_repository.get_by_student(db, student.id)

        if has_attempts or has_checkins:
            raise BusinessException(
                "Siswa yang memiliki riwayat ujian tidak dapat dihapus. Silakan nonaktifkan akun siswa untuk menjaga integritas data riwayat ujian.",
                status_code=409,
            )

        auth_repository.delete(db, student)
        db.flush()

    @staticmethod
    def toggle_student_active(db: Session, school_id: int, student_public_id: str) -> AuthAccount:
        """
        Deactivate or activate student account while preserving historical exam records intact.
        """
        student = auth_repository.get_by_public_id_and_school(
            db, school_id, student_public_id, role="STUDENT"
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        student.is_active = not student.is_active
        auth_repository.update(db, student)
        db.flush()
        return student

    @staticmethod
    def reset_student_password(
        db: Session, school_id: int, student_public_id: str
    ) -> tuple[AuthAccount, str]:
        """
        Reset password siswa ke password default berdasarkan NIS/NISN.
        """
        student = auth_repository.get_by_public_id_and_school(
            db, school_id, student_public_id, role="STUDENT"
        )
        if not student:
            raise BusinessException("Akun siswa tidak ditemukan.", status_code=404)

        identifier = student.username.split("@")[0]
        new_password = f"eQu!6r4d3{identifier}"

        student.password_hash = hash_password(new_password)
        student.must_change_password = True
        auth_repository.update(db, student)
        db.flush()
        return student, new_password

    @staticmethod
    def import_students_xlsx(
        db: Session,
        school_id: int,
        academic_year_id: int,
        rows: list[dict],
    ) -> tuple[bool, list[AuthAccount], list[dict]]:
        # 1. Verify academic_year_id exists and belongs to this school
        from datetime import date, datetime

        from app.repositories.academic.academic_year_repository import academic_year_repository
        from app.repositories.academic.class_repository import class_repository
        from app.services.academic.class_structure_service import ClassStructureService

        academic_year = academic_year_repository.get_by_id(db, academic_year_id)
        if not academic_year or academic_year.school_id != school_id:
            raise BusinessException(
                "Tahun ajaran tidak ditemukan atau bukan milik sekolah Anda.", status_code=400
            )

        errors = []

        # Maps to check duplicates inside the XLSX
        seen_nisn = {}  # nisn -> row index (2-indexed)
        seen_nis = {}  # nis -> row index (2-indexed)
        seen_username = {}  # username -> row index (2-indexed)

        domain = SchoolStudentService._get_school_domain(db, school_id)

        # First pass: Validate each row semantically and structurally
        validated_rows_data = []

        for index, row in enumerate(rows):
            row_num = index + 2  # Excel rows usually start at index 2 (1 is header)

            name = str(row.get("name") or "").strip()
            nisn = str(row.get("nisn") or "").strip()
            nis = str(row.get("nis") or "").strip() or None
            gender = str(row.get("gender") or "").strip().upper()
            birth_date_raw = row.get("birth_date")
            class_name = str(row.get("class_name") or "").strip() or None
            registered_year_raw = row.get("registered_year")

            # 1. Structural checks
            if not name:
                errors.append(
                    {
                        "row": row_num,
                        "field": "name",
                        "value": "",
                        "code": "NAME_REQUIRED",
                        "message": "Nama lengkap wajib diisi.",
                    }
                )

            import re

            # 2. NISN Validation
            if not nisn:
                errors.append(
                    {
                        "row": row_num,
                        "field": "nisn",
                        "value": "",
                        "code": "NISN_REQUIRED",
                        "message": "NISN wajib diisi.",
                    }
                )
            elif not re.match(r"^[0-9]{4,20}$", nisn):
                errors.append(
                    {
                        "row": row_num,
                        "field": "nisn",
                        "value": nisn,
                        "code": "INVALID_NISN",
                        "message": f"NISN '{nisn}' harus berupa angka sepanjang 4 sampai 20 karakter.",
                    }
                )
            else:
                # Deduplication check inside the Excel file
                if nisn in seen_nisn:
                    errors.append(
                        {
                            "row": row_num,
                            "field": "nisn",
                            "value": nisn,
                            "code": "DUPLICATE_NISN_IN_FILE",
                            "message": f"NISN '{nisn}' ganda di dalam file Excel (bentrok dengan baris {seen_nisn[nisn]}).",
                        }
                    )
                else:
                    seen_nisn[nisn] = row_num

                    # Check uniqueness against DB
                    existing_by_nisn = auth_repository.get_by_nisn(db, school_id, nisn)
                    if existing_by_nisn:
                        errors.append(
                            {
                                "row": row_num,
                                "field": "nisn",
                                "value": nisn,
                                "code": "DUPLICATE_NISN",
                                "message": f"NISN '{nisn}' sudah terdaftar pada siswa lain di database.",
                            }
                        )

            # 3. NIS Validation (Optional but must be numeric if present)
            if nis:
                if not re.match(r"^[0-9]{4,20}$", nis):
                    errors.append(
                        {
                            "row": row_num,
                            "field": "nis",
                            "value": nis,
                            "code": "INVALID_NIS",
                            "message": f"NIS '{nis}' harus berupa angka sepanjang 4 sampai 20 karakter jika diisi.",
                        }
                    )
                else:
                    if nis in seen_nis:
                        errors.append(
                            {
                                "row": row_num,
                                "field": "nis",
                                "value": nis,
                                "code": "DUPLICATE_NIS_IN_FILE",
                                "message": f"NIS '{nis}' ganda di dalam file Excel (bentrok dengan baris {seen_nis[nis]}).",
                            }
                        )
                    else:
                        seen_nis[nis] = row_num

                        existing_by_nis = auth_repository.get_by_nis(db, school_id, nis)
                        if existing_by_nis:
                            errors.append(
                                {
                                    "row": row_num,
                                    "field": "nis",
                                    "value": nis,
                                    "code": "DUPLICATE_NIS",
                                    "message": f"NIS '{nis}' sudah terdaftar pada siswa lain di database.",
                                }
                            )

            # 4. Username/Identifier deduplication
            if name and (nisn or nis):
                identifier = nis if nis else nisn
                if identifier:
                    username = f"{identifier}@siswa.{domain}"
                    if username in seen_username:
                        errors.append(
                            {
                                "row": row_num,
                                "field": "username",
                                "value": username,
                                "code": "DUPLICATE_USERNAME_IN_FILE",
                                "message": f"Username/Identitas '{username}' ganda di dalam file Excel.",
                            }
                        )
                    else:
                        seen_username[username] = row_num

                        existing_by_username = auth_repository.get_by_username(db, username)
                        if existing_by_username:
                            errors.append(
                                {
                                    "row": row_num,
                                    "field": "nisn" if not nis else "nis",
                                    "value": identifier,
                                    "code": "DUPLICATE_USERNAME",
                                    "message": f"Identitas '{identifier}' sudah terdaftar di sekolah ini.",
                                }
                            )

            # 5. Gender Validation
            gender_norm = None
            if not gender:
                errors.append(
                    {
                        "row": row_num,
                        "field": "gender",
                        "value": "",
                        "code": "GENDER_REQUIRED",
                        "message": "Jenis Kelamin wajib diisi (L/P).",
                    }
                )
            elif gender in ["L", "LAKI-LAKI", "LAKI", "MALE", "M"]:
                gender_norm = "L"
            elif gender in ["P", "PEREMPUAN", "FEMALE", "F"]:
                gender_norm = "P"
            else:
                errors.append(
                    {
                        "row": row_num,
                        "field": "gender",
                        "value": gender,
                        "code": "INVALID_GENDER",
                        "message": f"Jenis Kelamin '{gender}' tidak valid. Harus 'L' (Laki-laki) atau 'P' (Perempuan).",
                    }
                )

            # 6. Birth Date Parsing
            birth_date_parsed = None
            if birth_date_raw:
                if isinstance(birth_date_raw, (date, datetime)):
                    birth_date_parsed = (
                        birth_date_raw
                        if isinstance(birth_date_raw, date)
                        else birth_date_raw.date()
                    )
                else:
                    # Try to parse string
                    try:
                        # try ISO format first YYYY-MM-DD
                        birth_date_parsed = date.fromisoformat(
                            str(birth_date_raw).split("T")[0].strip()
                        )
                    except ValueError:
                        try:
                            # try DD-MM-YYYY or DD/MM/YYYY
                            s = str(birth_date_raw).strip()
                            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                                try:
                                    birth_date_parsed = datetime.strptime(s, fmt).date()
                                    break
                                except ValueError:
                                    continue
                        except ValueError:
                            pass
                    if not birth_date_parsed:
                        errors.append(
                            {
                                "row": row_num,
                                "field": "birth_date",
                                "value": str(birth_date_raw),
                                "code": "INVALID_BIRTH_DATE",
                                "message": f"Format Tanggal Lahir '{birth_date_raw}' tidak valid. Gunakan format YYYY-MM-DD.",
                            }
                        )

            # 7. Registered Year Parsing
            registered_year_parsed = None
            if registered_year_raw:
                try:
                    registered_year_parsed = int(float(registered_year_raw))
                except (ValueError, TypeError):
                    errors.append(
                        {
                            "row": row_num,
                            "field": "registered_year",
                            "value": str(registered_year_raw),
                            "code": "INVALID_REGISTERED_YEAR",
                            "message": f"Tahun Terdaftar '{registered_year_raw}' harus berupa angka tahun (contoh: 2026).",
                        }
                    )

            # 8. Class Reference Validation
            class_entity = None
            if class_name:
                class_entity = class_repository.get_by_name(
                    db, school_id, academic_year_id, class_name
                )
                if not class_entity:
                    # Check if it exists in another academic year just to be specific in error message (Required by Test 8!)
                    exists_elsewhere = class_repository.get_any_by_name_in_school(
                        db, school_id, class_name
                    )
                    if exists_elsewhere:
                        message = f"Kelas '{class_name}' ditemukan di tahun ajaran lain, tetapi belum terdaftar pada Tahun Ajaran yang dipilih."
                    else:
                        message = (
                            f"Kelas '{class_name}' tidak ditemukan pada Tahun Ajaran yang dipilih."
                        )

                    errors.append(
                        {
                            "row": row_num,
                            "field": "class_name",
                            "value": class_name,
                            "code": "CLASS_NOT_FOUND",
                            "message": message,
                        }
                    )

            validated_rows_data.append(
                {
                    "name": name,
                    "nisn": nisn,
                    "nis": nis,
                    "gender": gender_norm,
                    "birth_date": birth_date_parsed,
                    "class_name": class_name,
                    "registered_year": registered_year_parsed,
                    "class_entity": class_entity,
                }
            )

        if errors:
            return False, [], errors

        # 2. No validation errors found, proceed to persist atomically in a transaction block
        created_students = []
        try:
            savepoint = db.begin_nested()

            for data in validated_rows_data:
                nis_val = data["nis"]
                nisn_val = data["nisn"]
                identifier = nis_val.strip() if (nis_val and nis_val.strip()) else nisn_val.strip()
                username = f"{identifier}@siswa.{domain}"
                default_password = f"eQu!6r4d3{identifier}"

                account = AuthAccount(
                    school_id=school_id,
                    username=username,
                    password_hash=hash_password(default_password),
                    role=UserRole.STUDENT,
                    is_active=True,
                    must_change_password=True,
                    name=data["name"],
                    nis=nis_val,
                    nisn=nisn_val,
                    birth_date=data["birth_date"],
                    gender=data["gender"],
                    class_name=data["class_name"],
                    registered_year=data["registered_year"],
                )
                db.add(account)
                db.flush()

                # Enroll in class if provided
                if data["class_entity"]:
                    ClassStructureService.enroll_student_to_class(
                        db=db,
                        school_id=school_id,
                        student_id=account.id,
                        class_id=data["class_entity"].id,
                    )

                created_students.append(account)

            savepoint.commit()
            return True, created_students, []

        except Exception as e:
            savepoint.rollback()
            db.rollback()
            from app.logging.logger import logger

            logger.error(f"Student bulk import persistence failure: {str(e)}", exc_info=True)
            raise BusinessException(
                "Gagal melakukan penyimpanan data ke database. Terjadi kesalahan internal pada server.",
                status_code=500,
            )
