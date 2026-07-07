from pydantic import BaseModel


class AdminCreate(BaseModel):

    school_id: int

    username: str

    password: str

    fullname: str

    email: str | None = None
