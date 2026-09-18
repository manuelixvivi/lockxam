from app.core.database import SessionLocal
from app.models.master.license_type import LicenseType
from app.models.master.school_level import SchoolLevel

db = SessionLocal()
try:
    print("Inserting base school_levels...")
    level1 = db.query(SchoolLevel).filter_by(id=4).first()
    if not level1:
        db.add(SchoolLevel(id=4, code="SMA", name="SMA", description="SMA"))
    level2 = db.query(SchoolLevel).filter_by(id=5).first()
    if not level2:
        db.add(SchoolLevel(id=5, code="SMK", name="SMK", description="SMK"))

    print("Inserting license_types...")
    lic = db.query(LicenseType).filter_by(id=7).first()
    if not lic:
        db.add(
            LicenseType(
                id=7,
                code="PERMANENT",
                name="Permanent",
                duration_days=3650,
                max_users=9999,
                is_active=True,
            )
        )

    db.commit()
    print("Lookup data inserted successfully!")
except Exception as e:
    db.rollback()
    print("Error:", e)
finally:
    db.close()
