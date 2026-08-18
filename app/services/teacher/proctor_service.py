from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.exceptions import BusinessException
from app.models.teacher.bau_attendance import BAUAttendance
from app.models.teacher.bau_document import BAUDocument
from app.models.teacher.enums import AttendanceStatus, BAUStatus, ProctorEventType
from app.models.teacher.proctor_event import ProctorAuditEvent
from app.repositories.teacher.bau_repository import bau_repository
from app.repositories.teacher.proctor_event_repository import proctor_event_repository


class ProctorService:

    @staticmethod
    def log_proctor_event(
        db: Session,
        proctor_assignment_id: int,
        student_id: int,
        event_type: ProctorEventType,
        reason: str,
        proctor_id: int,
        action_taken: str,
    ) -> ProctorAuditEvent:
        try:
            event = ProctorAuditEvent(
                proctor_assignment_id=proctor_assignment_id,
                student_id=student_id,
                event_type=event_type,
                reason=reason,
                proctor_id=proctor_id,
                action_taken=action_taken,
                timestamp=datetime.now(timezone.utc),
            )
            proctor_event_repository.create(db, event)
            db.commit()
            return event
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def auto_mark_student_present(db: Session, proctor_assignment_id: int, student_id: int):
        try:
            doc = bau_repository.get_by_assignment(db, proctor_assignment_id)
            if not doc:
                doc = BAUDocument(
                    proctor_assignment_id=proctor_assignment_id,
                    status=BAUStatus.DRAFT,
                )
                bau_repository.create(db, doc)
                db.flush()

            attendance = None
            for att in doc.attendances:
                if att.student_id == student_id:
                    attendance = att
                    break

            if attendance:
                attendance.attendance_status = AttendanceStatus.HADIR
            else:
                attendance = BAUAttendance(
                    bau_document_id=doc.id,
                    student_id=student_id,
                    attendance_status=AttendanceStatus.HADIR,
                )
                db.add(attendance)
            db.commit()
        except Exception:
            db.rollback()

    @staticmethod
    def get_or_create_bau(db: Session, proctor_assignment_id: int) -> BAUDocument:
        try:
            from datetime import timedelta
            from app.models.academic.exam_schedule import ExamSchedule
            from app.models.exam.exam_session import ExamSession
            from app.models.exam.exam_attempt import ExamAttempt
            from app.models.academic.student_class_enrollment import StudentClassEnrollment
            from app.utils.timezone import ensure_wib

            doc = bau_repository.get_by_assignment(db, proctor_assignment_id)
            if not doc:
                doc = BAUDocument(
                    proctor_assignment_id=proctor_assignment_id,
                    status=BAUStatus.DRAFT,
                )
                bau_repository.create(db, doc)
                db.flush()

            schedule = db.query(ExamSchedule).filter(ExamSchedule.id == proctor_assignment_id).first()

            # Rule: 24-Hour Auto-Submit after exam end_time if still DRAFT
            if schedule and doc.status == BAUStatus.DRAFT:
                now_wib = ensure_wib(datetime.now(timezone.utc))
                end_wib = ensure_wib(schedule.end_time)
                if now_wib >= end_wib + timedelta(hours=24):
                    doc.status = BAUStatus.SUBMITTED
                    doc.submitted_at = now_wib
                    if not doc.proctor_notes:
                        doc.proctor_notes = "BAP Terkirim Otomatis oleh Sistem (Batas Waktu 24 Jam Pasca Ujian Selesai)."

            # Sync default attendance for class students
            if schedule:
                session = db.query(ExamSession).filter(ExamSession.schedule_id == schedule.id).first()
                attempt_student_ids = set()
                if session:
                    attempts = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id == session.id).all()
                    attempt_student_ids = {a.student_id for a in attempts}

                enrollments = db.query(StudentClassEnrollment).filter(
                    StudentClassEnrollment.class_id == schedule.class_id,
                    StudentClassEnrollment.status == "ACTIVE"
                ).all()

                existing_atts = {att.student_id: att for att in doc.attendances}
                for en in enrollments:
                    sid = en.student_id
                    if sid not in existing_atts:
                        # Default is ALPA unless student started attempt
                        st = AttendanceStatus.HADIR if sid in attempt_student_ids else AttendanceStatus.ALPA
                        new_att = BAUAttendance(
                            bau_document_id=doc.id,
                            student_id=sid,
                            attendance_status=st,
                        )
                        db.add(new_att)
                    elif sid in attempt_student_ids and existing_atts[sid].attendance_status == AttendanceStatus.ALPA:
                        existing_atts[sid].attendance_status = AttendanceStatus.HADIR

            db.commit()
            return doc
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def update_attendance(
        db: Session,
        bau_document_id: int,
        student_id: int,
        status: AttendanceStatus,
        reason: str | None = None,
    ) -> BAUAttendance:
        try:
            doc = bau_repository.get_by_id(db, bau_document_id)
            if not doc:
                raise BusinessException("Berita Acara tidak ditemukan.", status_code=404)

            # BAU/BAP is editable during DRAFT or within 24 hours after SUBMITTED
            if doc.status == BAUStatus.SUBMITTED:
                now_utc = datetime.now(timezone.utc)
                submitted_time = doc.submitted_at or doc.updated_at or doc.created_at
                if (now_utc - submitted_time).total_seconds() > 24 * 3600:
                    raise BusinessException(
                        "Berita Acara telah dikunci permanen. Batas waktu edit 24 jam telah lewat.",
                        status_code=400,
                    )

            # Check if attendance already exists
            attendance = None
            for att in doc.attendances:
                if att.student_id == student_id:
                    attendance = att
                    break

            if attendance:
                attendance.attendance_status = status
                attendance.reason = reason
            else:
                attendance = BAUAttendance(
                    bau_document_id=bau_document_id,
                    student_id=student_id,
                    attendance_status=status,
                    reason=reason,
                )
                db.add(attendance)

            db.commit()
            return attendance
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def submit_bau(
        db: Session, bau_document_id: int, proctor_notes: str | None = None
    ) -> BAUDocument:
        try:
            doc = bau_repository.get_by_id(db, bau_document_id)
            if not doc:
                raise BusinessException("Berita Acara tidak ditemukan.", status_code=404)

            now_utc = datetime.now(timezone.utc)
            if doc.status == BAUStatus.SUBMITTED:
                submitted_time = doc.submitted_at or doc.updated_at or doc.created_at
                if (now_utc - submitted_time).total_seconds() > 24 * 3600:
                    raise BusinessException("Berita Acara telah dikunci secara permanen.", status_code=400)

            doc.status = BAUStatus.SUBMITTED
            doc.proctor_notes = proctor_notes
            doc.submitted_at = now_utc
            db.commit()
            return doc
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def request_correction(db: Session, bau_document_id: int) -> BAUDocument:
        try:
            doc = bau_repository.get_by_id(db, bau_document_id)
            if not doc:
                raise BusinessException("Berita Acara tidak ditemukan.", status_code=404)

            if doc.status != BAUStatus.SUBMITTED:
                raise BusinessException(
                    "Hanya Berita Acara berstatus SUBMITTED yang dapat diajukan koreksi.",
                    status_code=400,
                )

            doc.status = BAUStatus.CORRECTION_REQUESTED
            db.commit()
            return doc
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def resolve_correction(db: Session, bau_document_id: int, approve: bool) -> BAUDocument:
        try:
            doc = bau_repository.get_by_id(db, bau_document_id)
            if not doc:
                raise BusinessException("Berita Acara tidak ditemukan.", status_code=404)

            if doc.status != BAUStatus.CORRECTION_REQUESTED:
                raise BusinessException(
                    "Berita Acara tidak memiliki pengajuan koreksi aktif.", status_code=400
                )

            # Jika disetujui (approve=True) status kembali ke DRAFT agar bisa diedit pengawas
            # Jika ditolak (approve=False) status dikembalikan ke SUBMITTED (terkunci)
            if approve:
                doc.status = BAUStatus.DRAFT
            else:
                doc.status = BAUStatus.SUBMITTED

            db.commit()
            return doc
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def dispatch_internal_proctor_command(
        db: Session,
        endpoint: str,
        proctor_id: int,
        attempt_id: int,
        proctor_assignment_id: int,
        exam_session_id: int,
        reason: str = "",
    ) -> dict:
        """EXAM-FIX-12: Teacher Domain memverifikasi otorisasi pengawas sebelum mengirim internal command."""
        # 1. Validasi Identitas & Peran Guru Pengawas
        from app.models.security.auth_account import AuthAccount

        teacher = (
            db.query(AuthAccount)
            .filter(AuthAccount.id == proctor_id, AuthAccount.role == "TEACHER")
            .first()
        )
        if not teacher:
            raise BusinessException("Akses ditolak: Pengawas tidak terdaftar.", status_code=403)

        # 2. Validasi Hubungan Kepengawasan Sesi (Mock/Placeholder Check karena tabel penjadwalan belum dimodelkan)
        if proctor_assignment_id <= 0 or exam_session_id <= 0:
            raise BusinessException(
                "Akses ditolak: Penugasan pengawas tidak valid.", status_code=403
            )

        # 3. Direct Execution via ExamService (avoiding HTTP loopback connection failures in Serverless)
        from app.schemas.exam.exam import ProctorCommandRequest
        from app.services.exam.exam_service import ExamService

        cmd_payload = ProctorCommandRequest(
            attempt_id=attempt_id,
            proctor_assignment_id=proctor_assignment_id,
            actor_teacher_id=proctor_id,
            exam_session_id=exam_session_id,
            reason=reason or "Executed by proctor",
        )

        if endpoint in ["lock-student", "lock"]:
            ExamService.proctor_lock_attempt(db=db, payload=cmd_payload)
        elif endpoint in ["unlock-student", "unlock"]:
            ExamService.proctor_unlock_attempt(db=db, attempt_id=attempt_id, exam_session_id=exam_session_id)
        elif endpoint == "device-reset":
            ExamService.proctor_reset_device(db=db, payload=cmd_payload)
        else:
            raise BusinessException(f"Perintah pengawas '{endpoint}' tidak dikenal.", status_code=400)

        return {
            "status": "SUCCESS",
            "message": f"Perintah {endpoint} berhasil dieksekusi untuk siswa.",
        }
