class AppException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", error_code: str = "NOT_FOUND"):
        super().__init__(message=message, error_code=error_code, status_code=404)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", error_code: str = "UNAUTHORIZED"):
        super().__init__(message=message, error_code=error_code, status_code=401)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", error_code: str = "FORBIDDEN"):
        super().__init__(message=message, error_code=error_code, status_code=403)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", error_code: str = "BAD_REQUEST"):
        super().__init__(message=message, error_code=error_code, status_code=400)
