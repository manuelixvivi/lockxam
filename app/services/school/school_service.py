import uuid

from sqlalchemy.orm import Session

from app.core.security.password import hash_password
from app.exceptions.base import BusinessException
from app.models.license.school_license import SchoolLicense
from app.models.school.school import School
from app.models.school.school_setting import SchoolSetting

from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.master.school_level_repository import (
    school_level_repository,
)
from app.repositories.school.school_repository import school_repository
from app.repositories.school.school_setting_repository import (
    school_setting_repository,
)
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
        existing_domain = db.query(School).filter(School.domain == data.domain).first()
        if existing_domain:
            raise BusinessException(f"Domain '{data.domain}' sudah digunakan sekolah lain.", status_code=409)

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
        # Format: admin@admin.{domain}
        admin_username = f"admin@admin.{data.domain}"
        # Default password: eQu!6r4de@{code}
        admin_password = f"eQu!6r4de@{school_code}"
        admin_hashed_pw = hash_password(admin_password)

        admin_acc = AuthAccount(
            school_id=school.id,
            username=admin_username,
            password_hash=admin_hashed_pw,
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=True,  # Force password change on first login
        )
        auth_repository.create(db, admin_acc)
        db.flush()

        # Auto-apply initial subscription preset
        from app.models.master.license_type import LicenseType
        from app.services.license.license_service import LicenseService

        lic_type = db.query(LicenseType).filter(LicenseType.code == data.initial_subscription_preset).first()
        if not lic_type:
            raise BusinessException(f"Preset subscription '{data.initial_subscription_preset}' tidak valid.", status_code=400)

        # Get superadmin to be the key generator
        superadmin = db.query(AuthAccount).filter(AuthAccount.role == UserRole.SUPERADMIN).first()
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
        return school

    @staticmethod
    def _enrich_admin_username(db: Session, school: School) -> School:
        admin_acc = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.school_id == school.id,
                AuthAccount.role.in_([UserRole.ADMIN, "SCHOOL_ADMIN"]),
            )
            .first()
        )
        if admin_acc:
            setattr(school, "admin_username", admin_acc.username)
        else:
            setattr(school, "admin_username", None)

        # Enrich subscription status & expiration date
        latest_license = (
            db.query(SchoolLicense)
            .filter(SchoolLicense.school_id == school.id)
            .order_by(SchoolLicense.created_at.desc())
            .first()
        )
        if latest_license:
            setattr(school, "subscription_status", latest_license.status)
            setattr(school, "subscription_end_date", latest_license.end_date)
        else:
            setattr(school, "subscription_status", "NO_LICENSE")
            setattr(school, "subscription_end_date", None)

        # Enrich total registered students count

        total_students = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.school_id == school.id,
                AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
            )
            .count()
        )
        setattr(school, "registered_students_count", total_students)

        return school


    @staticmethod
    def toggle_school_subscription(db: Session, public_id: uuid.UUID) -> tuple[School, str]:
        school = SchoolService.get_school_by_public_id(db, public_id)
        latest_license = (
            db.query(SchoolLicense)
            .filter(SchoolLicense.school_id == school.id)
            .order_by(SchoolLicense.created_at.desc())
            .first()
        )
        if not latest_license:
            raise BusinessException(
                "Sekolah ini belum memiliki lisensi. Terbitkan Activation Key terlebih dahulu.",
                status_code=400,
            )

        new_status = "SUSPENDED" if latest_license.status == "ACTIVE" else "ACTIVE"
        latest_license.status = new_status
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
    def get_all_schools(db: Session) -> list[School]:
        schools = school_repository.get_all_active(db)
        for s in schools:
            SchoolService._enrich_admin_username(db, s)
        return schools

    @staticmethod
    def reset_school_admin_password(
        db: Session, public_id: uuid.UUID, new_password: str | None = None
    ) -> tuple[str, str]:
        school = SchoolService.get_school_by_public_id(db, public_id)
        admin_acc = (
            db.query(AuthAccount)
            .filter(
                AuthAccount.school_id == school.id,
                AuthAccount.role.in_([UserRole.ADMIN, "SCHOOL_ADMIN"]),
            )
            .first()
        )

        if not admin_acc:
            raise BusinessException(
                "Akun Admin Sekolah tidak ditemukan untuk sekolah ini.", status_code=404
            )

        if not new_password:
            # Reset to default: eQu!6r4de@{code}
            new_password = f"eQu!6r4de@{school.code}"

        from app.core.security.password import validate_password_strength
        validate_password_strength(new_password)
        admin_acc.password_hash = hash_password(new_password)
        admin_acc.must_change_password = True  # Force password change after reset
        db.commit()

        return admin_acc.username, new_password

    @staticmethod
    def update_school(db: Session, public_id: uuid.UUID, data: SchoolUpdateRequest) -> School:
        school = SchoolService.get_school_by_public_id(db, public_id)

        if data.npsn is not None and data.npsn.strip() != school.npsn:

            existing = school_repository.get_by_npsn(db, data.npsn.strip())
            if existing and existing.id != school.id:
                raise BusinessException(f"School with NPSN {data.npsn} already exists", status_code=400)
            school.npsn = data.npsn.strip()

        if data.code is not None:
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
            existing = db.query(School).filter(School.domain == data.domain.strip()).first()
            if existing and existing.id != school.id:
                raise BusinessException(f"Domain '{data.domain}' sudah digunakan sekolah lain.", status_code=409)
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
        if data.status is not None:
            school.status = data.status


        school_repository.update(db, school)
        db.commit()
        db.refresh(school)
        return SchoolService._enrich_admin_username(db, school)

    @staticmethod
    def delete_school(db: Session, public_id: uuid.UUID) -> None:
        school = SchoolService.get_school_by_public_id(db, public_id)
        
        # Free up unique constraints (NPSN and Domain) by appending a suffix
        suffix = f"_d_{school.id}"
        school.npsn = f"{school.npsn}{suffix}"
        if school.domain:
            school.domain = f"{school.domain}{suffix}"
            
        school_repository.soft_delete(db, school)
        db.commit()

