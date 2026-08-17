from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rbac import require_role
from app.models.security.enums import UserRole
from app.repositories.security.auth_repository import auth_repository
from app.schemas.security.auth import (
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SessionResponse,
    TokenResponse,
)
from app.services.security.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return AuthService.login(db=db, request=request, data=data)


@router.post("/logout", status_code=204)
def logout(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    AuthService.logout(
        db=db, current_user=current_user, ip_address=ip_address, user_agent=user_agent
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService.refresh(db=db, data=data)


@router.get("/sessions", response_model=list[SessionResponse])
def get_active_sessions(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return AuthService.get_active_sessions(db=db, current_user=current_user)


@router.post("/revoke-session/{session_id}", status_code=200)
def revoke_session(
    session_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    AuthService.revoke_session(db=db, session_id=session_id, current_user=current_user)
    return {"message": "Session successfully revoked"}


@router.post("/logout-all", status_code=200)
def logout_all(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    AuthService.logout_all(db=db, current_user=current_user)
    return {"message": "Logged out of all sessions successfully"}


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = int(current_user["sub"])
    account = auth_repository.get_by_id(db, user_id)
    school_level_code = None
    school_name = None
    resolved_class_name = account.class_name if account else None

    if account and account.school_id:
        if account.role in [UserRole.TEACHER, "TEACHER"]:
            from app.services.school.staff_service import SchoolStaffService
            SchoolStaffService.list_teachers(db, account.school_id)
            db.refresh(account)

        if account.role in [UserRole.STUDENT, "STUDENT"] and not resolved_class_name:
            from app.models.academic.student_class_enrollment import StudentClassEnrollment
            from app.models.academic.class_entity import ClassEntity
            enrollment = db.query(StudentClassEnrollment).filter(
                StudentClassEnrollment.student_id == account.id,
                StudentClassEnrollment.status == "ACTIVE"
            ).first()
            if enrollment:
                cls = db.query(ClassEntity).filter(ClassEntity.id == enrollment.class_id).first()
                if cls:
                    resolved_class_name = cls.name
                    account.class_name = cls.name
                    db.commit()

        from app.models.school.school import School
        from app.models.master.school_level import SchoolLevel
        school = db.query(School).filter(School.id == account.school_id).first()
        if school:
            school_name = school.name
            if school.school_level_id:
                s_lvl = db.query(SchoolLevel).filter(SchoolLevel.id == school.school_level_id).first()
                if s_lvl:
                    school_level_code = s_lvl.code

    return CurrentUserResponse(
        user_id=user_id,
        username=account.username if account else "unknown",
        role=current_user["role"],
        school_id=current_user.get("school_id"),
        school_name=school_name,
        school_level_code=school_level_code,
        must_change_password=account.must_change_password if account else False,
        name=account.name if account else None,
        nis=account.nis if account else None,
        nisn=account.nisn if account else None,
        birth_date=account.birth_date if account else None,
        gender=account.gender if account else None,
        class_name=resolved_class_name,
        registered_year=account.registered_year if account else None,
        nip=account.nip if account else None,
        teacher_code=account.teacher_code if account else None,
        subjects_taught=account.subjects_taught if account else None,
        classes_taught=account.classes_taught if account else None,
    )


@router.post("/change-password", status_code=200)
def change_password(
    data: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    AuthService.change_password(
        db=db,
        current_user=current_user,
        old_password=data.old_password,
        new_password=data.new_password,
    )
    return {"message": "Kata sandi berhasil diperbarui"}


@router.get("/superadmin-only")
def superadmin_only(current_user=Depends(require_role(UserRole.SUPERADMIN))):  # CF-3: Use Enum
    return {"message": "Welcome Superadmin", "current_user": current_user}

