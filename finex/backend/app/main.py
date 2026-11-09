from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ExceptionHandler

from app.config.logging import logger
from app.config.settings import get_settings
from app.core.exceptions import FinExException
from app.core.handlers import (
    finex_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import CorrelationIdMiddleware
from app.routers.auth import router as auth_router
from app.routers.demo import router as demo_router
from app.routers.health import router as health_router
from app.routers.onboarding import router as onboarding_router
from app.routers.profile import router as profile_router
from app.routers.risk import router as risk_router
from app.routers.users import router as users_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FinEx Financial Platform Backend",
)


app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(demo_router)
app.include_router(profile_router)
app.include_router(risk_router)
app.include_router(onboarding_router)


app.add_exception_handler(
    FinExException,
    finex_exception_handler,
)

app.add_exception_handler(
    HTTPException,
    http_exception_handler,
)

app.add_exception_handler(
    RequestValidationError,
    cast(ExceptionHandler, validation_exception_handler),
)


@app.on_event("startup")
async def startup():
    logger.info("FinEx Backend Started")


@app.on_event("shutdown")
async def shutdown():
    logger.info("FinEx Backend Stopped")
