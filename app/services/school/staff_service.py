from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.exceptions.base import BusinessException
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.security.auth_repository import auth_repository


class SchoolStaffService:

    @staticmethod
    def _get_school_domain(db: Session, school_id: int) -> str:
        """Return domain slug for the school."""
        school = db.query(School).filter(School.id == school_id).first()
        if not school or not school.domain:
            raise BusinessException("Domain sekolah belum dikonfigurasi.", status_code=400)
        return school.domain

    @staticmethod
    def list_teachers(db: Session, school_id: int) -> list[AuthAccount]:
        teachers = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
            )
            .order_by(AuthAccount.created_at.desc())
            .all()
        )

        from app.models.academic.class_entity import ClassEntity
        from app.models.academic.class_subject_teacher import ClassSubjectTeacher
        from app.models.academic.teacher_subject import TeacherSubject
        from app.models.academic.subject import Subject

        active_classes = db.query(ClassEntity).filter(
            ClassEntity.school_id == school_id,
            ClassEntity.is_active == True
        ).all()
        active_class_names = {c.name for c in active_classes}

        active_subjects = db.query(Subject).filter(
            Subject.school_id == school_id
        ).all()
        active_subject_dict = {}
        for s in active_subjects:
            active_subject_dict[s.id] = s.name
            active_subject_dict[s.name.strip().lower()] = s.name
            if s.code:
                active_subject_dict[s.code.strip().lower()] = s.name

        for t in teachers:
            # 1. Sync classes_taught
            assigned_csts = db.query(ClassSubjectTeacher).filter(
                ClassSubjectTeacher.school_id == school_id,
                ClassSubjectTeacher.teacher_id == t.id
            ).all()
            assigned_class_ids = [cst.class_id for cst in assigned_csts]
            cst_class_names = []
            if assigned_class_ids:
                cst_classes = db.query(ClassEntity).filter(
                    ClassEntity.id.in_(assigned_class_ids),
                    ClassEntity.is_active == True
                ).all()
                cst_class_names = [c.name for c in cst_classes]

            existing_taught_classes = list(t.classes_taught or [])
            valid_taught_classes = [c_name for c_name in existing_taught_classes if c_name in active_class_names]
            
            combined_class_names = list(dict.fromkeys(valid_taught_classes + cst_class_names))
            
            if t.classes_taught != combined_class_names:
                t.classes_taught = combined_class_names

            # 2. Sync subjects_taught
            assigned_ts = db.query(TeacherSubject).filter(
                TeacherSubject.school_id == school_id,
                TeacherSubject.teacher_id == t.id
            ).all()

            subject_ids_from_cst = [cst.subject_id for cst in assigned_csts if cst.subject_id]
            subject_ids_from_ts = [ts.subject_id for ts in assigned_ts if ts.subject_id]
            combined_subject_ids = list(dict.fromkeys(subject_ids_from_cst + subject_ids_from_ts))

            relational_subject_names = []
            if combined_subject_ids:
                relational_subjects = db.query(Subject).filter(
                    Subject.id.in_(combined_subject_ids),
                    Subject.school_id == school_id
                ).all()
                relational_subject_names = [s.name for s in relational_subjects]

            existing_taught_subjects = list(t.subjects_taught or [])
            valid_taught_subjects = []
            for s_str in existing_taught_subjects:
                s_key = s_str.strip().lower()
                if s_key in active_subject_dict:
                    valid_taught_subjects.append(active_subject_dict[s_key])

            combined_subject_names = list(dict.fromkeys(valid_taught_subjects + relational_subject_names))

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
        subjects_taught: list[str],
        teacher_code: str | None = None,
    ) -> tuple[AuthAccount, str]:
        """
        Buat akun guru baru dengan format:
        """
        domain = SchoolStaffService._get_school_domain(db, school_id)

        username = f"{nip}@guru.{domain}"
        default_password = f"eQu!6r4d3{nip}"

        # Check username uniqueness
        existing = auth_repository.get_by_username(db, username)
        if existing:
            raise BusinessException(
                f"NIP '{nip}' sudah terdaftar sebagai guru di sekolah ini.",
                status_code=409,
            )

        # Check / generate teacher_code
        if not teacher_code or not teacher_code.strip():
            teacher_code = f"T-{nip}"
        else:
            teacher_code = teacher_code.strip().upper()

        existing_code = db.query(AuthAccount).filter(
            AuthAccount.school_id == school_id,
            AuthAccount.teacher_code == teacher_code
        ).first()
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
            must_change_password=True,  # Wajib ganti password setelah login pertama
            name=name,
            nip=nip,
            teacher_code=teacher_code,
            gender=gender,
            registered_year=registered_year,
            classes_taught=classes_taught,
            subjects_taught=subjects_taught,
        )
        db.add(account)
        db.flush()

        # Auto-sync to teacher_subjects relational table
        if subjects_taught:
            from app.repositories.academic.subject_repository import subject_repository
            from app.repositories.academic.teacher_subject_repository import teacher_subject_repository
            all_subjects = subject_repository.list_by_school(db, school_id)
            cleaned_taught = [s.strip().lower() for s in subjects_taught]
            for subj in all_subjects:
                if subj.name.strip().lower() in cleaned_taught or subj.code.strip().lower() in cleaned_taught:
                    teacher_subject_repository.assign(db, school_id, account.id, subj.id)

        return account, default_password

    @staticmethod
    def update_teacher(
        db: Session,
        school_id: int,
        teacher_public_id: str,
        name: str | None = None,
        nip: str | None = None,
        gender: str | None = None,
        registered_year: int | None = None,
        classes_taught: list[str] | None = None,
        subjects_taught: list[str] | None = None,
        is_active: bool | None = None,
        teacher_code: str | None = None,
    ) -> AuthAccount:
        from uuid import UUID

        teacher = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(teacher_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
            )
            .first()
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        if teacher_code is not None:
            clean_code = teacher_code.strip().upper()
            if clean_code != teacher.teacher_code:
                existing_code = db.query(AuthAccount).filter(
                    AuthAccount.school_id == school_id,
                    AuthAccount.teacher_code == clean_code
                ).first()
                if existing_code:
                    raise BusinessException(
                        f"Kode Guru '{clean_code}' sudah digunakan oleh guru lain.",
                        status_code=409,
                    )
                teacher.teacher_code = clean_code

        if name is not None:
            teacher.name = name
        if nip is not None:
            domain = SchoolStaffService._get_school_domain(db, school_id)
            new_username = f"{nip}@guru.{domain}"
            if new_username != teacher.username:
                existing = auth_repository.get_by_username(db, new_username)
                if existing:
                    raise BusinessException(
                        f"NIP '{nip}' sudah terdaftar sebagai guru di sekolah ini.",
                        status_code=409,
                    )
                teacher.username = new_username
            teacher.nip = nip
        if gender is not None:
            teacher.gender = gender
        if registered_year is not None:
            teacher.registered_year = registered_year
        if classes_taught is not None:
            teacher.classes_taught = classes_taught
        if subjects_taught is not None:
            teacher.subjects_taught = subjects_taught
            # Sync to teacher_subjects relational table
            from app.repositories.academic.subject_repository import subject_repository
            from app.repositories.academic.teacher_subject_repository import teacher_subject_repository
            
            # Clear old mappings
            teacher_subject_repository.unassign_all_for_teacher(db, teacher.id)
            
            # Assign new matching ones
            all_subjects = subject_repository.list_by_school(db, school_id)
            cleaned_taught = [s.strip().lower() for s in subjects_taught]
            for subj in all_subjects:
                if subj.name.strip().lower() in cleaned_taught or subj.code.strip().lower() in cleaned_taught:
                    teacher_subject_repository.assign(db, school_id, teacher.id, subj.id)
        if is_active is not None:
            teacher.is_active = is_active

        db.flush()
        return teacher

    @staticmethod
    def toggle_teacher_active(
        db: Session, school_id: int, teacher_public_id: str
    ) -> AuthAccount:
        from uuid import UUID

        teacher = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(teacher_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
            )
            .first()
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        teacher.is_active = not teacher.is_active
        db.flush()
        return teacher

    @staticmethod
    def reset_teacher_password(
        db: Session, school_id: int, teacher_public_id: str
    ) -> tuple[AuthAccount, str]:
        """
        Reset password guru ke password default berdasarkan NIP.
        NIP diambil dari bagian username sebelum '@'.
        """
        from uuid import UUID

        teacher = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(teacher_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
            )
            .first()
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        # Extract NIP from username: {NIP}@guru.{domain}
        nip = teacher.username.split("@")[0]
        new_password = f"eQu!6r4d3{nip}"

        teacher.password_hash = hash_password(new_password)
        teacher.must_change_password = True  # Wajib ganti password setelah reset
        db.flush()
        return teacher, new_password

    @staticmethod
    def delete_teacher(db: Session, school_id: int, teacher_public_id: str) -> None:
        from uuid import UUID
        from app.models.academic.class_subject_teacher import ClassSubjectTeacher
        from app.models.teacher.question import Question
        from app.models.teacher.question_package import QuestionPackage
        from app.models.teacher.package_item import QuestionPackageItem
        from app.models.academic.exam_schedule import ExamSchedule

        teacher = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.public_id == UUID(teacher_public_id),
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
            )
            .first()
        )
        if not teacher:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        # ── Guard: cegah hapus jika ada jadwal ujian PLANNED/ACTIVE yang bergantung pada guru ini ──
        active_schedules_count = (
            db.query(ExamSchedule)
            .filter(
                ExamSchedule.school_id == school_id,
                ExamSchedule.teacher_id == teacher.id,
            )
            .count()
        )
        if active_schedules_count > 0:
            raise BusinessException(
                f"Guru ini masih terdaftar sebagai pengampu pada {active_schedules_count} jadwal ujian. "
                "Hapus atau perbarui jadwal ujian tersebut terlebih dahulu sebelum menghapus akun guru.",
                status_code=409,
            )

        # ── 1. Hapus ClassSubjectTeacher assignments milik guru ──
        db.query(ClassSubjectTeacher).filter(
            ClassSubjectTeacher.teacher_id == teacher.id
        ).delete(synchronize_session=False)

        # ── 2. Hapus QuestionPackageItems → QuestionPackages milik guru ──
        pkg_ids = [
            row[0]
            for row in db.query(QuestionPackage.id).filter(
                QuestionPackage.owner_teacher_account_id == teacher.id
            ).all()
        ]
        if pkg_ids:
            db.query(QuestionPackageItem).filter(
                QuestionPackageItem.package_id.in_(pkg_ids)
            ).delete(synchronize_session=False)
            db.query(QuestionPackage).filter(
                QuestionPackage.id.in_(pkg_ids)
            ).delete(synchronize_session=False)

        # ── 3. Hapus QuestionPackageItems yang mengacu soal guru (soal dari bank soal lain) ──
        question_ids = [
            row[0]
            for row in db.query(Question.id).filter(
                Question.owner_teacher_account_id == teacher.id
            ).all()
        ]
        if question_ids:
            db.query(QuestionPackageItem).filter(
                QuestionPackageItem.question_id.in_(question_ids)
            ).delete(synchronize_session=False)
            # ── 4. Hapus Questions milik guru ──
            db.query(Question).filter(
                Question.owner_teacher_account_id == teacher.id
            ).delete(synchronize_session=False)

        # ── 5. Hapus akun guru ──
        db.delete(teacher)
        db.flush()

