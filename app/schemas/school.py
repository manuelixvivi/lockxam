from pydantic import BaseModel


class SchoolCreate(BaseModel):

    code: str
    name: str

    address: str | None = None

    phone: str | None = None

    email: str | None = None
