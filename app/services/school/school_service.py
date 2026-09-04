import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security.password import hash_password
from app.exceptions.base import BusinessException
from app.models.school.school import School
from app.models.school.school_setting import SchoolSetting
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.license.school_license_repository import school_license_repository
from app.repositories.master.license_type_repository import license_type_repository
from app.repositories.master.school_level_repository import school_level_repository
from app.repositories.school.school_repository import school_repository
from app.repositories.school.school_setting_repository import school_setting_repository
from app.repositories.security.auth_repository import auth_repository
from app.schemas.school.school import SchoolCreateRequest, SchoolUpdateRequest


class SchoolService:

    @staticmethod
    def create_school(db: Session, data: SchoolCreateRequest) -> School:
        # BR-SCH-004: Validate NPSN uniqueness
        existing_school = school_repository.get_by_npsn(db, data.npsn)
        if existing_school:
            raise BusinessException(f"School with NPSN {data.npsn} already exists", status_code=400)

        # Validate domain uniqueness
        existing_domain = school_repository.get_by_domain(db, data.domain)
        if existing_domain:
            raise BusinessException(
                f"Domain '{data.domain}' sudah digunakan sekolah lain.", status_code=409
            )

        # BR-SCH-005: Validate school level exists
        level = school_level_repository.get_by_id(db, data.school_level_id)
        if not level:
            raise BusinessException(
                f"School level with ID {data.school_level_id} not found",
                status_code=400,
            )

        # Auto-generate school code from NPSN
        school_code = f"SCH_{uuid.uuid4().hex[:8].upper()}"

        # 1. Create School
        school = School(
            public_id=uuid.uuid4(),
            npsn=data.npsn,
            code=school_code,
            name=data.name,
            domain=data.domain,
            school_level_id=data.school_level_id,
            address=data.address,
            phone=data.phone,
            email=data.email,
            website=data.website,
            logo_url=data.logo_url,
            is_active=False,  # BR-SCH-002: Status School PENDING_ACTIVATION
            status="PENDING_ACTIVATION",
        )
        school_repository.create(db, school)
        db.flush()  # Retrieve school.id

        # BR-SCH-006: Create default School Settings
        setting = SchoolSetting(school_id=school.id, timezone="Asia/Jakarta", language="id-ID")
        school_setting_repository.create(db, setting)

        # BR-SCH-002: Create Default Admin Account with domain-based username
        admin_username = f"admin@admin.{data.domain}"
        admin_password = f"eQu!6r4de@{school_code}"
        admin_hashed_pw = hash_password(admin_password)

        admin_acc = AuthAccount(
            school_id=school.id,
            username=admin_username,
            password_hash=admin_hashed_pw,
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=True,
        )
        auth_repository.create(db, admin_acc)
        db.flush()

        # Auto-apply initial subscription preset
        from app.services.license.license_service import LicenseService

        lic_type = license_type_repository.get_by_code(db, data.initial_subscription_preset)
        if not lic_type:
            raise BusinessException(
                f"Preset subscription '{data.initial_subscription_preset}' tidak valid.",
                status_code=400,
            )

        # Get superadmin to be the key generator
        superadmin = auth_repository.get_superadmin(db)
        superadmin_id = superadmin.id if superadmin else admin_acc.id

        # Generate the activation key
        key_record, raw_key = LicenseService.generate_activation_key(
            db=db,
            license_type_id=lic_type.id,
            school_id=school.id,
            generated_by_id=superadmin_id,
            validity_days=lic_type.duration_days,
        )

        # Activate the license immediately
        LicenseService.activate_license(
            db=db,
            plain_key=raw_key,
            school_id=school.id,
            used_by_id=admin_acc.id,
        )

        # Make the school active immediately
        school.is_active = True

        db.commit()
        db.refresh(school)
        school.admin_username = admin_username  # type: ignore[attr-defined]
        school.subscription_status = "ACTIVE"  # type: ignore[attr-defined]
        school.subscription_end_date = None  # type: ignore[attr-defined]
        school.registered_students_count = 0  # type: ignore[attr-defined]
        school.temporary_password = admin_password  # type: ignore[attr-defined]
        return school

    @staticmethod
    def _enrich_admin_username(db: Session, school: School) -> School:
        admin_acc = auth_repository.get_school_admin(db, school.id)
        if admin_acc:
            school.admin_username = admin_acc.username  # type: ignore[attr-defined]
        else:
            school.admin_username = None  # type: ignore[attr-defined]

        # Enrich subscription status & expiration date
        latest_license = school_license_repository.get_latest_license(db, school.id)
        if latest_license:
            school.subscription_status = latest_license.status  # type: ignore[attr-defined]
            school.subscription_end_date = latest_license.end_date  # type: ignore[attr-defined]
        else:
            school.subscription_status = "NO_LICENSE"  # type: ignore[attr-defined]
            school.subscription_end_date = None  # type: ignore[attr-defined]

        # Enrich total registered students count
        total_students = auth_repository.count_students_by_school(db, school.id)
        school.registered_students_count = total_students  # type: ignore[attr-defined]

        return school

    @staticmethod
    def toggle_school_subscription(db: Session, public_id: uuid.UUID) -> tuple[School, str]:
        school = SchoolService.get_school_by_public_id(db, public_id)
        latest_license = school_license_repository.get_latest_license(db, school.id)
        if not latest_license:
            raise BusinessException(
                "Sekolah ini belum memiliki lisensi. Terbitkan Activation Key terlebih dahulu.",
                status_code=400,
            )

        new_status = "SUSPENDED" if latest_license.status == "ACTIVE" else "ACTIVE"
        latest_license.status = new_status
        school.status = new_status
        school_repository.update(db, school)
        db.commit()
        db.refresh(latest_license)
        return SchoolService._enrich_admin_username(db, school), new_status

    @staticmethod
    def get_school_by_public_id(db: Session, public_id: uuid.UUID) -> School:
        school = school_repository.get_by_public_id(db, public_id)
        if not school:
            raise BusinessException("School not found", status_code=404)
        return SchoolService._enrich_admin_username(db, school)

    @staticmethod
    def get_school_by_id_or_public_id(db: Session, identifier: str | int | uuid.UUID) -> School:
        school = None
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            school = school_repository.get_by_id(db, int(identifier))
        else:
            try:
                u = uuid.UUID(str(identifier))
                school = school_repository.get_by_public_id(db, u)
            except (ValueError, AttributeError):
                pass
        if not school:
            raise BusinessException("School not found", status_code=404)
        return SchoolService._enrich_admin_username(db, school)

    @staticmethod
    def _bulk_enrich_schools(db: Session, schools: list[School]) -> list[School]:
        if not schools:
            return []
        school_ids = [s.id for s in schools]

        # 1. Bulk query admins
        admins = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.school_id.in_(school_ids),
                AuthAccount.role == UserRole.ADMIN,
                AuthAccount.is_active == True,
            )
            .all()
        )
        admin_map = {a.school_id: a.username for a in admins}

        # 2. Bulk query latest licenses (using max ID subquery per school)
        from sqlalchemy import func

        from app.models.license.school_license import SchoolLicense

        latest_lic_subq = (
            db.query(
                SchoolLicense.school_id,
                func.max(SchoolLicense.id).label("max_id"),
            )
            .filter(SchoolLicense.school_id.in_(school_ids))
            .group_by(SchoolLicense.school_id)
            .subquery()
        )

        licenses = (
            db.query(SchoolLicense)
            .join(latest_lic_subq, SchoolLicense.id == latest_lic_subq.c.max_id)
            .all()
        )
        license_map = {lic.school_id: lic for lic in licenses}

        # 3. Bulk query registered students count via GROUP BY
        from sqlalchemy import func

        student_counts = (
            db.query(AuthAccount.school_id, func.count(AuthAccount.id))
            .filter(
                AuthAccount.school_id.in_(school_ids),
                AuthAccount.role == UserRole.STUDENT,
                AuthAccount.is_active == True,
            )
            .group_by(AuthAccount.school_id)
            .all()
        )
        student_count_map = {sc[0]: sc[1] for sc in student_counts}

        # 4. Attach attributes to school objects in memory
        for s in schools:
            s.admin_username = admin_map.get(s.id, "-")  # type: ignore[attr-defined]
            lic = license_map.get(s.id)
            if lic:
                s.subscription_status = lic.status  # type: ignore[attr-defined]
                s.subscription_end_date = lic.end_date  # type: ignore[attr-defined]
            else:
                s.subscription_status = "NO_LICENSE"  # type: ignore[attr-defined]
                s.subscription_end_date = None  # type: ignore[attr-defined]
            s.registered_students_count = student_count_map.get(s.id, 0)  # type: ignore[attr-defined]

        return schools

    @staticmethod
    def get_all_schools(db: Session) -> list[School]:
        schools = school_repository.get_all_active(db)
        return SchoolService._bulk_enrich_schools(db, schools)

    @staticmethod
    def list_schools_paginated(
        db: Session,
        limit: int = 20,
        skip: int = 0,
        search: str | None = None,
    ) -> tuple[list[School], int]:
        schools, total = school_repository.list_paginated(db, limit=limit, skip=skip, search=search)
        return SchoolService._bulk_enrich_schools(db, schools), total

    @staticmethod
    def get_superadmin_dashboard_summary(db: Session) -> dict:
        from sqlalchemy import func, select

        from app.models.license.renewal_request import RenewalRequest
        from app.models.license.school_license import SchoolLicense

        # Execute all 4 aggregate counts in a single database round-trip
        stats_query = select(
            select(func.count(School.id))
            .where(School.deleted_at.is_(None))
            .scalar_subquery()
            .label("total_schools"),
            select(func.count(School.id))
            .where(School.deleted_at.is_(None), School.is_active.is_(True))
            .scalar_subquery()
            .label("active_schools"),
            select(func.count(RenewalRequest.id))
            .where(RenewalRequest.status.in_(["PENDING", "REQUESTED"]))
            .scalar_subquery()
            .label("pending_renewals"),
            select(func.count(SchoolLicense.id)).scalar_subquery().label("total_licenses"),
        )
        stats_row = db.execute(stats_query).one()
        total_schools = stats_row[0] or 0
        active_schools = stats_row[1] or 0
        pending_renewals = stats_row[2] or 0
        total_licenses = stats_row[3] or 0

        recent_schools = list(
            db.scalars(
                select(School)
                .where(School.deleted_at.is_(None))
                .order_by(School.created_at.desc())
                .limit(5)
            ).all()
        )

        return {
            "total_schools": total_schools,
            "active_schools": active_schools,
            "pending_renewals": pending_renewals,
            "total_licenses": total_licenses,
            "recent_schools": recent_schools,
        }

    @staticmethod
    def reset_school_admin_password(
        db: Session, public_id: uuid.UUID, new_password: str | None = None
    ) -> tuple[str, str]:
        school = SchoolService.get_school_by_public_id(db, public_id)
        admin_acc = auth_repository.get_school_admin(db, school.id)

        if not admin_acc:
            raise BusinessException(
                "Akun Admin Sekolah tidak ditemukan untuk sekolah ini.", status_code=404
            )

        if not new_password:
            new_password = f"eQu!6r4de@{school.code}"

        from app.core.security.password import validate_password_strength

        validate_password_strength(new_password)
        admin_acc.password_hash = hash_password(new_password)
        admin_acc.must_change_password = True
        db.commit()

        return admin_acc.username, new_password

    @staticmethod
    def update_school(db: Session, public_id: uuid.UUID, data: SchoolUpdateRequest) -> School:
        school = SchoolService.get_school_by_public_id(db, public_id)

        if data.npsn is not None and data.npsn.strip() != school.npsn:
            existing = school_repository.get_by_npsn(db, data.npsn.strip())
            if existing and existing.id != school.id:
                raise BusinessException(
                    f"School with NPSN {data.npsn} already exists", status_code=400
                )
            school.npsn = data.npsn.strip()

        if data.code is not None and data.code.strip() != school.code:
            existing = school_repository.get_by_code(db, data.code.strip())
            if existing and existing.id != school.id:
                raise BusinessException(
                    f"School with code '{data.code}' already exists", status_code=400
                )
            school.code = data.code.strip()

        if data.school_level_id is not None:
            level = school_level_repository.get_by_id(db, data.school_level_id)
            if not level:
                raise BusinessException(
                    f"School level with ID {data.school_level_id} not found",
                    status_code=400,
                )
            school.school_level_id = data.school_level_id

        if data.domain is not None and data.domain.strip() != (school.domain or ""):
            existing = school_repository.get_by_domain(db, data.domain.strip())
            if existing and existing.id != school.id:
                raise BusinessException(
                    f"Domain '{data.domain}' sudah digunakan sekolah lain.", status_code=409
                )
            school.domain = data.domain.strip()

        if data.name is not None:
            school.name = data.name
        if data.address is not None:
            school.address = data.address
        if data.phone is not None:
            school.phone = data.phone
        if data.email is not None:
            school.email = data.email
        if data.website is not None:
            school.website = data.website
        if data.logo_url is not None:
            school.logo_url = data.logo_url
        if data.is_active is not None:
            school.is_active = data.is_active

        school_repository.update(db, school)
        db.commit()
        db.refresh(school)
        return SchoolService._enrich_admin_username(db, school)

    @staticmethod
    def get_dashboard_summary(db: Session, identifier: str) -> dict:
        school = SchoolService.get_school_by_id_or_public_id(db, identifier)
        from sqlalchemy import func

        from app.models.academic.academic_year import AcademicYear
        from app.models.academic.class_entity import ClassEntity
        from app.models.academic.exam_schedule import ExamSchedule
        from app.models.academic.subject import Subject
        from app.models.security.auth_account import AuthAccount
        from app.models.security.enums import UserRole

        student_count = (
            db.query(func.count(AuthAccount.id))
            .filter(AuthAccount.school_id == school.id, AuthAccount.role == UserRole.STUDENT)
            .scalar()
            or 0
        )
        teacher_count = (
            db.query(func.count(AuthAccount.id))
            .filter(AuthAccount.school_id == school.id, AuthAccount.role == UserRole.TEACHER)
            .scalar()
            or 0
        )
        class_count = (
            db.query(func.count(ClassEntity.id)).filter(ClassEntity.school_id == school.id).scalar()
            or 0
        )
        subject_count = (
            db.query(func.count(Subject.id)).filter(Subject.school_id == school.id).scalar() or 0
        )
        active_year = (
            db.query(AcademicYear)
            .filter(AcademicYear.school_id == school.id, AcademicYear.status == "ACTIVE")
            .first()
        )
        active_exam_schedules = (
            db.query(func.count(ExamSchedule.id))
            .filter(
                ExamSchedule.school_id == school.id,
                ExamSchedule.status.in_(["ACTIVE", "READY", "PLANNED", "ONGOING"]),
            )
            .scalar()
            or 0
        )

        return {
            "school_id": school.id,
            "school_name": school.name,
            "school_code": school.code,
            "total_students": student_count,
            "total_teachers": teacher_count,
            "total_classes": class_count,
            "total_subjects": subject_count,
            "active_academic_year": active_year.name if active_year else "-",
            "active_academic_year_id": active_year.id if active_year else None,
            "active_exam_schedules": active_exam_schedules,
        }

    @staticmethod
    def delete_school(db: Session, public_id: uuid.UUID) -> None:
        school = school_repository.get_by_public_id(db, public_id)
        if not school:
            raise BusinessException("School not found", status_code=404)
        school.is_active = False
        school.deleted_at = datetime.now(timezone.utc)
        school_repository.update(db, school)
        db.commit()
