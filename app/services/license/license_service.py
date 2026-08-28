import hashlib
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.license.activation_key import ActivationKey
from app.models.license.renewal_request import RenewalRequest
from app.models.license.school_license import SchoolLicense
from app.repositories.license.activation_key_repository import activation_key_repository
from app.repositories.license.renewal_request_repository import renewal_request_repository
from app.repositories.license.school_license_repository import school_license_repository
from app.repositories.master.license_type_repository import license_type_repository
from app.repositories.school.school_repository import school_repository
from app.repositories.security.auth_repository import auth_repository


class LicenseService:

    @staticmethod
    def hash_key(plain_key: str) -> str:
        return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_activation_key(
        db: Session,
        license_type_id: int,
        school_id: int,
        generated_by_id: int,
        validity_days: int = 30,
    ) -> tuple[ActivationKey, str]:
        # Validate master license type
        lic_type = license_type_repository.get_by_id(db, license_type_id)
        if not lic_type:
            raise BusinessException("License type not found", status_code=404)

        # Validate school exists
        school = school_repository.get_by_id(db, school_id)
        if not school:
            raise BusinessException("School not found", status_code=404)

        # Generate unique secure token
        raw_key = f"EQG-{secrets.token_hex(16).upper()}"
        hashed = LicenseService.hash_key(raw_key)

        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(days=validity_days)

        key_record = ActivationKey(
            key=hashed,
            license_type_id=license_type_id,
            school_id=school_id,
            generated_by_id=generated_by_id,
            valid_until=valid_until,
            status="GENERATED",
        )
        activation_key_repository.create(db, key_record)
        db.flush()

        return key_record, raw_key

    @staticmethod
    def cancel_activation_key(db: Session, public_id: UUID, cancelled_by_id: int) -> ActivationKey:
        key_record = activation_key_repository.get_by_public_id(db, public_id)
        if not key_record:
            raise BusinessException("Activation key not found", status_code=404)

        if key_record.status != "GENERATED":
            raise BusinessException(
                f"Cannot cancel activation key in status {key_record.status}", status_code=400
            )

        # Check if key was created more than 3 days ago (259200 seconds)
        now = datetime.now(timezone.utc)
        created_at = key_record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if (now - created_at).total_seconds() > 3 * 24 * 3600:
            raise BusinessException(
                "Activation Key tidak dapat dibatalkan setelah 3 hari diinput/dibuat.",
                status_code=400,
            )

        key_record.status = "CANCELLED"
        key_record.cancelled_by_id = cancelled_by_id
        key_record.cancelled_at = datetime.now(timezone.utc)

        activation_key_repository.update(db, key_record)
        return key_record

    @staticmethod
    def activate_license(
        db: Session, plain_key: str, school_id: int, used_by_id: int
    ) -> SchoolLicense:
        # BR-LIC-019 / BR-LIC-001: Idempotency & validation
        hashed = LicenseService.hash_key(plain_key)
        key_record = activation_key_repository.get_by_key(db, hashed)

        if not key_record:
            raise BusinessException("Invalid activation key", status_code=400)

        if key_record.status == "USED":
            raise BusinessException("Activation Key has already been used", status_code=400)

        if key_record.status == "CANCELLED":
            raise BusinessException("Activation Key was cancelled", status_code=400)

        # BR-LIC-002: Expiration check
        now = datetime.now(timezone.utc)
        if key_record.status == "EXPIRED" or key_record.valid_until < now:
            if key_record.status != "EXPIRED":
                key_record.status = "EXPIRED"
                activation_key_repository.update(db, key_record)
            raise BusinessException("Activation Key has expired", status_code=400)

        # BR-LIC-013: Ownership Check
        if key_record.school_id != school_id:
            raise BusinessException(
                "Activation Key is not designated for this school", status_code=400
            )

        # Get school
        school = school_repository.get_by_id(db, school_id)
        if not school:
            raise BusinessException("School not found", status_code=404)

        # Get license type
        lic_type = license_type_repository.get_by_id(db, key_record.license_type_id)
        if not lic_type:
            raise BusinessException("License type associated with key not found", status_code=404)

        # BR-LIC-005 / BR-LIC-006: Consecutive scheduling check & Permanent license priority
        is_permanent = lic_type.code == "PERMANENT" or lic_type.duration_days >= 9999
        active_lic = school_license_repository.get_active_license(db, school_id)

        if is_permanent:
            # Permanent license immediately takes effect and supersedes temporary licenses
            start_date = now
            status = "ACTIVE"
            school.status = "ACTIVE"
            school.is_active = True
            school_repository.update(db, school)
            # Mark previous active temporary license as SUPERSEDED
            if active_lic:
                active_lic.status = "SUPERSEDED"
                school_license_repository.update(db, active_lic)
        elif active_lic:
            # If current active is already PERMANENT, don't downgrade
            if active_lic.license_type_id == 7 or (
                active_lic.end_date and active_lic.end_date.year > 2070
            ):
                start_date = active_lic.end_date
                status = "SUPERSEDED"
            else:
                # Schedule for after current expires
                start_date = active_lic.end_date
                status = "PENDING"
        else:
            # Active immediately
            start_date = now
            status = "ACTIVE"
            school.status = "ACTIVE"
            school_repository.update(db, school)

        # Calculate end_date from master license_type duration_days
        end_date = start_date + timedelta(days=lic_type.duration_days)

        # Create new School License (BR-LIC-016: Immutable license record)
        new_license = SchoolLicense(
            school_id=school_id,
            license_type_id=key_record.license_type_id,
            activation_key_id=key_record.id,
            start_date=start_date,
            end_date=end_date,
            max_users=lic_type.max_users,
            status=status,
        )
        school_license_repository.create(db, new_license)

        # Update key record to USED
        key_record.status = "USED"
        key_record.used_at = now
        key_record.used_by_id = used_by_id
        activation_key_repository.update(db, key_record)

        return new_license

    @staticmethod
    def get_licenses_by_school(db: Session, school_id: int) -> list[SchoolLicense]:
        return school_license_repository.get_licenses_by_school(db, school_id)

    @staticmethod
    def get_license_history(db: Session, school_id: int) -> list[SchoolLicense]:
        return school_license_repository.get_licenses_by_school(db, school_id)

    @staticmethod
    def request_renewal(
        db: Session,
        school_id: int,
        requested_by_id: int,
        license_type_id: int,
        payment_proof_url: str | None = None,
    ) -> RenewalRequest:
        school = school_repository.get_by_id(db, school_id)
        if not school:
            raise BusinessException("School not found", status_code=404)

        lic_type = license_type_repository.get_by_id(db, license_type_id)
        if not lic_type:
            raise BusinessException("License type not found", status_code=404)

        now = datetime.now(timezone.utc)
        req_number = f"RNW-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        new_req = RenewalRequest(
            request_number=req_number,
            school_id=school_id,
            requested_by_id=requested_by_id,
            license_type_id=license_type_id,
            payment_proof_url=payment_proof_url,
            status="REQUESTED",
        )
        return renewal_request_repository.create(db, new_req)

    @staticmethod
    def process_renewal(
        db: Session,
        public_id: uuid.UUID,
        status: str,
        superadmin_notes: str | None,
        processed_by_id: int,
    ) -> tuple[RenewalRequest, ActivationKey | None, str | None]:
        req = renewal_request_repository.get_by_public_id(db, public_id)
        if not req:
            raise BusinessException("Renewal request not found", status_code=404)

        if req.status != "REQUESTED":
            raise BusinessException("Renewal request already processed", status_code=400)

        req.status = status
        req.superadmin_notes = superadmin_notes
        req.processed_by_id = processed_by_id
        req.processed_at = datetime.now(timezone.utc)

        key_record = None
        raw_key = None

        if status == "APPROVED":
            # Auto-generate activation key targeted for the school
            key_record, raw_key = LicenseService.generate_activation_key(
                db=db,
                license_type_id=req.license_type_id,
                school_id=req.school_id,
                generated_by_id=processed_by_id,
            )
            req.status = "COMPLETED"

        renewal_request_repository.update(db, req)
        return req, key_record, raw_key

    @staticmethod
    def get_my_license(db: Session, school_id: int) -> SchoolLicense | None:
        # Prioritize ACTIVE permanent license or current ACTIVE license
        lic = school_license_repository.get_active_license(db, school_id)
        if not lic:
            # Fallback to latest license if none active
            lic = school_license_repository.get_latest_license(db, school_id)
        if lic:
            total_students = auth_repository.count_students_by_school(db, school_id)
            lic.registered_students_count = total_students
        return lic
