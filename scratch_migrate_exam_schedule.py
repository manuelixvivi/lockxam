import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
print("Connecting to:", DATABASE_URL)
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Running migration for exam_schedules table...")
    conn.execute(text("ALTER TABLE exam_schedules ADD COLUMN IF NOT EXISTS target_type VARCHAR(20) DEFAULT 'ALL_CLASS';"))
    conn.execute(text("ALTER TABLE exam_schedules ADD COLUMN IF NOT EXISTS allowed_student_ids JSON;"))
    conn.commit()
    print("Migration successful!")
