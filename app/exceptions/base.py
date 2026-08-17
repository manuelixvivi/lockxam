class AppException(Exception):

    def __init__(self, message: str = "An unexpected error occurred", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthenticationException(AppException):

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, status_code=401)


class PermissionException(AppException):

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class ValidationException(AppException):

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)


class BusinessException(AppException):

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class LicenseExpiredException(AppException):

    def __init__(
        self,
        message: str = "School license has expired. This operation is not allowed in READ_ONLY mode.",
    ):
        super().__init__(message, status_code=403)


class AcademicValidationException(AppException):

    def __init__(self, errors: list[str]):
        super().__init__("Academic period verification failed", status_code=400)
        self.errors = errors
