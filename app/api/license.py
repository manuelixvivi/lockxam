from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_academic_staff, require_admin, require_superadmin
from app.repositories.license.renewal_request_repository import renewal_request_repository
from app.schemas.license.license import (
    ActivationKeyGenerateRequest,
    ActivationKeyGenerateResponse,
    ActivationKeyResponse,
    LicenseActivateRequest,
    LicenseActivateResponse,
    RenewalProcessRequest,
    RenewalProcessResponse,
    RenewalRequestCreateRequest,
    RenewalRequestResponse,
)
from app.services.license.license_service import LicenseService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/licenses", tags=["License Management"])


@router.post("/keys", response_model=ActivationKeyGenerateResponse)
def generate_activation_key(
    data: ActivationKeyGenerateRequest,
    request: Request,
    current_user=Depends(require_superadmin()),
    db: Session = Depends(get_db),
):
    user_id = int(current_user["sub"])
    key_record, raw_key = LicenseService.generate_activation_key(
        db=db,
        license_type_id=data.license_type_id,
        school_id=data.school_id,
        generated_by_id=user_id,
        validity_days=data.validity_days,
    )

    db.commit()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="LICENSE",
        action_name="GENERATE_ACTIVATION_KEY",
        school_id=data.school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"activation_key_id": key_record.id},
    )
    db.commit()

    return ActivationKeyGenerateResponse(
        public_id=key_record.public_id,
        key_plain=raw_key,
        valid_until=key_record.valid_until,
        status=key_record.status,
    )


@router.post("/keys/{public_id}/cancel")
def cancel_activation_key(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_superadmin()),
    db: Session = Depends(get_db),
):
    user_id = int(current_user["sub"])
    key_record = LicenseService.cancel_activation_key(
        db=db, public_id=public_id, cancelled_by_id=user_id
    )
    db.commit()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="LICENSE",
        action_name="CANCEL_ACTIVATION_KEY",
        school_id=key_record.school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"activation_key_id": key_record.id},
    )
    db.commit()

    return {"message": "Activation key successfully cancelled"}


@router.get("/keys", response_model=list[ActivationKeyResponse])
def list_activation_keys(
    current_user=Depends(require_superadmin()),
    db: Session = Depends(get_db),
):
    from app.repositories.license.activation_key_repository import activation_key_repository
    # Return all activation keys ordered by created_at desc
    from app.models.license.activation_key import ActivationKey
    return db.query(ActivationKey).order_by(ActivationKey.created_at.desc()).all()


@router.post("/activate", response_model=LicenseActivateResponse)
def activate_license(
    data: LicenseActivateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    user_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        from app.exceptions.base import BusinessException

        raise BusinessException("Admin account is not associated with any school", status_code=400)

    license_record = LicenseService.activate_license(
        db=db, plain_key=data.key_plain, school_id=school_id, used_by_id=user_id
    )
    db.commit()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="LICENSE",
        action_name="ACTIVATE_LICENSE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"school_license_id": license_record.id},
    )
    db.commit()

    return license_record


@router.post("/renewals", response_model=RenewalRequestResponse)
def request_renewal(
    data: RenewalRequestCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    user_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        from app.exceptions.base import BusinessException

        raise BusinessException("Admin account is not associated with any school", status_code=400)

    renewal_record = LicenseService.request_renewal(
        db=db,
        school_id=school_id,
        requested_by_id=user_id,
        license_type_id=data.license_type_id,
        payment_proof_url=data.payment_proof_url,
    )
    db.commit()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="LICENSE",
        action_name="REQUEST_RENEWAL",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"renewal_request_id": renewal_record.id},
    )
    db.commit()

    return renewal_record


@router.get("/renewals", response_model=list[RenewalRequestResponse])
def list_renewal_requests(
    current_user=Depends(require_superadmin()),
    db: Session = Depends(get_db),
):
    return renewal_request_repository.get_all(db)


@router.post("/renewals/{public_id}/process", response_model=RenewalProcessResponse)
def process_renewal(
    public_id: UUID,
    data: RenewalProcessRequest,
    request: Request,
    current_user=Depends(require_superadmin()),
    db: Session = Depends(get_db),
):
    user_id = int(current_user["sub"])
    renewal, key_record, raw_key = LicenseService.process_renewal(
        db=db,
        public_id=public_id,
        status=data.status,
        superadmin_notes=data.superadmin_notes,
        processed_by_id=user_id,
    )
    db.commit()

    # Log Activity
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="LICENSE",
        action_name="PROCESS_RENEWAL",
        school_id=renewal.school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"renewal_request_id": renewal.id, "status": data.status},
    )
    db.commit()

    return RenewalProcessResponse(
        renewal=RenewalRequestResponse.model_validate(renewal), key_plain=raw_key
    )


@router.get("/my-license", response_model=LicenseActivateResponse | None)
def get_my_license(
    current_user=Depends(require_academic_staff()),
    db: Session = Depends(get_db),
):
    school_id = current_user.get("school_id")
    if not school_id:
        return None
    return LicenseService.get_my_license(db=db, school_id=school_id)
