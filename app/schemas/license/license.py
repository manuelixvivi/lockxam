from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActivationKeyGenerateRequest(BaseModel):
    license_type_id: int
    school_id: int
    validity_days: int = Field(default=30, ge=1)


class ActivationKeyGenerateResponse(BaseModel):
    public_id: UUID
    key_plain: str
    valid_until: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class ActivationKeyResponse(BaseModel):
    public_id: UUID
    key: str
    school_id: int
    license_type_id: int
    valid_until: datetime
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LicenseActivateRequest(BaseModel):
    key_plain: str


class LicenseActivateResponse(BaseModel):
    public_id: UUID
    school_id: int
    license_type_id: int
    start_date: datetime
    end_date: datetime
    max_users: int
    status: str
    registered_students_count: int = 0

    model_config = ConfigDict(from_attributes=True)



class RenewalRequestCreateRequest(BaseModel):
    license_type_id: int
    payment_proof_url: str | None = None


class RenewalRequestResponse(BaseModel):
    public_id: UUID
    request_number: str
    school_id: int
    requested_by_id: int
    license_type_id: int
    status: str
    payment_proof_url: str | None = None
    superadmin_notes: str | None = None
    processed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RenewalProcessRequest(BaseModel):
    status: str = Field(description="Must be APPROVED or REJECTED")
    superadmin_notes: str | None = None


class RenewalProcessResponse(BaseModel):
    renewal: RenewalRequestResponse
    key_plain: str | None = None

    model_config = ConfigDict(from_attributes=True)
