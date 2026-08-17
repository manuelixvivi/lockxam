from pydantic import BaseModel


class SchoolLevelResponse(BaseModel):
    id: int
    name: str
    code: str
    description: str | None

    class Config:
        from_attributes = True


class LicenseTypeResponse(BaseModel):
    id: int
    name: str
    code: str
    duration_days: int
    max_users: int
    is_active: bool

    class Config:
        from_attributes = True
