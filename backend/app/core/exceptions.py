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


class ConfigurationError(FinExException):
    def __init__(
        self,
        message: str,
        error_code: str = "CONFIGURATION_ERROR",
        status_code: int = 500,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
        )


class CORSConfigurationError(ConfigurationError):
    def __init__(
        self,
        message: str,
        error_code: str = "CORS_CONFIGURATION_ERROR",
        status_code: int = 500,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
        )


class ProviderUnavailableException(FinExException):
    """A configured market-data provider cannot be reached safely."""

    def __init__(self, provider: str, reason: str = "upstream provider is unavailable"):
        super().__init__(
            message=f"Market-data provider '{provider}' is unavailable: {reason}",
            error_code="PROVIDER_UNAVAILABLE",
            status_code=503,
        )


class ProviderTimeoutException(FinExException):
    """A provider did not respond before the bounded request timeout."""

    def __init__(self, provider: str, timeout_seconds: float):
        super().__init__(
            message=(
                f"Market-data provider '{provider}' timed out after {timeout_seconds:g} seconds."
            ),
            error_code="PROVIDER_TIMEOUT",
            status_code=504,
        )


class RateLimitExceededException(FinExException):
    """A provider rejected a request because its rate limit was reached."""

    def __init__(self, provider: str, retry_after_seconds: int | None = None):
        retry_hint = (
            f" Retry after {retry_after_seconds} seconds."
            if retry_after_seconds is not None
            else ""
        )
        super().__init__(
            message=f"Market-data provider '{provider}' rate limit was exceeded.{retry_hint}",
            error_code="PROVIDER_RATE_LIMITED",
            status_code=429,
        )


class SymbolNotFoundException(NotFoundException):
    """A requested market symbol is not available from the selected provider."""

    def __init__(self, symbol: str):
        super().__init__(
            message=f"Market symbol '{symbol}' was not found.",
            error_code="MARKET_SYMBOL_NOT_FOUND",
        )
