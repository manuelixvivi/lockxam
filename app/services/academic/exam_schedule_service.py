from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.enums import ExamScheduleStatus
from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.exam_schedule_package import ExamSchedulePackage
from app.repositories.academic.academic_semester_repository import (
    academic_semester_repository,
)
from app.repositories.academic.academic_year_repository import (
    academic_year_repository,
)
from app.repositories.academic.class_repository import class_repository
from app.repositories.academic.class_subject_teacher_repository import (
    class_subject_teacher_repository,
)
from app.repositories.academic.exam_schedule_package_repository import (
    exam_schedule_package_repository,
)
from app.repositories.academic.exam_schedule_repository import (
    exam_schedule_repository,
)
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.security.auth_repository import (
    auth_repository,
)
from app.utils.timezone import ensure_wib


class ExamScheduleService:
    @staticmethod
    def create_exam_schedule(
        db: Session,
        school_id: int,
        academic_year_id: int,
        academic_semester_id: int,
        class_id: int,
        subject_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime,
        duration_minutes: int,
        proctor_id: int | None = None,
        package_id: int | None = None,
        target_type: str = "ALL_CLASS",
        allowed_student_ids: list[int] | None = None,
        lock_browser: bool = True,
        eyd_language_evaluation: bool = False,
        randomize_per_type: bool = True,
    ) -> ExamSchedule:
        from datetime import timedelta

        start_time = ensure_wib(start_time)
        end_time = ensure_wib(end_time)

        if package_id:
            pkg = exam_schedule_package_repository.get_by_id(db, package_id)
            if pkg and getattr(pkg, "is_closed", False):
                raise BusinessException(
                    f"Paket jadwal ujian '{pkg.title}' telah ditutup permanen. Tidak dapat menambahkan jadwal baru.",
                    status_code=400,
                )

        title_clean = title.strip()
        if not title_clean:
            raise BusinessException("Judul jadwal ujian wajib diisi.", status_code=400)

        if duration_minutes <= 0:
            raise BusinessException("Durasi ujian harus lebih besar dari 0 menit.", status_code=400)

        min_end_time = start_time + timedelta(minutes=duration_minutes)
        if end_time < min_end_time:
            raise BusinessException(
                f"Waktu selesai ({end_time.strftime('%H:%M')}) tidak boleh kurang dari waktu mulai ({start_time.strftime('%H:%M')}) + durasi pengerjaan ({duration_minutes} menit, minimal selesai jam {min_end_time.strftime('%H:%M')}).",
                status_code=400,
            )

        # Validate overlapping schedules for the same class (excluding CANCELLED/deleted schedules)
        overlap = exam_schedule_repository.find_class_schedule_overlap(
            db, school_id, class_id, start_time, end_time
        )
        if overlap:
            raise BusinessException(
                f"Jadwal ujian bentrok dengan '{overlap.title}' di kelas yang sama ({overlap.start_time.strftime('%H:%M')} - {overlap.end_time.strftime('%H:%M')}).",
                status_code=400,
            )

        year = academic_year_repository.get_by_id(db, academic_year_id)
        if not year or year.school_id != school_id:
            raise BusinessException("Tahun ajaran tidak ditemukan.", status_code=404)

        sem = academic_semester_repository.get_by_id(db, academic_semester_id)
        if not sem or sem.academic_year_id != academic_year_id:
            raise BusinessException("Semester tidak valid untuk tahun ajaran ini.", status_code=400)

        cls = class_repository.get_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        # Invariant EXAM-SCHEDULE-001: Guru Pengampu automatically derived from ClassSubjectTeacher
        cst = class_subject_teacher_repository.get_by_class_and_subject(db, class_id, subject_id)
        if not cst:
            raise BusinessException(
                f"Belum ada guru pengampu yang di-assign untuk mata pelajaran '{subj.name}' di kelas '{cls.name}'.",
                status_code=400,
            )

        # Validate Proctor if specified
        if proctor_id is not None:
            proctor = auth_repository.get_by_id(db, proctor_id)
            if not proctor or proctor.school_id != school_id:
                raise BusinessException("Akun pengawas tidak ditemukan.", status_code=404)

        schedule = ExamSchedule(
            package_id=package_id,
            school_id=school_id,
            academic_year_id=academic_year_id,
            academic_semester_id=academic_semester_id,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=cst.teacher_id,
            proctor_id=proctor_id,
            title=title_clean,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            status=ExamScheduleStatus.DRAFT.value,
            target_type=target_type or "ALL_CLASS",
            allowed_student_ids=allowed_student_ids,
            lock_browser=lock_browser,
            eyd_language_evaluation=eyd_language_evaluation,
            randomize_per_type=randomize_per_type,
        )
        return exam_schedule_repository.create(db, schedule)

    @staticmethod
    def update_exam_schedule(
        db: Session,
        school_id: int,
        public_id: UUID,
        academic_semester_id: int | None = None,
        class_id: int | None = None,
        subject_id: int | None = None,
        title: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration_minutes: int | None = None,
        proctor_id: int | None = None,
        status: str | None = None,
        target_type: str | None = None,
        allowed_student_ids: list[int] | None = None,
        lock_browser: bool | None = None,
        eyd_language_evaluation: bool | None = None,
        randomize_per_type: bool | None = None,
    ) -> ExamSchedule:
        schedule = exam_schedule_repository.get_by_public_id(db, public_id)
        if not schedule or schedule.school_id != school_id:
            raise BusinessException("Jadwal ujian tidak ditemukan.", status_code=404)

        from app.utils.timezone import ensure_wib

        target_class_id = class_id if class_id is not None else schedule.class_id
        target_subj_id = subject_id if subject_id is not None else schedule.subject_id
        target_start = (
            ensure_wib(start_time) if start_time is not None else ensure_wib(schedule.start_time)
        )
        target_end = ensure_wib(end_time) if end_time is not None else ensure_wib(schedule.end_time)
        target_duration = (
            duration_minutes if duration_minutes is not None else schedule.duration_minutes
        )
        target_title = title.strip() if title and title.strip() else schedule.title

        if target_duration <= 0:
            raise BusinessException("Durasi ujian harus lebih besar dari 0 menit.", status_code=400)

        min_target_end = target_start + timedelta(minutes=target_duration)
        if target_end < min_target_end:
            raise BusinessException(
                f"Waktu selesai ({target_end.strftime('%H:%M')}) tidak boleh kurang dari waktu mulai ({target_start.strftime('%H:%M')}) + durasi pengerjaan ({target_duration} menit, minimal selesai jam {min_target_end.strftime('%H:%M')}).",
                status_code=400,
            )

        # Validate overlapping schedules for the same class (excluding current and CANCELLED/deleted schedules)
        overlap = exam_schedule_repository.find_class_schedule_overlap(
            db, school_id, target_class_id, target_start, target_end, exclude_id=schedule.id
        )
        if overlap:
            raise BusinessException(
                f"Jadwal ujian bentrok dengan '{overlap.title}' di kelas yang sama ({overlap.start_time.strftime('%H:%M')} - {overlap.end_time.strftime('%H:%M')}).",
                status_code=400,
            )

        if academic_semester_id is not None:
            sem = academic_semester_repository.get_by_id(db, academic_semester_id)
            if not sem or sem.academic_year_id != schedule.academic_year_id:
                raise BusinessException(
                    "Semester tidak valid untuk tahun ajaran ini.", status_code=400
                )
            schedule.academic_semester_id = academic_semester_id

        if class_id is not None or subject_id is not None:
            cst = class_subject_teacher_repository.get_by_class_and_subject(
                db, target_class_id, target_subj_id
            )
            if not cst:
                subj_obj = subject_repository.get_by_id(db, target_subj_id)
                cls_obj = class_repository.get_by_id(db, target_class_id)
                raise BusinessException(
                    f"Belum ada guru pengampu yang di-assign untuk mata pelajaran '{subj_obj.name if subj_obj else target_subj_id}' di kelas '{cls_obj.name if cls_obj else target_class_id}'.",
                    status_code=400,
                )
            schedule.teacher_id = cst.teacher_id

        schedule.class_id = target_class_id
        schedule.subject_id = target_subj_id
        schedule.title = target_title
        schedule.start_time = target_start
        schedule.end_time = target_end
        schedule.duration_minutes = target_duration
        if proctor_id is not None:
            schedule.proctor_id = proctor_id
        if status is not None:
            schedule.status = status
        if target_type is not None:
            schedule.target_type = target_type
        if allowed_student_ids is not None:
            schedule.allowed_student_ids = allowed_student_ids
        if lock_browser is not None:
            schedule.lock_browser = lock_browser
        if eyd_language_evaluation is not None:
            schedule.eyd_language_evaluation = eyd_language_evaluation
        if randomize_per_type is not None:
            schedule.randomize_per_type = randomize_per_type

        return exam_schedule_repository.update(db, schedule)

    @staticmethod
    def assign_proctor(
        db: Session, school_id: int, public_id: UUID, proctor_id: int | None
    ) -> ExamSchedule:
        schedule = exam_schedule_repository.get_by_public_id(db, public_id)
        if not schedule or schedule.school_id != school_id:
            raise BusinessException("Jadwal ujian tidak ditemukan.", status_code=404)

        if proctor_id is not None:
            proctor = auth_repository.get_by_id(db, proctor_id)
            if not proctor or proctor.school_id != school_id:
                raise BusinessException("Akun pengawas tidak ditemukan.", status_code=404)

        schedule.proctor_id = proctor_id
        return exam_schedule_repository.update(db, schedule)

    @staticmethod
    def list_schedules(
        db: Session,
        school_id: int,
        academic_year_id: int | None = None,
        academic_semester_id: int | None = None,
        class_id: int | None = None,
    ) -> list[ExamSchedule]:
        return exam_schedule_repository.list_by_school(
            db,
            school_id=school_id,
            academic_year_id=academic_year_id,
            academic_semester_id=academic_semester_id,
            class_id=class_id,
        )

    @staticmethod
    def create_schedule_package(
        db: Session, school_id: int, title: str, academic_year_id: int
    ) -> ExamSchedulePackage:
        title_clean = title.strip()
        if not title_clean:
            raise BusinessException("Judul paket jadwal ujian wajib diisi.", status_code=400)

        year = academic_year_repository.get_by_id(db, academic_year_id)
        if not year or year.school_id != school_id:
            raise BusinessException("Tahun ajaran tidak ditemukan.", status_code=404)

        package = ExamSchedulePackage(
            school_id=school_id,
            academic_year_id=academic_year_id,
            title=title_clean,
        )
        return exam_schedule_package_repository.create(db, package)

    @staticmethod
    def evaluate_auto_close_package(db: Session, package: ExamSchedulePackage) -> bool:
        """Auto-closes package if current time is >= 2 weeks (14 days) after the latest schedule's end_time."""
        if getattr(package, "is_closed", False):
            return True

        schedules = exam_schedule_repository.list_by_package(db, package.id)
        if not schedules:
            return False

        from app.utils.timezone import ensure_wib
        latest_end_time = max(ensure_wib(s.end_time) for s in schedules)
        now = datetime.now(timezone.utc)

        # Auto close 2 weeks (14 days) after the last schedule's end_time
        if now >= latest_end_time + timedelta(days=14):
            if hasattr(package, "is_closed"):
                package.is_closed = True
            for sch in schedules:
                if sch.status != "CANCELLED":
                    sch.status = "COMPLETED"
            db.commit()
            return True

        return False

    @staticmethod
    def get_schedule_package(db: Session, school_id: int, public_id: UUID) -> ExamSchedulePackage:
        package = exam_schedule_package_repository.get_by_public_id(db, public_id)
        if not package or package.school_id != school_id:
            raise BusinessException("Paket jadwal ujian tidak ditemukan.", status_code=404)
        ExamScheduleService.evaluate_auto_close_package(db, package)
        return package

    @staticmethod
    def list_schedule_packages(
        db: Session, school_id: int, academic_year_id: int | None = None
    ) -> list[ExamSchedulePackage]:
        packages = exam_schedule_package_repository.list_by_school(db, school_id, academic_year_id)
        for p in packages:
            ExamScheduleService.evaluate_auto_close_package(db, p)
        return packages

    @staticmethod
    def delete_exam_schedule(db: Session, school_id: int, public_id: UUID) -> None:
        schedule = exam_schedule_repository.get_by_public_id(db, public_id)
        if not schedule or schedule.school_id != school_id:
            raise BusinessException("Jadwal ujian tidak ditemukan.", status_code=404)

        from app.repositories.exam.exam_session_repository import exam_session_repository
        from app.repositories.exam.attempt_repository import attempt_repository
        from app.repositories.exam.checkin_repository import checkin_repository
        from app.repositories.academic.exam_snapshot_repository import exam_snapshot_repository

        sessions = exam_session_repository.list_by_schedule_id(db, schedule.id)
        session_ids = [s.id for s in sessions]
        has_attempts = attempt_repository.get_by_session_id(db, session_ids[0]) if session_ids else []
        has_checkins = checkin_repository.get_by_schedule(db, schedule.id)

        # Academic Trace Integrity: If sessions, attempts, or check-ins exist, NEVER hard delete! Soft cancel to preserve student history!
        if sessions or has_attempts or has_checkins:
            schedule.status = "CANCELLED"
            schedule.package_id = None
            db.flush()
            return

        try:
            exam_snapshot_repository.delete_by_schedule(db, schedule.id)
            exam_schedule_repository.delete(db, schedule)
            db.flush()
        except Exception:
            schedule.status = "CANCELLED"
            schedule.package_id = None
            db.flush()

    @staticmethod
    def delete_schedule_package(db: Session, school_id: int, public_id: UUID) -> None:
        package = exam_schedule_package_repository.get_by_public_id(db, public_id)
        if not package or package.school_id != school_id:
            raise BusinessException("Paket jadwal ujian tidak ditemukan.", status_code=404)

        from app.repositories.exam.exam_session_repository import exam_session_repository
        from app.repositories.exam.snapshot_repository import snapshot_repository
        from app.repositories.academic.exam_snapshot_repository import exam_snapshot_repository

        # 1. Unlink or delete child schedules
        schedules = exam_schedule_repository.list_by_package(db, package.id)
        for sch in schedules:
            sch.package_id = None
            sessions = exam_session_repository.list_by_schedule_id(db, sch.id)
            has_historical = any(sess.status in ["ACTIVE", "COMPLETED"] for sess in sessions)

            if has_historical:
                sch.status = "CANCELLED"
            else:
                exam_snapshot_repository.delete_by_schedule(db, sch.id)
                for sess in sessions:
                    snapshot_repository.delete_by_session(db, sess.id)
                    try:
                        exam_session_repository.delete(db, sess)
                    except Exception:
                        pass
                try:
                    exam_schedule_repository.delete(db, sch)
                except Exception:
                    sch.status = "CANCELLED"
                    sch.package_id = None

        db.flush()
        # 2. Hard delete the package row
        exam_schedule_package_repository.delete(db, package)

    @staticmethod
    def import_schedules_xlsx(
        db: Session, school_id: int, package_id: int, rows: list[dict]
    ) -> list[ExamSchedule]:
        package = exam_schedule_package_repository.get_by_id(db, package_id)
        if not package or package.school_id != school_id:
            raise BusinessException("Paket jadwal ujian tidak ditemukan.", status_code=404)

        if getattr(package, "is_closed", False):
            raise BusinessException(
                f"Paket jadwal ujian '{package.title}' telah ditutup permanen. Tidak dapat mengimpor jadwal ke dalamnya.",
                status_code=400,
            )

        # Get active or first semester for the year
        semesters = academic_semester_repository.get_semesters_by_year(db, package.academic_year_id)
        active_semester = next((s for s in semesters if s.status == "ACTIVE"), None)
        if not active_semester:
            if semesters:
                active_semester = semesters[0]
            else:
                raise BusinessException(
                    "Tidak ada semester yang terdaftar untuk tahun ajaran paket jadwal ini.",
                    status_code=400,
                )

        from app.repositories.academic.class_repository import class_repository
        from app.repositories.academic.class_subject_teacher_repository import (
            class_subject_teacher_repository,
        )
        from app.repositories.academic.subject_repository import subject_repository

        created_schedules = []
        batch_class_schedules = {}

        for index, row in enumerate(rows):
            # Parse row data
            raw_class = str(row.get("Kelas") or "").strip()
            raw_mapel = str(row.get("Mata Pelajaran") or row.get("Mapel") or "").strip()
            raw_date = str(row.get("Tanggal Ujian") or row.get("Tanggal") or "").strip()
            raw_start = str(row.get("Jam Mulai") or "").strip()
            raw_end = str(row.get("Jam Selesai") or "").strip()
            raw_proctor_code = str(row.get("Kode Pengawas") or "").strip()

            row_num = index + 1
            if not raw_class:
                raise BusinessException(
                    f"Baris #{row_num}: Kolom 'Kelas' wajib diisi.", status_code=400
                )
            if not raw_mapel:
                raise BusinessException(
                    f"Baris #{row_num}: Kolom 'Mata Pelajaran' wajib diisi.", status_code=400
                )
            if not raw_date:
                raise BusinessException(
                    f"Baris #{row_num}: Kolom 'Tanggal Ujian' wajib diisi.", status_code=400
                )
            if not raw_start or not raw_end:
                raise BusinessException(
                    f"Baris #{row_num}: Kolom 'Jam Mulai' dan 'Jam Selesai' wajib diisi.",
                    status_code=400,
                )

            # 1. Resolve Class via repository
            cls = class_repository.get_by_name(db, school_id, package.academic_year_id, raw_class)
            if not cls:
                raise BusinessException(
                    f"Baris #{row_num}: Rombel Kelas '{raw_class}' tidak ditemukan pada tahun ajaran paket ini.",
                    status_code=400,
                )

            # 2. Resolve Subject (by code or name) via repository
            subj = subject_repository.get_by_code_or_name(db, school_id, raw_mapel)
            if not subj:
                raise BusinessException(
                    f"Baris #{row_num}: Mata Pelajaran '{raw_mapel}' tidak ditemukan di Master Data.",
                    status_code=400,
                )

            # 3. Resolve ClassSubjectTeacher (Guru Pengampu) - Invariant EXAM-SCHEDULE-001
            cst = class_subject_teacher_repository.get_by_class_and_subject(db, cls.id, subj.id)
            if not cst:
                raise BusinessException(
                    f"Baris #{row_num}: Belum ada guru pengampu yang di-assign untuk mapel '{subj.name}' di kelas '{cls.name}'.",
                    status_code=400,
                )

            # 4. Resolve Proctor by teacher_code via repository
            proctor_id = None
            if raw_proctor_code:
                proctor = auth_repository.get_teacher_by_code(db, school_id, raw_proctor_code)
                if not proctor:
                    raise BusinessException(
                        f"Baris #{row_num}: Guru Pengawas dengan Kode Guru '{raw_proctor_code}' tidak ditemukan.",
                        status_code=400,
                    )
                proctor_id = proctor.id

            # 5. Parse Times
            try:
                # Combine Date and Start/End times
                start_dt_str = f"{raw_date} {raw_start}"
                end_dt_str = f"{raw_date} {raw_end}"

                fmt_start = (
                    "%Y-%m-%d %H:%M:%S" if len(raw_start.split(":")) == 3 else "%Y-%m-%d %H:%M"
                )
                fmt_end = "%Y-%m-%d %H:%M:%S" if len(raw_end.split(":")) == 3 else "%Y-%m-%d %H:%M"

                start_time = datetime.strptime(start_dt_str, fmt_start).replace(tzinfo=timezone.utc)
                end_time = datetime.strptime(end_dt_str, fmt_end).replace(tzinfo=timezone.utc)
            except Exception:
                raise BusinessException(
                    f"Baris #{row_num}: Format Tanggal Ujian (YYYY-MM-DD) atau Jam (HH:MM) tidak valid.",
                    status_code=400,
                )

            if end_time <= start_time:
                raise BusinessException(
                    f"Baris #{row_num}: Waktu selesai ({raw_end}) harus lebih besar dari waktu mulai ({raw_start}).",
                    status_code=400,
                )

            duration_minutes = int((end_time - start_time).total_seconds() / 60)

            # Validate overlapping schedules for the same class in DB via repository
            overlap = exam_schedule_repository.find_class_schedule_overlap(db, school_id, cls.id, start_time, end_time)
            if overlap:
                raise BusinessException(
                    f"Baris #{row_num}: Kelas '{cls.name}' sudah memiliki jadwal ujian lain pada waktu tersebut di database: '{overlap.title}' ({overlap.start_time.strftime('%Y-%m-%d %H:%M')} - {overlap.end_time.strftime('%Y-%m-%d %H:%M')}).",
                    status_code=400,
                )

            # Check for overlapping schedules within the current import batch
            if cls.id not in batch_class_schedules:
                batch_class_schedules[cls.id] = []

            for b_start, b_end, b_row in batch_class_schedules[cls.id]:
                if start_time < b_end and end_time > b_start:
                    raise BusinessException(
                        f"Baris #{row_num}: Bentrok waktu ujian kelas '{cls.name}' dengan data di baris #{b_row} ({b_start.strftime('%H:%M')} - {b_end.strftime('%H:%M')}).",
                        status_code=400,
                    )

            batch_class_schedules[cls.id].append((start_time, end_time, row_num))

            # 6. Create ExamSchedule
            title = f"Ujian {subj.name} - {cls.name}"
            schedule = ExamSchedule(
                package_id=package.id,
                school_id=school_id,
                academic_year_id=package.academic_year_id,
                academic_semester_id=active_semester.id,
                class_id=cls.id,
                subject_id=subj.id,
                teacher_id=cst.teacher_id,
                proctor_id=proctor_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                status=ExamScheduleStatus.DRAFT.value,
            )
            db.add(schedule)
            created_schedules.append(schedule)

        db.flush()
        return created_schedules
