from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE schools ADD COLUMN domain VARCHAR(100) UNIQUE"))
        print("Added schools.domain")
    except Exception as e:
        print(f"schools.domain: {e}")

    try:
        conn.execute(text("ALTER TABLE auth_accounts ADD COLUMN must_change_password BOOLEAN DEFAULT true NOT NULL"))
        print("Added auth_accounts.must_change_password")
    except Exception as e:
        print(f"auth_accounts.must_change_password: {e}")

    conn.execute(text("UPDATE auth_accounts SET must_change_password = false WHERE role IN ('SUPERADMIN', 'SCHOOL_ADMIN')"))
    print("Updated existing accounts")
    conn.commit()
    print("Done.")
