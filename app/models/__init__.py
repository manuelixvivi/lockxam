from app.models.academic.academic_semester import AcademicSemester as AcademicSemester
from app.models.academic.academic_year import AcademicYear as AcademicYear
from app.models.academic.class_entity import ClassEntity as ClassEntity
from app.models.academic.class_subject import ClassSubject as ClassSubject
from app.models.academic.class_subject_teacher import ClassSubjectTeacher as ClassSubjectTeacher
from app.models.academic.enums import (
    AcademicStatus as AcademicStatus,
)
from app.models.academic.enums import (
    EnrollmentStatus as EnrollmentStatus,
)
from app.models.academic.enums import (
    ExamScheduleStatus as ExamScheduleStatus,
)
from app.models.academic.enums import (
    GradingRunStatus as GradingRunStatus,
)
from app.models.academic.exam_schedule import ExamSchedule as ExamSchedule
from app.models.academic.exam_snapshot import ExamSnapshot as ExamSnapshot
from app.models.academic.grading_run import GradingRun as GradingRun
from app.models.academic.student_class_enrollment import (
    StudentClassEnrollment as StudentClassEnrollment,
)
from app.models.academic.subject import Subject as Subject
from app.models.academic.teacher_subject import TeacherSubject as TeacherSubject
from app.models.ai.ai_system_setting import (
    AiConfigHistory as AiConfigHistory,
    AiSystemSetting as AiSystemSetting,
)
from app.models.ai.assessment_embedding import AssessmentEmbedding as AssessmentEmbedding
from app.models.ai.assessment_history import AssessmentHistory as AssessmentHistory
from app.models.ai.dataset_version import DatasetVersion as DatasetVersion
from app.models.ai.model_version import (
    ModelVersion as ModelVersion,
)
from app.models.ai.model_version import (
    ModelVersionStatus as ModelVersionStatus,
)
from app.models.ai.registered_model import RegisteredModel as RegisteredModel
from app.models.ai.training_candidate import TrainingCandidate as TrainingCandidate
from app.models.ai.training_job import (
    TrainingJob as TrainingJob,
)
from app.models.ai.training_job import (
    TrainingJobStatus as TrainingJobStatus,
)
from app.models.exam.ai_event_log import AiGradingEventLog as AiGradingEventLog
from app.models.exam.answer_evaluation import ExamAnswerEvaluation as ExamAnswerEvaluation
from app.models.exam.device_session import DeviceSession as DeviceSession
from app.models.exam.enums import (
    DeviceSessionStatus as DeviceSessionStatus,
)
from app.models.exam.enums import (
    ExamAttemptStatus as ExamAttemptStatus,
)
from app.models.exam.enums import (
    ExamSessionStatus as ExamSessionStatus,
)
from app.models.exam.enums import (
    GradingSource as GradingSource,
)
from app.models.exam.enums import (
    GradingStatus as GradingStatus,
)
from app.models.exam.exam_attempt import ExamAttempt as ExamAttempt
from app.models.exam.exam_checkin import ExamCheckin as ExamCheckin
from app.models.exam.exam_session import ExamSession as ExamSession
from app.models.exam.package_snapshot import ExamPackageSnapshot as ExamPackageSnapshot
from app.models.exam.student_answer import StudentAnswer as StudentAnswer
from app.models.license.activation_key import ActivationKey as ActivationKey
from app.models.license.renewal_request import RenewalRequest as RenewalRequest
from app.models.license.school_license import SchoolLicense as SchoolLicense
from app.models.master.license_type import LicenseType as LicenseType
from app.models.master.school_level import SchoolLevel as SchoolLevel
from app.models.school.school import School as School
from app.models.school.school_setting import SchoolSetting as SchoolSetting
from app.models.security.activity_log import ActivityLog as ActivityLog
from app.models.security.auth_account import AuthAccount as AuthAccount
from app.models.security.enums import SessionRevokedReason as SessionRevokedReason
from app.models.security.enums import UserRole as UserRole
from app.models.security.login_attempt import LoginAttempt as LoginAttempt
from app.models.security.user_session import UserSession as UserSession
from app.models.teacher.bau_attendance import BAUAttendance as BAUAttendance
from app.models.teacher.bau_document import BAUDocument as BAUDocument
from app.models.teacher.enums import (
    AttendanceStatus as AttendanceStatus,
)
from app.models.teacher.enums import (
    BAUStatus as BAUStatus,
)
from app.models.teacher.enums import (
    PackageStatus as PackageStatus,
)
from app.models.teacher.enums import (
    ProctorEventType as ProctorEventType,
)
from app.models.teacher.enums import (
    QuestionType as QuestionType,
)
from app.models.teacher.package_item import QuestionPackageItem as QuestionPackageItem
from app.models.teacher.proctor_event import ProctorAuditEvent as ProctorAuditEvent
from app.models.teacher.question import Question as Question
from app.models.teacher.question_package import QuestionPackage as QuestionPackage
