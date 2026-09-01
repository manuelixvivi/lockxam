import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.academic.class_entity import ClassEntity
from app.models.academic.class_subject import ClassSubject
from app.models.academic.exam_snapshot import ExamSnapshot
from app.models.academic.subject import Subject
from app.models.academic.teacher_subject import TeacherSubject
from app.models.teacher.enums import QuestionType
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage

# ============================================================
# QUESTION BANK IMPORT TESTS
# ============================================================


def test_import_questions_valid_pg_batch(client: TestClient, api_test_data, db: Session):
    """TEST 1: Valid batch of PG questions -> imported successfully."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Berapakah 2 + 2?",
                "options": ["2", "3", "4", "5"],
                "answer_key": "4",
                "class_level": "X",
                "row_num": 2,
                "sheet": "Pilihan Ganda",
            },
            {
                "type": "PG",
                "content": "Berapakah 3 x 3?",
                "options": ["6", "7", "8", "9"],
                "answer_key": "9",
                "class_level": "X",
                "row_num": 3,
                "sheet": "Pilihan Ganda",
            },
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200, f"Response: {res.status_code} - {res.json()}"
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 2
    assert "dilewati" not in data["message"]

    # Verify DB
    q1 = (
        db.query(Question)
        .filter_by(content="Berapakah 2 + 2?", owner_teacher_account_id=teacher.id)
        .first()
    )
    assert q1 is not None
    assert q1.type == QuestionType.PG
    assert q1.options == ["2", "3", "4", "5"]
    assert q1.answer_key == "4"

    q2 = (
        db.query(Question)
        .filter_by(content="Berapakah 3 x 3?", owner_teacher_account_id=teacher.id)
        .first()
    )
    assert q2 is not None


def test_import_questions_valid_is_batch(client: TestClient, api_test_data, db: Session):
    """TEST 2: Valid batch of IS questions -> imported successfully."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Ibu kota Indonesia adalah...",
                "answer_key": "Jakarta",
                "class_level": "XI",
                "row_num": 2,
                "sheet": "Isian Singkat",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1

    # Verify DB
    q = (
        db.query(Question)
        .filter_by(content="Ibu kota Indonesia adalah...", owner_teacher_account_id=teacher.id)
        .first()
    )
    assert q is not None
    assert q.type == QuestionType.IS
    assert q.options is None
    assert q.answer_key == "Jakarta"


def test_import_questions_valid_essay_manual_rubric(client: TestClient, api_test_data, db: Session):
    """TEST 3: Valid batch of Essay questions with manual rubric -> imported successfully."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Jelaskan cara kerja komputer!",
                "answer_key": "Input, proses, output...",
                "class_level": "XII",
                "ai_grading": False,
                "rubrics": [
                    {"criteria": "Penjelasan Input", "max_score": 50},
                    {"criteria": "Penjelasan Output", "max_score": 50},
                ],
                "row_num": 2,
                "sheet": "Essay",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1

    # Verify DB
    q = (
        db.query(Question)
        .filter_by(content="Jelaskan cara kerja komputer!", owner_teacher_account_id=teacher.id)
        .first()
    )
    assert q is not None
    assert q.type == QuestionType.ES
    assert q.ai_grading is False
    assert len(q.rubrics) == 2
    assert q.rubrics[0]["criteria"] == "Penjelasan Input"
    assert q.rubrics[0]["max_score"] == 50


def test_import_questions_valid_essay_ai_grading(client: TestClient, api_test_data, db: Session):
    """TEST 4: Valid batch of Essay questions with AI grading enabled -> imported successfully without manual rubrics."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Jelaskan definisi AI!",
                "answer_key": "Kecerdasan buatan...",
                "class_level": "XII",
                "ai_grading": True,
                "rubrics": [],
                "row_num": 2,
                "sheet": "Essay",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1

    # Verify DB
    q = (
        db.query(Question)
        .filter_by(content="Jelaskan definisi AI!", owner_teacher_account_id=teacher.id)
        .first()
    )
    assert q is not None
    assert q.type == QuestionType.ES
    assert q.ai_grading is True
    assert q.rubrics == []


def test_import_questions_invalid_type(client: TestClient, api_test_data, db: Session):
    """TEST 5: Invalid question type -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "INVALID_TYPE",
                "content": "Tipe salah",
                "answer_key": "kunci",
                "row_num": 2,
                "sheet": "PG",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "INVALID_QUESTION_TYPE"


def test_import_questions_pg_less_than_2_options(client: TestClient, api_test_data, db: Session):
    """TEST 6: PG with less than 2 options -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Opsi sedikit",
                "options": ["Hanya Satu"],
                "answer_key": "Hanya Satu",
                "row_num": 2,
                "sheet": "PG",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert "minimal 2 opsi" in res.json()["errors"][0]["message"]


def test_import_questions_pg_more_than_6_options(client: TestClient, api_test_data, db: Session):
    """TEST 7: PG with more than 6 options -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Opsi kebanyakan",
                "options": ["1", "2", "3", "4", "5", "6", "7"],
                "answer_key": "1",
                "row_num": 2,
                "sheet": "PG",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert "maksimal 6 opsi" in res.json()["errors"][0]["message"]


def test_import_questions_pg_option_gap(client: TestClient, api_test_data, db: Session):
    """TEST 8: PG option has a gap (A and B set, C empty, D set) -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Ada gap",
                "options": ["A", "B", "", "D"],
                "answer_key": "A",
                "row_num": 2,
                "sheet": "PG",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert "Opsi tidak boleh ada gap" in res.json()["errors"][0]["message"]


def test_import_questions_pg_invalid_answer_key(client: TestClient, api_test_data, db: Session):
    """TEST 9: PG answer key does not match any options -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Kunci salah",
                "options": ["A", "B"],
                "answer_key": "C",
                "row_num": 2,
                "sheet": "PG",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert "tidak cocok dengan opsi mana pun" in res.json()["errors"][0]["message"]


def test_import_questions_is_missing_answer_key(client: TestClient, api_test_data, db: Session):
    """TEST 10: IS missing answer key -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "IS Tanpa Kunci",
                "answer_key": "",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422, f"Response body: {res.json()}"
    assert res.json()["errors"][0]["code"] == "ANSWER_KEY_REQUIRED"


def test_import_questions_essay_missing_answer_key(client: TestClient, api_test_data, db: Session):
    """TEST 11: Essay missing answer key -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Essay Tanpa Kunci",
                "answer_key": "",
                "ai_grading": True,
                "row_num": 2,
                "sheet": "Essay",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "ANSWER_KEY_REQUIRED"


def test_import_questions_essay_no_rubric_manual(client: TestClient, api_test_data, db: Session):
    """TEST 12: Essay manual grading (AI=false) without manual rubrics -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Essay Tanpa Rubrik",
                "answer_key": "Model Jawaban",
                "ai_grading": False,
                "rubrics": [],
                "row_num": 2,
                "sheet": "Essay",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert "rubrik manual wajib diisi" in res.json()["errors"][0]["message"]


def test_import_questions_essay_invalid_max_score(client: TestClient, api_test_data, db: Session):
    """TEST 13: Essay manual grading (AI=false) with invalid rubric max score (0 or negative) -> HTTP 422, reject."""
    headers = api_test_data["headers_teacher_a"]

    # max_score = 0
    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Essay Rubrik 0",
                "answer_key": "Jawaban",
                "ai_grading": False,
                "rubrics": [{"criteria": "Kriteria A", "max_score": 0}],
                "row_num": 2,
                "sheet": "Essay",
            }
        ],
    }
    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert "harus angka positif" in res.json()["errors"][0]["message"]


def test_import_questions_duplicate_inside_xlsx(client: TestClient, api_test_data, db: Session):
    """TEST 14: Duplicate content + type in same XLSX batch -> HTTP 422, reject whole batch."""
    headers = api_test_data["headers_teacher_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Sama",
                "answer_key": "Kunci A",
                "row_num": 2,
                "sheet": "IS",
            },
            {
                "type": "IS",
                "content": " Soal Sama  ",
                "answer_key": "Kunci B",
                "row_num": 3,
                "sheet": "IS",
            },
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "DUPLICATE_IN_FILE"


def test_import_questions_existing_db_duplicate_skipped(
    client: TestClient, api_test_data, db: Session
):
    """TEST 15: Existing DB duplicate owned by same teacher -> skipped (warning), not fail."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    # Pre-create a question in DB
    existing = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.IS,
        content="Soal Eksis",
        answer_key="Kunci Eksis",
        rubrics=[],
        subject="Matematika",
    )
    db.add(existing)
    db.commit()

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Eksis",
                "answer_key": "Lain",
                "row_num": 2,
                "sheet": "IS",
            },
            {
                "type": "IS",
                "content": "Soal Baru",
                "answer_key": "Baru",
                "row_num": 3,
                "sheet": "IS",
            },
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["row"] == 2
    assert "dilewati karena sudah ada" in data["message"]


def test_import_questions_mixed_valid_invalid_zero_persisted(
    client: TestClient, api_test_data, db: Session
):
    """TEST 16: Mixed valid and invalid rows -> HTTP 422, zero rows persisted (atomicity)."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Valid Sekali",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            },
            {
                "type": "PG",
                "content": "Soal Invalid Opsi Gap",
                "options": ["A", "", "C"],
                "answer_key": "A",
                "row_num": 3,
                "sheet": "PG",
            },
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422

    # Verify that valid question was NOT created
    q = (
        db.query(Question)
        .filter_by(content="Soal Valid Sekali", owner_teacher_account_id=teacher.id)
        .first()
    )
    assert q is None


def test_import_questions_persistence_failure_rollback(
    client: TestClient, api_test_data, db: Session, monkeypatch
):
    """TEST 17: Database persistence failure -> rollback -> zero created."""
    headers = api_test_data["headers_teacher_a"]

    def mock_flush(*args, **kwargs):
        raise Exception("DB write failed!")

    monkeypatch.setattr(db, "flush", mock_flush)

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Trigger Fail",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    # Use a TestClient with raise_server_exceptions=False to test actual HTTP response serialization
    from fastapi.testclient import TestClient

    from main import app as fastapi_app

    safe_client = TestClient(fastapi_app, raise_server_exceptions=False)

    res = safe_client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 500
    # Verify that the internal error details are not exposed to the client
    assert "DB write failed" not in res.text
    assert "traceback" not in res.text
    assert "select " not in res.text.lower()
    assert "insert " not in res.text.lower()


def test_import_questions_teacher_ownership_jwt(client: TestClient, api_test_data, db: Session):
    """TEST 18: Teacher A imports -> owner_teacher_account_id is automatically set to Teacher A."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Milik Budi",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    q = db.query(Question).filter_by(content="Soal Milik Budi").first()
    assert q is not None
    assert q.owner_teacher_account_id == teacher.id


def test_import_questions_teacher_id_ignored(client: TestClient, api_test_data, db: Session):
    """TEST 19: Payload containing extra teacher_id field is ignored / not trusted (uses JWT instead)."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Abaikan ID",
                "answer_key": "Kunci",
                "teacher_id": 9999,  # attacker trying to hijack ownership
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    q = db.query(Question).filter_by(content="Soal Abaikan ID").first()
    assert q is not None
    assert q.owner_teacher_account_id == teacher.id  # still assigned to logged-in teacher, not 9999


def test_import_questions_cross_tenant_isolation(client: TestClient, api_test_data, db: Session):
    """TEST 20: Cross-tenant duplicate checks do not check other schools' teachers' questions."""
    headers_teacher_a = api_test_data["headers_teacher_a"]
    teacher_a = api_test_data["teacher_math_a"]
    teacher_bio_a = api_test_data["teacher_bio_a"]

    # Pre-create duplicate question for teacher bio A
    existing_other_teacher = Question(
        owner_teacher_account_id=teacher_bio_a.id,
        type=QuestionType.IS,
        content="Soal Lintas Guru",
        answer_key="Kunci Lain",
        rubrics=[],
        subject="Biologi",
    )
    db.add(existing_other_teacher)
    db.commit()

    # Teacher A imports same question content -> should NOT skip, because it's a different teacher
    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Lintas Guru",
                "answer_key": "Kunci Kita",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers_teacher_a)
    assert res.status_code == 200
    data = res.json()
    assert data["imported_count"] == 1
    assert len(data["skipped"]) == 0  # not skipped!


def test_import_questions_no_subject_created(client: TestClient, api_test_data, db: Session):
    """TEST 21: Importing question with a new subject label does NOT create any Subject record in database."""
    headers = api_test_data["headers_teacher_a"]
    school = api_test_data["school_a"]

    # Count subjects before
    count_before = db.query(Subject).filter_by(school_id=school.id).count()

    payload = {
        "subject": "Subjek Baru Aneh",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Subjek Baru",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    # Count subjects after
    count_after = db.query(Subject).filter_by(school_id=school.id).count()
    assert count_before == count_after


def test_import_questions_no_class_created(client: TestClient, api_test_data, db: Session):
    """TEST 22: Importing question with class_level does NOT create any ClassEntity record in database."""
    headers = api_test_data["headers_teacher_a"]
    school = api_test_data["school_a"]

    count_before = db.query(ClassEntity).filter_by(school_id=school.id).count()

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Kelas Baru",
                "answer_key": "Kunci",
                "class_level": "Kelas_Aneh_123",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    count_after = db.query(ClassEntity).filter_by(school_id=school.id).count()
    assert count_before == count_after


def test_import_questions_no_teacher_subject_created(
    client: TestClient, api_test_data, db: Session
):
    """TEST 23: Importing does NOT create any TeacherSubject relationship."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    count_before = db.query(TeacherSubject).filter_by(teacher_id=teacher.id).count()

    payload = {
        "subject": "Matematika Baru",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Latihan",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    count_after = db.query(TeacherSubject).filter_by(teacher_id=teacher.id).count()
    assert count_before == count_after


def test_import_questions_no_class_subject_created(client: TestClient, api_test_data, db: Session):
    """TEST 24: Importing does NOT create any ClassSubject relationship."""
    headers = api_test_data["headers_teacher_a"]

    count_before = db.query(ClassSubject).count()

    payload = {
        "subject": "Matematika Baru",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Kelas Baru Latihan",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    count_after = db.query(ClassSubject).count()
    assert count_before == count_after


def test_import_questions_package_not_modified(client: TestClient, api_test_data, db: Session):
    """TEST 25: Question Packages are not modified during import."""
    headers = api_test_data["headers_teacher_a"]

    # Count packages
    count_before = db.query(QuestionPackage).count()

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Paket Aman",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    count_after = db.query(QuestionPackage).count()
    assert count_before == count_after


# ============================================================
# MANDATORY ATOMIC TEST
# ============================================================


def test_import_questions_atomic_50_rows(client: TestClient, api_test_data, db: Session):
    """TEST 26 (MANDATORY ATOMIC TEST): 50 rows (49 valid, 1 invalid) -> Expected: HTTP 422, 0 Question records created."""
    headers = api_test_data["headers_teacher_a"]
    teacher = api_test_data["teacher_math_a"]

    # Questions count before
    count_before = db.query(Question).filter_by(owner_teacher_account_id=teacher.id).count()

    rows_list = []
    # 49 valid rows
    for i in range(49):
        rows_list.append(
            {
                "type": "IS",
                "content": f"Soal Atomic ke-{i}",
                "answer_key": f"Kunci-{i}",
                "row_num": i + 2,
                "sheet": "IS",
            }
        )
    # 1 invalid row (invalid type)
    rows_list.append(
        {
            "type": "INVALID_TYPE",
            "content": "Soal Atomic ke-49 Invalid Tipe",
            "answer_key": "Kunci-49",
            "row_num": 51,
            "sheet": "IS",
        }
    )

    payload = {"subject": "Matematika", "rows": rows_list}

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 422

    # Verify that absolutely zero new questions were created
    count_after = db.query(Question).filter_by(owner_teacher_account_id=teacher.id).count()
    assert count_before == count_after


# ============================================================
# MANDATORY SNAPSHOT TEST
# ============================================================


def test_import_questions_examsnapshot_not_modified(client: TestClient, api_test_data, db: Session):
    """TEST 27 (MANDATORY SNAPSHOT TEST): Creating/importing questions does NOT mutate any existing ExamSnapshot."""
    headers = api_test_data["headers_teacher_a"]
    school = api_test_data["school_a"]

    from datetime import datetime, timedelta, timezone

    from app.models.academic.exam_schedule import ExamSchedule

    # Create parent entities to satisfy FK constraints
    subject_entity = Subject(
        school_id=school.id, code="MATH-SNAP", name="Matematika Snapshot", is_active=True
    )
    db.add(subject_entity)
    db.flush()

    class_entity = ClassEntity(
        school_id=school.id,
        academic_year_id=api_test_data["year_2025"].id,
        name="X-MATH-SNAP",
        grade_level="10",
        is_active=True,
    )
    db.add(class_entity)
    db.flush()

    pkg = QuestionPackage(
        owner_teacher_account_id=api_test_data["teacher_math_a"].id,
        school_id=school.id,
        name="Paket Uji Snapshot",
        class_level="X",
        subject="Matematika",
        status="READY",
        target_counts={"IS": 1},
    )
    db.add(pkg)
    db.flush()

    schedule = ExamSchedule(
        school_id=school.id,
        academic_year_id=api_test_data["year_2025"].id,
        academic_semester_id=api_test_data["sem_ganjil"].id,
        class_id=class_entity.id,
        subject_id=subject_entity.id,
        teacher_id=api_test_data["teacher_math_a"].id,
        title="Ujian Snapshot",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=120,
        status="DRAFT",
    )
    db.add(schedule)
    db.flush()

    # Pre-create an ExamSnapshot referencing schedule and pkg
    snapshot = ExamSnapshot(
        public_id=uuid.uuid4(),
        school_id=school.id,
        exam_schedule_id=schedule.id,
        question_package_id=pkg.id,
        teacher_id=api_test_data["teacher_math_a"].id,
        class_id=class_entity.id,
        subject_id=subject_entity.id,
        academic_year_id=api_test_data["year_2025"].id,
        academic_semester_id=api_test_data["sem_ganjil"].id,
        snapshot_data={"original": "data", "package_name": "Paket A"},
        total_questions=10,
        total_points=100,
        duration_minutes=90,
        is_locked=True,
    )
    db.add(snapshot)
    db.commit()

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Penguji Snapshot",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
    assert res.status_code == 200

    # Assert that snapshot data remains exactly unchanged
    db.refresh(snapshot)
    assert snapshot.snapshot_data == {"original": "data", "package_name": "Paket A"}
    assert snapshot.is_locked is True


# ============================================================
# MANDATORY OWNERSHIP TEST
# ============================================================


def test_import_questions_ownership_test(client: TestClient, api_test_data, db: Session):
    """TEST 28 (MANDATORY OWNERSHIP TEST): Teacher A imports questions. Assert: all new questions have owner == Teacher A, never Teacher B."""
    headers_teacher_a = api_test_data["headers_teacher_a"]
    teacher_a = api_test_data["teacher_math_a"]
    teacher_bio_a = api_test_data["teacher_bio_a"]

    payload = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal Uji Kepemilikan",
                "answer_key": "Kunci",
                "row_num": 2,
                "sheet": "IS",
            }
        ],
    }

    res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers_teacher_a)
    assert res.status_code == 200

    q = db.query(Question).filter_by(content="Soal Uji Kepemilikan").first()
    assert q is not None
    assert q.owner_teacher_account_id == teacher_a.id
    assert q.owner_teacher_account_id != teacher_bio_a.id


def test_import_questions_hardened_validation(client: TestClient, api_test_data, db: Session):
    """TEST 29: Test hardened rubric and AI grading validation rules."""
    headers = api_test_data["headers_teacher_a"]

    # 1. Essay manual rubric 1 -> valid (200)
    payload_es_1 = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Soal Essay Rubrik 1",
                "answer_key": "Kunci",
                "ai_grading": False,
                "rubrics": [{"criteria": "Kriteria 1", "max_score": 5}],
                "row_num": 2,
                "sheet": "Essay",
            }
        ],
    }
    res = client.post("/api/v1/teacher/questions/import", json=payload_es_1, headers=headers)
    assert res.status_code == 200
    q = db.query(Question).filter_by(content="Soal Essay Rubrik 1").first()
    assert q is not None

    # 2. Essay manual rubric 5 -> valid (200)
    payload_es_5 = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Soal Essay Rubrik 5",
                "answer_key": "Kunci",
                "ai_grading": False,
                "rubrics": [
                    {"criteria": "Kriteria 1", "max_score": 2},
                    {"criteria": "Kriteria 2", "max_score": 2},
                    {"criteria": "Kriteria 3", "max_score": 2},
                    {"criteria": "Kriteria 4", "max_score": 2},
                    {"criteria": "Kriteria 5", "max_score": 2},
                ],
                "row_num": 3,
                "sheet": "Essay",
            }
        ],
    }
    res = client.post("/api/v1/teacher/questions/import", json=payload_es_5, headers=headers)
    assert res.status_code == 200
    q = db.query(Question).filter_by(content="Soal Essay Rubrik 5").first()
    assert q is not None

    # Helper to check failed validation doesn't save to DB
    def assert_failed_payload(payload, content_to_check):
        count_before = db.query(Question).count()
        res = client.post("/api/v1/teacher/questions/import", json=payload, headers=headers)
        assert res.status_code == 422
        count_after = db.query(Question).count()
        assert count_before == count_after
        q = db.query(Question).filter_by(content=content_to_check).first()
        assert q is None

    # 3. Essay manual rubric 6 -> 422
    payload_es_6 = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Soal Essay Rubrik 6",
                "answer_key": "Kunci",
                "ai_grading": False,
                "rubrics": [
                    {"criteria": "Kriteria 1", "max_score": 1},
                    {"criteria": "Kriteria 2", "max_score": 1},
                    {"criteria": "Kriteria 3", "max_score": 1},
                    {"criteria": "Kriteria 4", "max_score": 1},
                    {"criteria": "Kriteria 5", "max_score": 1},
                    {"criteria": "Kriteria 6", "max_score": 1},
                ],
                "row_num": 4,
                "sheet": "Essay",
            }
        ],
    }
    assert_failed_payload(payload_es_6, "Soal Essay Rubrik 6")

    # 4. Essay manual rubric 0 -> 422
    payload_es_0 = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Soal Essay Rubrik 0",
                "answer_key": "Kunci",
                "ai_grading": False,
                "rubrics": [],
                "row_num": 5,
                "sheet": "Essay",
            }
        ],
    }
    assert_failed_payload(payload_es_0, "Soal Essay Rubrik 0")

    # 5. Essay AI=true + empty rubric -> valid (200)
    payload_es_ai_empty = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Soal Essay AI Empty Rubric",
                "answer_key": "Kunci",
                "ai_grading": True,
                "rubrics": [],
                "row_num": 6,
                "sheet": "Essay",
            }
        ],
    }
    res = client.post("/api/v1/teacher/questions/import", json=payload_es_ai_empty, headers=headers)
    assert res.status_code == 200
    q = db.query(Question).filter_by(content="Soal Essay AI Empty Rubric").first()
    assert q is not None

    # 6. Essay AI=true + malformed non-empty rubric -> 422
    payload_es_ai_malformed = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "ES",
                "content": "Soal Essay AI NonEmpty Rubric",
                "answer_key": "Kunci",
                "ai_grading": True,
                "rubrics": [{"criteria": "Kriteria", "max_score": 5}],
                "row_num": 7,
                "sheet": "Essay",
            }
        ],
    }
    assert_failed_payload(payload_es_ai_malformed, "Soal Essay AI NonEmpty Rubric")

    # 7. PG + rubric -> 422
    payload_pg_rubric = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Soal PG Rubric Fail",
                "options": ["A", "B"],
                "answer_key": "A",
                "rubrics": [{"criteria": "Kriteria", "max_score": 5}],
                "row_num": 8,
                "sheet": "PG",
            }
        ],
    }
    assert_failed_payload(payload_pg_rubric, "Soal PG Rubric Fail")

    # 8. IS + rubric -> 422
    payload_is_rubric = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal IS Rubric Fail",
                "answer_key": "Kunci",
                "rubrics": [{"criteria": "Kriteria", "max_score": 5}],
                "row_num": 9,
                "sheet": "IS",
            }
        ],
    }
    assert_failed_payload(payload_is_rubric, "Soal IS Rubric Fail")

    # 9. PG + ai_grading=true -> 422
    payload_pg_ai = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "PG",
                "content": "Soal PG AI Fail",
                "options": ["A", "B"],
                "answer_key": "A",
                "ai_grading": True,
                "row_num": 10,
                "sheet": "PG",
            }
        ],
    }
    assert_failed_payload(payload_pg_ai, "Soal PG AI Fail")

    # 10. IS + ai_grading=true -> 422
    payload_is_ai = {
        "subject": "Matematika",
        "rows": [
            {
                "type": "IS",
                "content": "Soal IS AI Fail",
                "answer_key": "Kunci",
                "ai_grading": True,
                "row_num": 11,
                "sheet": "IS",
            }
        ],
    }
    assert_failed_payload(payload_is_ai, "Soal IS AI Fail")
