from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_admin
from app.exceptions.base import BusinessException
from app.schemas.common.import_validation import ImportResponse
from app.schemas.academic.admin_academic import (
    ClassCreateRequest,
    ClassResponse,
    ClassSubjectAssignRequest,
    ClassSubjectResponse,
    ClassSubjectTeacherAssignRequest,
    ClassSubjectTeacherResponse,
    ClassUpdateRequest,
    StudentEnrollmentRequest,
    StudentEnrollmentResponse,
    TeacherCandidateResponse,
    StudentBulkEnrollRequest,
    StudentBulkRemoveRequest,
    ClassSubjectBulkAssignRequest,
    ClassSubjectBulkRemoveRequest,
    ClassFullImportRequest,
)
from app.services.academic.class_service import ClassService
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.subject_service import SubjectService
from app.services.security.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/admin/classes", tags=["School Admin — Classes & Enrollments"])


def _get_school_id(current_user: dict) -> int:
    school_id = current_user.get("school_id")
    if not school_id:
        raise BusinessException(
            "Akun admin tidak terikat dengan sekolah manapun.", status_code=400
        )
    return school_id


# ── 1. Class Master Endpoints ──

@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    data: ClassCreateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    new_class = ClassService.create_class(
        db=db,
        school_id=school_id,
        academic_year_id=data.academic_year_id,
        name=data.name,
        grade_level=data.grade_level,
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="CLASS",
        action_name="CREATE_CLASS",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"class_id": new_class.id, "name": new_class.name},
    )
    db.commit()

    return ClassResponse(
        id=new_class.id,
        public_id=new_class.public_id,
        school_id=new_class.school_id,
        academic_year_id=new_class.academic_year_id,
        name=new_class.name,
        grade_level=new_class.grade_level,
        is_active=new_class.is_active,
        student_count=0,
        subject_count=0,
        created_at=new_class.created_at,
        updated_at=new_class.updated_at,
    )


@router.get("", response_model=list[ClassResponse])
def list_classes(
    academic_year_id: int | None = None,
    is_active: bool | None = True,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.academic.student_enrollment_repository import student_enrollment_repository
    from app.repositories.academic.class_subject_repository import class_subject_repository
    from app.repositories.academic.academic_year_repository import academic_year_repository

    if academic_year_id is None:
        active_year = academic_year_repository.get_active_year(db, school_id)
        if active_year:
            academic_year_id = active_year.id

    if academic_year_id is not None:
        classes = class_repository.list_by_academic_year(
            db, school_id=school_id, academic_year_id=academic_year_id, is_active=is_active
        )
    else:
        classes = class_repository.list_by_school(db, school_id=school_id)
        if is_active is not None:
            classes = [c for c in classes if c.is_active == is_active]

    res = []
    for c in classes:
        students = student_enrollment_repository.list_by_class(db, c.id, status=["ACTIVE", "COMPLETED", "TRANSFERRED"])
        subjects = class_subject_repository.list_by_class(db, c.id)
        res.append(
            ClassResponse(
                id=c.id,
                public_id=c.public_id,
                school_id=c.school_id,
                academic_year_id=c.academic_year_id,
                name=c.name,
                grade_level=c.grade_level,
                is_active=c.is_active,
                student_count=len(students),
                subject_count=len(subjects),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return res


@router.get("/{public_id}", response_model=ClassResponse)
def get_class(
    public_id: UUID,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.academic.student_enrollment_repository import student_enrollment_repository
    from app.repositories.academic.class_subject_repository import class_subject_repository

    cls = class_repository.get_by_public_id(db, public_id)
    if not cls or cls.school_id != school_id:
        raise BusinessException("Kelas tidak ditemukan.", status_code=404)

    students = student_enrollment_repository.list_by_class(db, cls.id, status=["ACTIVE", "COMPLETED", "TRANSFERRED"])
    subjects = class_subject_repository.list_by_class(db, cls.id)

    return ClassResponse(
        id=cls.id,
        public_id=cls.public_id,
        school_id=cls.school_id,
        academic_year_id=cls.academic_year_id,
        name=cls.name,
        grade_level=cls.grade_level,
        is_active=cls.is_active,
        student_count=len(students),
        subject_count=len(subjects),
        created_at=cls.created_at,
        updated_at=cls.updated_at,
    )


@router.put("/{public_id}", response_model=ClassResponse)
def update_class(
    public_id: UUID,
    data: ClassUpdateRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    cls = ClassService.update_class(
        db=db,
        school_id=school_id,
        public_id=public_id,
        name=data.name,
        grade_level=data.grade_level,
        is_active=data.is_active,
    )

    from app.repositories.academic.student_enrollment_repository import student_enrollment_repository
    from app.repositories.academic.class_subject_repository import class_subject_repository
    students = student_enrollment_repository.list_by_class(db, cls.id, status="ACTIVE")
    subjects = class_subject_repository.list_by_class(db, cls.id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="CLASS",
        action_name="UPDATE_CLASS",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"class_id": cls.id, "name": cls.name},
    )
    db.commit()

    return ClassResponse(
        id=cls.id,
        public_id=cls.public_id,
        school_id=cls.school_id,
        academic_year_id=cls.academic_year_id,
        name=cls.name,
        grade_level=cls.grade_level,
        is_active=cls.is_active,
        student_count=len(students),
        subject_count=len(subjects),
        created_at=cls.created_at,
        updated_at=cls.updated_at,
    )


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    public_id: UUID,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    ClassService.delete_class(db=db, school_id=school_id, public_id=public_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="CLASS",
        action_name="DELETE_CLASS",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"class_public_id": str(public_id)},
    )
    db.commit()


# ── 2. Student Enrollment & Mutation Endpoints ──

@router.post("/{class_id}/students", response_model=StudentEnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_student(
    class_id: int,
    data: StudentEnrollmentRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    enrollment = ClassStructureService.enroll_student_to_class(
        db=db, school_id=school_id, student_id=data.student_id, class_id=class_id
    )

    from app.repositories.security.auth_repository import auth_repository
    from app.repositories.academic.class_repository import class_repository
    student = auth_repository.get_by_id(db, data.student_id)
    cls = class_repository.get_by_id(db, class_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ENROLLMENT",
        action_name="ENROLL_STUDENT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"student_id": data.student_id, "class_id": class_id},
    )
    db.commit()

    return StudentEnrollmentResponse(
        id=enrollment.id,
        public_id=enrollment.public_id,
        school_id=enrollment.school_id,
        student_id=enrollment.student_id,
        class_id=enrollment.class_id,
        academic_year_id=enrollment.academic_year_id,
        status=enrollment.status,
        start_date=enrollment.start_date,
        end_date=enrollment.end_date,
        student_name=student.name if student else None,
        student_username=student.username if student else None,
        nisn=student.nisn if student else None,
        nis=student.nis if student else None,
        class_name=cls.name if cls else None,
    )


@router.get("/{class_id}/students", response_model=list[StudentEnrollmentResponse])
def list_enrolled_students(
    class_id: int,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.security.auth_repository import auth_repository

    cls = class_repository.get_by_id(db, class_id)
    if not cls or cls.school_id != school_id:
        raise BusinessException("Kelas tidak ditemukan.", status_code=404)

    enrollments = ClassStructureService.list_students_in_class(db, class_id)
    res = []
    for e in enrollments:
        student = auth_repository.get_by_id(db, e.student_id)
        res.append(
            StudentEnrollmentResponse(
                id=e.id,
                public_id=e.public_id,
                school_id=e.school_id,
                student_id=e.student_id,
                class_id=e.class_id,
                academic_year_id=e.academic_year_id,
                status=e.status,
                start_date=e.start_date,
                end_date=e.end_date,
                student_name=student.name if student else None,
                student_username=student.username if student else None,
                nisn=student.nisn if student else None,
                nis=student.nis if student else None,
                class_name=cls.name,
            )
        )
    return res


@router.delete("/{class_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_student_from_class(
    class_id: int,
    student_id: int,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    ClassStructureService.remove_student_from_class(
        db=db, school_id=school_id, student_id=student_id, class_id=class_id
    )

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="ENROLLMENT",
        action_name="REMOVE_STUDENT_FROM_CLASS",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"student_id": student_id, "class_id": class_id},
    )
    db.commit()


# ── 3. Class ↔ Subject & Teacher Assignments ──

@router.post("/{class_id}/subjects", response_model=ClassSubjectResponse, status_code=status.HTTP_201_CREATED)
def assign_subject_to_class(
    class_id: int,
    data: ClassSubjectAssignRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    cs = ClassStructureService.assign_subject_to_class(
        db=db, school_id=school_id, class_id=class_id, subject_id=data.subject_id
    )

    from app.repositories.academic.subject_repository import subject_repository
    subj = subject_repository.get_by_id(db, data.subject_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="CLASS_SUBJECT",
        action_name="ASSIGN_SUBJECT_TO_CLASS",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"class_id": class_id, "subject_id": data.subject_id},
    )
    db.commit()

    return ClassSubjectResponse(
        id=cs.id,
        school_id=cs.school_id,
        class_id=cs.class_id,
        subject_id=cs.subject_id,
        created_at=cs.created_at,
        subject_code=subj.code if subj else None,
        subject_name=subj.name if subj else None,
    )


@router.get("/{class_id}/subjects", response_model=list[ClassSubjectResponse])
def list_class_subjects(
    class_id: int,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    from app.repositories.academic.class_repository import class_repository
    from app.repositories.academic.class_subject_repository import class_subject_repository
    from app.repositories.academic.class_subject_teacher_repository import class_subject_teacher_repository
    from app.repositories.academic.subject_repository import subject_repository
    from app.repositories.security.auth_repository import auth_repository

    cls = class_repository.get_by_id(db, class_id)
    if not cls or cls.school_id != school_id:
        raise BusinessException("Kelas tidak ditemukan.", status_code=404)

    class_subjects = class_subject_repository.list_by_class(db, class_id)
    res = []
    for cs in class_subjects:
        subj = subject_repository.get_by_id(db, cs.subject_id)
        cst = class_subject_teacher_repository.get_by_class_and_subject(db, class_id, cs.subject_id)
        teacher = auth_repository.get_by_id(db, cst.teacher_id) if cst else None

        res.append(
            ClassSubjectResponse(
                id=cs.id,
                school_id=cs.school_id,
                class_id=cs.class_id,
                subject_id=cs.subject_id,
                created_at=cs.created_at,
                subject_code=subj.code if subj else None,
                subject_name=subj.name if subj else None,
                teacher_id=teacher.id if teacher else None,
                teacher_name=teacher.name if teacher else None,
            )
        )
    return res


@router.post("/{class_id}/subjects/{subject_id}/teachers", response_model=ClassSubjectTeacherResponse)
def assign_teacher_to_class_subject(
    class_id: int,
    subject_id: int,
    data: ClassSubjectTeacherAssignRequest,
    request: Request,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    user_id = int(current_user["sub"])

    cst = ClassStructureService.assign_teacher_to_class_subject(
        db=db,
        school_id=school_id,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=data.teacher_id,
    )

    from app.repositories.security.auth_repository import auth_repository
    from app.repositories.academic.subject_repository import subject_repository
    from app.repositories.academic.class_repository import class_repository

    teacher = auth_repository.get_by_id(db, data.teacher_id)
    subj = subject_repository.get_by_id(db, subject_id)
    cls = class_repository.get_by_id(db, class_id)

    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="CLASS_TEACHER",
        action_name="ASSIGN_TEACHER_TO_CLASS_SUBJECT",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"class_id": class_id, "subject_id": subject_id, "teacher_id": data.teacher_id},
    )
    db.commit()

    return ClassSubjectTeacherResponse(
        id=cst.id,
        school_id=cst.school_id,
        class_id=cst.class_id,
        subject_id=cst.subject_id,
        teacher_id=cst.teacher_id,
        created_at=cst.created_at,
        teacher_name=teacher.name if teacher else None,
        teacher_username=teacher.username if teacher else None,
        teacher_nip=teacher.nip if teacher else None,
        subject_name=subj.name if subj else None,
        class_name=cls.name if cls else None,
    )


# ── 4. Candidate Teacher Endpoint (Core UX Requirement) ──

@router.get("/{class_id}/subjects/{subject_id}/teacher-candidates", response_model=list[TeacherCandidateResponse])
def get_teacher_candidates(
    class_id: int,
    subject_id: int,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """
    Returns candidate teachers eligible to teach this subject in this class.
    Enforces:
      1. teacher.school_id == admin.school_id (Tenant Isolation)
      2. teacher_subject.subject_id == requested_subject_id (Competency Verification)
      3. teacher.is_active == True (Active Status)
    """
    school_id = _get_school_id(current_user)
    from app.repositories.academic.class_repository import class_repository
    cls = class_repository.get_by_id(db, class_id)
    if not cls or cls.school_id != school_id:
        raise BusinessException("Kelas tidak ditemukan.", status_code=404)

    teachers = SubjectService.list_qualified_teachers_for_subject(
        db=db, school_id=school_id, subject_id=subject_id
    )

    return [
        TeacherCandidateResponse(
            teacher_id=t.id,
            public_id=t.public_id,
            name=t.name or t.username,
            username=t.username,
            nip=t.nip,
            is_active=t.is_active,
            status="ACTIVE" if t.is_active else "INACTIVE",
        )
        for t in teachers
    ]


# ── 5. Bulk Student & Subject Mutations + Full Class XLSX Import ──

@router.post("/{class_id}/students/bulk-enroll", status_code=status.HTTP_200_OK)
def bulk_enroll_students(
    class_id: int,
    data: StudentBulkEnrollRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    for s_id in data.student_ids:
        ClassStructureService.enroll_student_to_class(
            db=db, school_id=school_id, student_id=s_id, class_id=class_id
        )
    db.commit()
    return {"status": "success", "enrolled_count": len(data.student_ids)}


@router.post("/{class_id}/students/bulk-remove", status_code=status.HTTP_200_OK)
def bulk_remove_students(
    class_id: int,
    data: StudentBulkRemoveRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    for s_id in data.student_ids:
        ClassStructureService.remove_student_from_class(
            db=db, school_id=school_id, student_id=s_id, class_id=class_id
        )
    db.commit()
    return {"status": "success", "removed_count": len(data.student_ids)}


@router.post("/{class_id}/subjects/bulk-assign", status_code=status.HTTP_200_OK)
def bulk_assign_subjects(
    class_id: int,
    data: ClassSubjectBulkAssignRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    for subj_id in data.subject_ids:
        ClassStructureService.assign_subject_to_class(
            db=db, school_id=school_id, class_id=class_id, subject_id=subj_id
        )
    db.commit()
    return {"status": "success", "assigned_count": len(data.subject_ids)}


@router.post("/{class_id}/subjects/bulk-remove", status_code=status.HTTP_200_OK)
def bulk_remove_subjects(
    class_id: int,
    data: ClassSubjectBulkRemoveRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    school_id = _get_school_id(current_user)
    for subj_id in data.subject_ids:
        ClassStructureService.remove_subject_from_class(
            db=db, school_id=school_id, class_id=class_id, subject_id=subj_id
        )
    db.commit()
    return {"status": "success", "removed_count": len(data.subject_ids)}


@router.post("/import-full", response_model=ImportResponse[ClassSubjectTeacherResponse])
def import_full_classes_xlsx(
    request: Request,
    data: ClassFullImportRequest,
    current_user=Depends(require_admin()),
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse
    from app.schemas.common.import_validation import ImportResponse, ImportRowError

    school_id = _get_school_id(current_user)

    classes_list = []
    for cls in data.classes:
        classes_list.append(cls.model_dump())

    success, created_relations, errors = ClassStructureService.import_classes_xlsx(
        db=db,
        school_id=school_id,
        academic_year_id=data.academic_year_id,
        classes_data=classes_list,
    )

    if not success:
        row_errors = [ImportRowError(**err) for err in errors]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ImportResponse(
                status="error",
                message="Impor struktur kelas gagal karena terdapat kesalahan validasi.",
                imported_count=0,
                errors=row_errors,
            ).model_dump()
        )

    # Logging activity
    user_id = int(current_user["sub"])
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="CLASS_STRUCTURE",
        action_name="IMPORT_CLASS_STRUCTURE",
        school_id=school_id,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "academic_year_id": data.academic_year_id,
            "classes_count": len(data.classes),
            "assigned_teachers_count": len(created_relations)
        },
    )

    db.commit()

    # Resolve details for response
    from app.repositories.security.auth_repository import auth_repository
    from app.repositories.academic.subject_repository import subject_repository
    from app.repositories.academic.class_repository import class_repository

    response_data = []
    for cst in created_relations:
        teacher = auth_repository.get_by_id(db, cst.teacher_id)
        subj = subject_repository.get_by_id(db, cst.subject_id)
        cls = class_repository.get_by_id(db, cst.class_id)
        response_data.append(
            ClassSubjectTeacherResponse(
                id=cst.id,
                school_id=cst.school_id,
                class_id=cst.class_id,
                subject_id=cst.subject_id,
                teacher_id=cst.teacher_id,
                created_at=cst.created_at,
                teacher_name=teacher.name if teacher else None,
                teacher_username=teacher.username if teacher else None,
                teacher_nip=teacher.nip if teacher else None,
                subject_name=subj.name if subj else None,
                class_name=cls.name if cls else None,
            )
        )

    return ImportResponse[ClassSubjectTeacherResponse](
        status="success",
        message=f"Berhasil menyinkronkan {len(data.classes)} rombel kelas secara massal.",
        imported_count=len(created_relations),
        data=response_data,
    )

