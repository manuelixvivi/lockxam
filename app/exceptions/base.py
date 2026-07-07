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
