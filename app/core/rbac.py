from typing import Any, Optional, Union

from fastapi import Depends, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from app.core.dependencies import get_current_user
from app.models.security.enums import UserRole


def normalize_role(role: Any) -> Optional[UserRole]:
    """
    Canonical normalizer for user roles.
    Maps string representations and legacy variants ("SCHOOL_ADMIN", "SUPER_ADMIN")
    strictly to canonical UserRole enum instances.
    """
    if not role:
        return None
    if isinstance(role, UserRole):
        return role
    role_str = str(role).strip().upper()
    if role_str in ("SUPERADMIN", "SUPER_ADMIN"):
        return UserRole.SUPERADMIN
    if role_str in ("ADMIN", "SCHOOL_ADMIN"):
        return UserRole.ADMIN
    if role_str == "TEACHER":
        return UserRole.TEACHER
    if role_str == "STUDENT":
        return UserRole.STUDENT
    try:
        return UserRole(role_str)
    except ValueError:
        return None


def require_role(*allowed_roles: Union[UserRole, str]):
    normalized_allowed = {
        normalize_role(r) for r in allowed_roles if normalize_role(r) is not None
    }

    def checker(current_user=Depends(get_current_user)):
        user_role = normalize_role(current_user.get("role"))
        if user_role not in normalized_allowed:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_user

    return checker


def require_any_role(*allowed_roles: Union[UserRole, str]):
    return require_role(*allowed_roles)


def require_superadmin():
    return require_role(UserRole.SUPERADMIN)


def require_admin():
    return require_role(UserRole.ADMIN)


def require_teacher():
    return require_role(UserRole.TEACHER)


def require_student():
    return require_role(UserRole.STUDENT)


def require_staff():
    return require_role(UserRole.SUPERADMIN, UserRole.ADMIN)


def require_academic_staff():
    return require_role(UserRole.SUPERADMIN, UserRole.ADMIN, UserRole.TEACHER)


def require_authenticated():
    return require_role(
        UserRole.SUPERADMIN,
        UserRole.ADMIN,
        UserRole.TEACHER,
        UserRole.STUDENT,
    )


def is_superadmin(current_user: Any) -> bool:
    role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", current_user)
    return normalize_role(role) == UserRole.SUPERADMIN


def is_admin(current_user: Any) -> bool:
    role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", current_user)
    return normalize_role(role) == UserRole.ADMIN


def is_teacher(current_user: Any) -> bool:
    role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", current_user)
    return normalize_role(role) == UserRole.TEACHER


def is_student(current_user: Any) -> bool:
    role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", current_user)
    return normalize_role(role) == UserRole.STUDENT
