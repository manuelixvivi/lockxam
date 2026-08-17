from sqlalchemy.orm import Session

from app.models.master.license_type import LicenseType
from app.models.master.school_level import SchoolLevel


def seed_master_data(db: Session) -> None:
    # 1. Seed School Levels
    levels = ["TK", "SD", "SMP", "SMA", "SMK", "MI", "MTS", "MA"]
    for lvl in levels:
        existing_level = db.query(SchoolLevel).filter(SchoolLevel.code == lvl).first()
        if not existing_level:
            db.add(SchoolLevel(name=lvl, code=lvl, description=f"Jenjang Pendidikan {lvl}"))

    # 2. Seed License Types
    license_info = [
        ("ONE_WEEK", "One Week License", 7, 50),
        ("ONE_MONTH", "One Month License", 30, 100),
        ("THREE_MONTHS", "Three Months License", 90, 250),
        ("SIX_MONTHS", "Six Months License", 180, 500),
        ("ONE_YEAR", "One Year License", 365, 1000),
        ("TWO_YEARS", "Two Years License", 730, 2500),
        ("PERMANENT", "Permanent License", 99999, 999999),
    ]
    for code, name, duration, max_users in license_info:
        existing_license = db.query(LicenseType).filter(LicenseType.code == code).first()
        if not existing_license:
            db.add(
                LicenseType(
                    code=code,
                    name=name,
                    duration_days=duration,
                    max_users=max_users,
                    is_active=True,
                )
            )
    db.commit()
