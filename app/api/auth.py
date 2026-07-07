from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rbac import require_role
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SessionResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

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


@router.post("/revoke-session/{session_id}")
def revoke_session(
    session_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    AuthService.revoke_session(db=db, session_id=session_id, current_user=current_user)
    return {"message": "Session successfully revoked"}


@router.post("/logout-all")
def logout_all(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    AuthService.logout_all(db=db, current_user=current_user)
    return {"message": "Logged out of all sessions successfully"}


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user=Depends(get_current_user)):
    return CurrentUserResponse(
        user_id=int(current_user["sub"]),
        username="root",  # sementara
        role=current_user["role"],
        school_id=current_user["school_id"],
    )


@router.get("/superadmin-only")
def superadmin_only(current_user=Depends(require_role("SUPERADMIN"))):
    return {"message": "Welcome Superadmin", "current_user": current_user}
