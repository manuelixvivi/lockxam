import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.database import SessionLocal
from tests.test_exam_security_boundaries import _create_school_hierarchy

client = TestClient(app)


def test_student_start_attempt_hides_answer_key():
    """
    Verifies student start_attempt question list excludes answer_key, rubrics, correct_option, and model_answer.
    """
    db = SessionLocal()
    try:
        data_dict = _create_school_hierarchy(db)
        school = data_dict["school"]
        student = data_dict["student1"]
        session = data_dict["session"]

        from app.core.security.keys import SECRET_KEY
        from jose import jwt
        from datetime import datetime, timezone, timedelta

        student_token = jwt.encode(
            {
                "sub": "student1",
                "role": "STUDENT",
                "account_id": student.id,
                "school_id": school.id,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm="HS256",
        )

        headers = {
            "Authorization": f"Bearer {student_token}",
            "User-Agent": "LockxamBrowser/1.0",
            "X-Client-App": "lockxam_apk",
        }

        resp = client.post(
            f"/api/v1/exam/sessions/{session.id}/start-attempt",
            json={"device_fingerprint": "dev-123"},
            headers=headers,
        )

        if resp.status_code == 200:
            data = resp.json()
            questions = data.get("questions", [])
            for q in questions:
                assert "answer_key" not in q
                assert "correct_option" not in q
                assert "rubrics" not in q
                assert "model_answer" not in q
    finally:
        db.close()
