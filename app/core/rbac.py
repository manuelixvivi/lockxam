from fastapi import Depends, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from app.core.dependencies import get_current_user


def require_role(*allowed_roles: str):
    def checker(current_user=Depends(get_current_user)):

        user_role = current_user.get("role")

        if user_role not in allowed_roles:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Permission denied")

        return current_user

    return checker


def require_any_role(*allowed_roles: str):
    return require_role(*allowed_roles)


def require_superadmin():
    return require_role("SUPERADMIN")


def require_admin():
    return require_role("ADMIN")


def require_teacher():
    return require_role("TEACHER")


def require_student():
    return require_role("STUDENT")


def require_staff():
    return require_role("SUPERADMIN", "ADMIN")


def require_academic_staff():
    return require_role("SUPERADMIN", "ADMIN", "TEACHER")


def require_authenticated():
    return require_role("SUPERADMIN", "ADMIN", "TEACHER", "STUDENT")


def is_superadmin(current_user):

    return current_user["role"] == "SUPERADMIN"


def is_admin(current_user):

    return current_user["role"] == "ADMIN"


def is_teacher(current_user):

    return current_user["role"] == "TEACHER"


def is_student(current_user):

    return current_user["role"] == "STUDENT"
