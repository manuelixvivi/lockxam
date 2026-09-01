from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ImportRowError(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row: int
    field: str
    value: str | None = None
    code: str
    message: str


class ImportValidationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    total_rows: int
    valid_rows: int
    errors: list[ImportRowError]


class ImportResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["success", "error"]
    message: str
    imported_count: int
    errors: list[ImportRowError] | None = None
    data: list[T] | None = None
    skipped: list[dict] | None = None
