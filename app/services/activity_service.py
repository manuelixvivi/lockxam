from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


def log_activity(
    db: Session,
    auth_account_id: int,
    action_type: str,
    action_name: str,
    school_id: int | None = None,
    session_id: str | None = None,
    endpoint: str | None = None,
    method: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
):
    activity = ActivityLog(
        auth_account_id=auth_account_id,
        school_id=school_id,
        session_id=session_id,
        action_type=action_type,
        action_name=action_name,
        endpoint=endpoint,
        method=method,
        ip_address=ip_address,
        user_agent=user_agent,
        meta_data=metadata or {},
    )

    db.add(activity)

    return activity


def log_login(
    db: Session,
    auth_account_id: int,
    school_id: int | None,
    session_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    return log_activity(
        db=db,
        auth_account_id=auth_account_id,
        school_id=school_id,
        session_id=session_id,
        action_type="AUTH",
        action_name="LOGIN_SUCCESS",
        endpoint="/api/v1/auth/login",
        method="POST",
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_login_failed(db: Session, username: str, ip_address: str | None = None):
    return log_activity(
        db=db,
        auth_account_id=0,
        action_type="AUTH",
        action_name="LOGIN_FAILED",
        ip_address=ip_address,
        metadata={"username": username},
    )
