from app.repositories.academic.academic_semester_repository import (
    academic_semester_repository,
)
from app.repositories.academic.academic_year_repository import (
    academic_year_repository,
)
from app.repositories.academic.class_repository import class_repository
from app.repositories.academic.class_subject_repository import class_subject_repository
from app.repositories.academic.class_subject_teacher_repository import (
    class_subject_teacher_repository,
)
from app.repositories.academic.exam_schedule_repository import exam_schedule_repository
from app.repositories.academic.exam_snapshot_repository import exam_snapshot_repository
from app.repositories.academic.student_enrollment_repository import (
    student_enrollment_repository,
)
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.academic.teacher_subject_repository import (
    teacher_subject_repository,
)

__all__ = [
    "academic_year_repository",
    "academic_semester_repository",
    "subject_repository",
    "class_repository",
    "teacher_subject_repository",
    "student_enrollment_repository",
    "class_subject_repository",
    "class_subject_teacher_repository",
    "exam_schedule_repository",
    "exam_snapshot_repository",
]
