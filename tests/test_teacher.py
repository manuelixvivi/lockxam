import uuid
from datetime import datetime, timezone

import pytest

from app.exceptions import BusinessException
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.question import Question
from app.services.teacher.question_package_service import QuestionPackageService


def create_another_school_and_teacher(db, npsn: str) -> tuple[School, AuthAccount]:
    school = School(
        public_id=uuid.uuid4(),
        npsn=npsn,
        code=npsn,
        name=f"School {npsn}",
        school_level_id=1,
        status="ACTIVE",
    )
    db.add(school)
    db.flush()

    teacher = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school.id,
        username=f"teacher_{npsn}",
        password_hash="hashed_password",
        role="TEACHER",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(teacher)
    db.flush()
    return school, teacher


def test_create_package_service(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS IPA",
        class_level="X",
        target_counts={"PG": 2, "ES": 1},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="IPA",
    )
    assert package.id is not None
    assert package.name == "UTS IPA"
    assert package.status == PackageStatus.INCOMPLETE


def test_add_question_service_success(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Biologi",
        class_level="X",
        target_counts={"PG": 1},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Biologi",
    )

    q = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Apa itu sel?",
        options=["A", "B"],
        answer_key="A",
        rubrics=[{"ku": "ku_1", "weight": 100}],
    )
    db.add(q)
    db.flush()

    updated_package = QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )

    assert updated_package.status == PackageStatus.READY
    assert len(updated_package.items) == 1
    assert updated_package.items[0].canonical_order == 1


def test_add_question_ownership_error(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Biologi",
        class_level="X",
        target_counts={"PG": 1},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Biologi",
    )

    _, another_teacher = create_another_school_and_teacher(db, "99990001")

    # Create question owned by another teacher
    q = Question(
        owner_teacher_account_id=another_teacher.id,
        type=QuestionType.PG,
        content="Apa itu sel?",
        options=["A", "B"],
        answer_key="A",
        rubrics=[{"ku": "ku_1", "weight": 100}],
    )
    db.add(q)
    db.flush()

    with pytest.raises(BusinessException) as exc_info:
        QuestionPackageService.add_question_to_package(
            db=db,
            package_id=package.id,
            question_id=q.id,
            teacher_account_id=teacher.id,
            school_id=test_school.id,
        )
    assert "Akses ditolak" in str(exc_info.value)


def test_add_question_tenant_cross_school_error(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Biologi",
        class_level="X",
        target_counts={"PG": 1},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Biologi",
    )

    # Question is owned by teacher, but school_id of package does not match school_id of teacher
    another_school, _ = create_another_school_and_teacher(db, "99990002")

    q = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Apa itu sel?",
        options=["A", "B"],
        answer_key="A",
        rubrics=[{"ku": "ku_1", "weight": 100}],
    )
    db.add(q)
    db.flush()

    with pytest.raises(BusinessException) as exc_info:
        QuestionPackageService.add_question_to_package(
            db=db,
            package_id=package.id,
            question_id=q.id,
            teacher_account_id=teacher.id,
            school_id=another_school.id,
        )
    assert "Akses ditolak" in str(exc_info.value)


def test_add_question_overflow_error(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Biologi",
        class_level="X",
        target_counts={"PG": 1},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Biologi",
    )

    q1 = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Soal 1",
        options=["A", "B"],
        answer_key="A",
        rubrics=[],
    )
    q2 = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Soal 2",
        options=["A", "B"],
        answer_key="B",
        rubrics=[],
    )
    db.add_all([q1, q2])
    db.flush()

    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q1.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )

    with pytest.raises(BusinessException) as exc_info:
        QuestionPackageService.add_question_to_package(
            db=db,
            package_id=package.id,
            question_id=q2.id,
            teacher_account_id=teacher.id,
            school_id=test_school.id,
        )
    assert "QUESTION_TARGET_EXCEEDED" in str(exc_info.value)


def test_reorder_questions_collision_safe(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Fisika",
        class_level="X",
        target_counts={"PG": 2},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Fisika",
    )

    q1 = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Soal A",
        options=["A"],
        answer_key="A",
        rubrics=[],
    )
    q2 = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Soal B",
        options=["B"],
        answer_key="B",
        rubrics=[],
    )
    db.add_all([q1, q2])
    db.flush()

    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q1.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )
    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q2.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )

    # Reorder swap q1 (1->2) and q2 (2->1)
    reordered = QuestionPackageService.reorder_questions(
        db=db,
        package_id=package.id,
        order_map={q1.id: 2, q2.id: 1},
        teacher_account_id=teacher.id,
    )

    items = sorted(reordered.items, key=lambda x: x.canonical_order)
    assert items[0].question_id == q2.id
    assert items[0].canonical_order == 1
    assert items[1].question_id == q1.id
    assert items[1].canonical_order == 2


def test_reorder_mismatch_keyset_error(db, test_teacher, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Fisika",
        class_level="X",
        target_counts={"PG": 2},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Fisika",
    )

    q1 = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Soal A",
        options=["A"],
        answer_key="A",
        rubrics=[],
    )
    q2 = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Soal B",
        options=["B"],
        answer_key="B",
        rubrics=[],
    )
    db.add_all([q1, q2])
    db.flush()

    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q1.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )
    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q2.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )

    # Attempt to reorder with a non-existent question ID in keys
    with pytest.raises(BusinessException) as exc_info:
        QuestionPackageService.reorder_questions(
            db=db,
            package_id=package.id,
            order_map={q1.id: 1, 99999: 2},
            teacher_account_id=teacher.id,
        )
    assert "REORDER_INVALID_QUESTION_SET" in str(exc_info.value)


def test_api_create_package_success(client, test_teacher, db, test_school):
    # Ensure school is ACTIVE so mutating requests are allowed
    test_school.status = "ACTIVE"
    db.add(test_school)
    db.commit()

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    token = login_res.json()["access_token"]

    res = client.post(
        "/api/v1/teacher/packages",
        json={
            "name": "UTS Kimia",
            "class_level": "XI",
            "subject": "Kimia",
            "target_counts": {"PG": 20},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "UTS Kimia"
    assert data["status"] == "INCOMPLETE"


def test_api_get_snapshot_payload_internal_only(client, test_teacher, db, test_school):
    teacher = test_teacher["account"]
    package = QuestionPackageService.create_package(
        db=db,
        name="UTS Fisika",
        class_level="X",
        target_counts={"PG": 1},
        teacher_account_id=teacher.id,
        school_id=test_school.id,
        subject="Fisika",
    )

    q = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG,
        content="Test Question content",
        options=["A"],
        answer_key="A",
        rubrics=[],
    )
    db.add(q)
    db.flush()

    QuestionPackageService.add_question_to_package(
        db=db,
        package_id=package.id,
        question_id=q.id,
        teacher_account_id=teacher.id,
        school_id=test_school.id,
    )

    # 1. Accessing without internal token -> should fail with 403
    fail_res = client.get(f"/api/v1/teacher/packages/{package.id}/snapshot-payload")
    assert fail_res.status_code == 403

    # 2. Accessing with correct internal token -> should succeed
    success_res = client.get(
        f"/api/v1/teacher/packages/{package.id}/snapshot-payload",
        headers={"X-Internal-Service-Token": "equigrade-internal-secret-token"},
    )
    assert success_res.status_code == 200
    data = success_res.json()
    assert data["package_id"] == package.id
    assert data["name"] == "UTS Fisika"
    assert len(data["questions"]) == 1
    assert data["questions"][0]["id"] == q.id
    assert data["questions"][0]["canonical_order"] == 1
    assert (
        "answer_key" in data["questions"][0]
    )  # Verification that answer_key is included in snapshot payload DTO
