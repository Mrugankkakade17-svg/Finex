from app.core.exceptions import (
    AIException,
    AppException,
    AuthenticationException,
    BadRequestException,
    DatabricksException,
    FinExException,
    ForbiddenException,
    NotFoundException,
    PortfolioException,
    UnauthorizedException,
    UserNotFoundException,
)


def test_base_finex_exception():
    exc = FinExException(
        message="Test error",
        error_code="TEST_ERROR",
        status_code=418,
    )

    assert exc.message == "Test error"
    assert exc.error_code == "TEST_ERROR"
    assert exc.status_code == 418


def test_app_exception_alias():
    assert AppException is FinExException


def test_user_not_found_exception():
    exc = UserNotFoundException()

    assert exc.message == "User not found"
    assert exc.error_code == "USER_NOT_FOUND"
    assert exc.status_code == 404


def test_authentication_exception():
    exc = AuthenticationException()

    assert exc.message == "Authentication failed"
    assert exc.error_code == "AUTHENTICATION_FAILED"
    assert exc.status_code == 401


def test_portfolio_exception():
    exc = PortfolioException()

    assert exc.message == "Portfolio error"
    assert exc.error_code == "PORTFOLIO_ERROR"
    assert exc.status_code == 400


def test_ai_exception():
    exc = AIException()

    assert exc.message == "AI service error"
    assert exc.error_code == "AI_ERROR"
    assert exc.status_code == 500


def test_databricks_exception():
    exc = DatabricksException()

    assert exc.message == "Databricks connection error"
    assert exc.error_code == "DATABRICKS_ERROR"
    assert exc.status_code == 500


def test_not_found_exception():
    exc = NotFoundException()

    assert exc.message == "Resource not found"
    assert exc.error_code == "NOT_FOUND"
    assert exc.status_code == 404


def test_unauthorized_exception():
    exc = UnauthorizedException()

    assert exc.message == "Unauthorized"
    assert exc.error_code == "UNAUTHORIZED"
    assert exc.status_code == 401


def test_forbidden_exception():
    exc = ForbiddenException()

    assert exc.message == "Forbidden"
    assert exc.error_code == "FORBIDDEN"
    assert exc.status_code == 403


def test_bad_request_exception():
    exc = BadRequestException()

    assert exc.message == "Bad request"
    assert exc.error_code == "BAD_REQUEST"
    assert exc.status_code == 400
