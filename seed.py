import uuid
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.activity_log import ActivityLog
from app.models.auth_account import AuthAccount
from app.models.school import School
from app.models.user_session import UserSession

fake = Faker()


def seed_database():
    print("=========================================")
    print("RUNNING EQUIGRADE DATABASE SEEDER SCRIPT")
    print("=========================================")

    # Ensure all tables exist before seeding
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # Check if we already have seeded data
        existing_school = db.query(School).first()
        if existing_school:
            print("Database already has seeded data. Skipping...")
            return

        print("1. Seeding Schools...")
        schools = []
        for _ in range(2):
            school = School(
                public_id=uuid.uuid4(),
                code=f"SCH_{fake.unique.random_number(digits=4)}",
                name=f"{fake.company()} Academy",
                address=fake.address(),
                phone=fake.phone_number(),
                email=fake.email(),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(school)
            schools.append(school)
        db.flush()
        print(f"   Successfully seeded {len(schools)} schools.")

        # Default password for all seeded accounts
        default_pwd = hash_password("Password123!")

        print("2. Seeding Auth Accounts (SUPERADMIN)...")
        superadmin = AuthAccount(
            public_id=uuid.uuid4(),
            school_id=schools[0].id,
            username="superadmin",
            password_hash=default_pwd,
            role="SUPERADMIN",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(superadmin)
        print("   Seeded superadmin account (username: 'superadmin', password: 'Password123!').")

        print("3. Seeding Auth Accounts (TEACHER)...")
        teachers = []
        for i in range(5):
            teacher = AuthAccount(
                public_id=uuid.uuid4(),
                school_id=schools[0].id if i < 3 else schools[1].id,
                username=f"teacher{i+1}",
                password_hash=default_pwd,
                role="TEACHER",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(teacher)
            teachers.append(teacher)
        print(
            f"   Seeded {len(teachers)} teacher accounts (username: 'teacher1'-'teacher5', password: 'Password123!')."
        )

        print("4. Seeding Auth Accounts (STUDENT)...")
        students = []
        for i in range(10):
            student = AuthAccount(
                public_id=uuid.uuid4(),
                school_id=schools[0].id if i < 6 else schools[1].id,
                username=f"student{i+1}",
                password_hash=default_pwd,
                role="STUDENT",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(student)
            students.append(student)
        print(
            f"   Seeded {len(students)} student accounts (username: 'student1'-'student10', password: 'Password123!')."
        )

        # Flush to database
        db.flush()

        print("5. Seeding User Sessions & activity logs...")
        all_accounts = [superadmin] + teachers + students
        for acc in all_accounts[:5]:  # only create sessions for first 5 accounts
            # Create a session
            session_id = uuid.uuid4()
            access_jti = uuid.uuid4()
            refresh_jti = uuid.uuid4()

            session = UserSession(
                id=session_id,
                auth_account_id=acc.id,
                access_token_jti=access_jti,
                refresh_token_jti=refresh_jti,
                ip_address=fake.ipv4(),
                user_agent=fake.user_agent(),
                created_at=datetime.utcnow() - timedelta(days=1),
                last_activity_at=datetime.utcnow() - timedelta(hours=2),
                expires_at=datetime.utcnow() + timedelta(days=29),
                revoked=False,
            )
            db.add(session)

            # Create log activity
            log_login = ActivityLog(
                auth_account_id=acc.id,
                school_id=acc.school_id,
                session_id=session_id,
                action_type="AUTH",
                action_name="LOGIN_SUCCESS",
                endpoint="/api/auth/login",
                method="POST",
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                meta_data={},
                created_at=datetime.utcnow() - timedelta(days=1),
            )
            db.add(log_login)

        # Commit everything
        db.commit()
        print("   Database seeded successfully!")
        print("=========================================")

    except Exception as e:
        print("Error seeding database:", e)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
