import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.school.school import School
from app.models.security.activity_log import ActivityLog
from app.models.security.auth_account import AuthAccount
from app.models.security.user_session import UserSession
from app.models.license.school_license import SchoolLicense
from app.models.master.license_type import LicenseType



def seed_database():
    print("=========================================")
    print("RUNNING EQUIGRADE DATABASE SEEDER SCRIPT")
    print("=========================================")

    # Ensure all tables exist before seeding
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # Clear old seeded test data to refresh sample data
        from app.models.license.activation_key import ActivationKey
        from app.models.license.renewal_request import RenewalRequest
        from app.models.academic.academic_year import AcademicYear
        from app.models.academic.academic_semester import AcademicSemester

        db.query(AcademicSemester).delete()
        db.query(AcademicYear).delete()
        db.query(SchoolLicense).delete()
        db.query(RenewalRequest).delete()
        db.query(ActivationKey).delete()
        db.query(UserSession).delete()
        db.query(ActivityLog).delete()
        db.query(AuthAccount).delete()
        db.query(School).delete()
        db.commit()



        print("1. Seeding Sample Schools...")
        school1 = School(
            public_id=uuid.uuid4(),
            npsn="20101234",
            code="SCH_2026_01",
            name="SMA Negeri 1 Nusantara",
            domain="sman1",
            school_level_id=4,  # SMA
            address="Jl. Pendidikan Merdeka No. 45, Kebayoran Baru, Jakarta Selatan",
            phone="(021) 555-8899",
            email="info@sman1nusantara.sch.id",
            website="https://www.sman1nusantara.sch.id",
            logo_url="https://images.unsplash.com/photo-1546410531-bb4caa6b424d?auto=format&fit=crop&w=120&q=80",
            is_active=True,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        school2 = School(
            public_id=uuid.uuid4(),
            npsn="20105678",
            code="SCH_2026_02",
            name="SMK Telekomunikasi Garuda",
            domain="smkgaruda",
            school_level_id=5,  # SMK
            address="Jl. Garuda Sakti No. 88, Lengkong, Bandung",
            phone="(022) 777-3344",
            email="contact@smkgaruda.sch.id",
            website="https://www.smkgaruda.sch.id",
            logo_url=None,
            is_active=True,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add_all([school1, school2])
        db.flush()
        print("   Successfully seeded 2 sample schools.")

        print("2. Seeding Sample Active Subscription License...")
        perm_type = db.query(LicenseType).filter_by(code="PERMANENT").first()
        license_type_id = perm_type.id if perm_type else 7

        sample_license = SchoolLicense(
            public_id=uuid.uuid4(),
            school_id=school1.id,
            license_type_id=license_type_id,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=99999),
            max_users=1000,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(sample_license)
        db.flush()
        print("   Seeded active PERMANENT subscription license for 'SMA Negeri 1 Nusantara'.")

        # Default password for all seeded accounts
        default_pwd = hash_password("Password123!")

        print("3. Seeding Auth Accounts (SUPERADMIN)...")
        superadmin = AuthAccount(
            public_id=uuid.uuid4(),
            school_id=school1.id,
            username="superadmin",
            password_hash=default_pwd,
            role="SUPERADMIN",
            is_active=True,
            must_change_password=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(superadmin)

        print("4. Seeding Auth Accounts (SCHOOL_ADMIN)...")
        school_admin = AuthAccount(
            public_id=uuid.uuid4(),
            school_id=school1.id,
            username="admin_school",
            password_hash=default_pwd,
            role="SCHOOL_ADMIN",
            is_active=True,
            must_change_password=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(school_admin)

        print("5. Seeding Auth Accounts (TEACHER)...")
        teachers = []
        for i in range(5):
            teacher = AuthAccount(
                public_id=uuid.uuid4(),
                school_id=school1.id if i < 3 else school2.id,
                username=f"teacher{i+1}",
                password_hash=default_pwd,
                role="TEACHER",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(teacher)
            teachers.append(teacher)

        print("6. Seeding Auth Accounts (STUDENT)...")
        students = []
        for i in range(10):
            student = AuthAccount(
                public_id=uuid.uuid4(),
                school_id=school1.id if i < 6 else school2.id,
                username=f"student{i+1}",
                password_hash=default_pwd,
                role="STUDENT",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(student)
            students.append(student)

        print("7. Seeding Sample Academic Years & Semesters...")
        from app.models.academic.academic_year import AcademicYear
        from app.models.academic.academic_semester import AcademicSemester

        ay_active = AcademicYear(
            public_id=uuid.uuid4(),
            school_id=school1.id,
            name="2025/2026",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc) + timedelta(days=335),
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        ay_planned = AcademicYear(
            public_id=uuid.uuid4(),
            school_id=school1.id,
            name="2026/2027",
            start_date=datetime.now(timezone.utc) + timedelta(days=336),
            end_date=datetime.now(timezone.utc) + timedelta(days=700),
            status="PLANNED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add_all([ay_active, ay_planned])
        db.flush()

        sem_odd = AcademicSemester(
            public_id=uuid.uuid4(),
            academic_year_id=ay_active.id,
            code="ODD",
            display_name="Semester Ganjil",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        sem_even = AcademicSemester(
            public_id=uuid.uuid4(),
            academic_year_id=ay_active.id,
            code="EVEN",
            display_name="Semester Genap",
            status="PLANNED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add_all([sem_odd, sem_even])

        db.commit()
        print("=========================================")
        print("   SAMPLE DATA SEEDING COMPLETE 100%!   ")
        print("=========================================")


    except Exception as e:
        print("Error seeding database sample data:", e)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
