from fastapi import Request
from fastapi.responses import JSONResponse

from app.config.logging import logger
from app.exceptions.custom_exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException):
    logger.error(f"{exc.error_code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR",
        },
    )
