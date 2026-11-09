class FinExException(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)

        # Backward-compatible alias used by existing tests/code


AppException = FinExException


class UserNotFoundException(FinExException):
    def __init__(self, message: str = "User not found"):
        super().__init__(
            message=message,
            error_code="USER_NOT_FOUND",
            status_code=404,
        )


class AuthenticationException(FinExException):
    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_FAILED",
        status_code: int = 401,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
        )


class PortfolioException(FinExException):
    def __init__(self, message: str = "Portfolio error"):
        super().__init__(
            message=message,
            error_code="PORTFOLIO_ERROR",
            status_code=400,
        )


class AIException(FinExException):
    def __init__(self, message: str = "AI service error"):
        super().__init__(
            message=message,
            error_code="AI_ERROR",
            status_code=500,
        )


class DatabricksException(FinExException):
    def __init__(self, message: str = "Databricks connection error"):
        super().__init__(
            message=message,
            error_code="DATABRICKS_ERROR",
            status_code=500,
        )


class NotFoundException(FinExException):
    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "NOT_FOUND",
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=404,
        )


class UnauthorizedException(FinExException):
    def __init__(
        self,
        message: str = "Unauthorized",
        error_code: str = "UNAUTHORIZED",
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=401,
        )


class ForbiddenException(FinExException):
    def __init__(
        self,
        message: str = "Forbidden",
        error_code: str = "FORBIDDEN",
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=403,
        )


class BadRequestException(FinExException):
    def __init__(
        self,
        message: str = "Bad request",
        error_code: str = "BAD_REQUEST",
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
        )
