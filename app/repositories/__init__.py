from app.repositories.academic.academic_semester_repository import (
    academic_semester_repository as academic_semester_repository,
)
from app.repositories.academic.academic_year_repository import (
    academic_year_repository as academic_year_repository,
)
from app.repositories.base_repository import BaseRepository as BaseRepository
from app.repositories.license.activation_key_repository import (
    activation_key_repository as activation_key_repository,
)
from app.repositories.license.renewal_request_repository import (
    renewal_request_repository as renewal_request_repository,
)
from app.repositories.license.school_license_repository import (
    school_license_repository as school_license_repository,
)
from app.repositories.master.license_type_repository import (
    license_type_repository as license_type_repository,
)
from app.repositories.master.school_level_repository import (
    school_level_repository as school_level_repository,
)
from app.repositories.school.school_repository import school_repository as school_repository
from app.repositories.school.school_setting_repository import (
    school_setting_repository as school_setting_repository,
)
from app.repositories.security.activity_repository import activity_repository as activity_repository
from app.repositories.security.auth_repository import auth_repository as auth_repository
from app.repositories.security.login_attempt_repository import (
    login_attempt_repository as login_attempt_repository,
)
from app.repositories.security.session_repository import session_repository as session_repository
from app.repositories.teacher.bau_repository import (
    bau_repository as bau_repository,
)
from app.repositories.teacher.proctor_event_repository import (
    proctor_event_repository as proctor_event_repository,
)
from app.repositories.teacher.question_package_repository import (
    question_package_repository as question_package_repository,
)
from app.repositories.teacher.question_repository import (
    question_repository as question_repository,
)
