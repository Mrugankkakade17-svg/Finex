from threading import Lock
from typing import Optional, cast

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ExceptionHandler

from app.auth.local_boundary import require_local_legacy_auth
from app.config.cors import get_cors_middleware_kwargs
from app.config.logging import logger
from app.config.settings import Settings, get_settings
from app.core.exceptions import FinExException
from app.core.handlers import (
    finex_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import CorrelationIdMiddleware, LocalApplicationBoundaryMiddleware
from app.domain.local_application import Clock
from app.ports.local_application_store import LocalApplicationStore
from app.ports.local_foundation_store import LocalFoundationStore
from app.ports.local_portfolio_quotes import LocalPortfolioCatalogPort, LocalPortfolioQuotePort
from app.ports.local_portfolio_store import LocalPortfolioStore
from app.ports.local_risk_store import LocalRiskStore
from app.routers.auth import router as auth_router
from app.routers.consent_profile import router as consent_profile_router
from app.routers.demo import router as demo_router
from app.routers.health import router as health_router
from app.routers.local_application import router as local_application_router
from app.routers.local_foundation import router as local_foundation_router
from app.routers.local_portfolio import router as local_portfolio_router
from app.routers.local_risk import router as local_risk_router
from app.routers.onboarding import router as onboarding_router
from app.routers.profile import router as profile_router
from app.routers.risk import router as risk_router
from app.routers.risk_contract import router as risk_contract_router
from app.routers.users import router as users_router
from app.routers.paper_trading import router as paper_trading_router
from app.routers.goals import router as goals_router
from app.routers.privacy import router as privacy_router
from app.routers.spending import router as spending_router
from app.routers.ai_assistant import router as ai_assistant_router
from app.routers.alerts import router as alerts_router
from app.routers.ops_hardening import router as ops_hardening_router
from app.routers.release_handover import router as release_handover_router


def create_app(
    custom_settings: Optional[Settings] = None,
    *,
    local_store: LocalApplicationStore | None = None,
    local_risk_store: LocalRiskStore | None = None,
    local_portfolio_store: LocalPortfolioStore | None = None,
    local_portfolio_catalogue: LocalPortfolioCatalogPort | None = None,
    local_portfolio_quotes: LocalPortfolioQuotePort | None = None,
    local_foundation_store: LocalFoundationStore | None = None,
    local_clock: Clock | None = None,
) -> FastAPI:
    """Create the API with an explicit, validated configuration boundary."""

    active_settings = custom_settings or get_settings()
    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description="FinEx Financial Platform Backend",
    )
    application.state.settings = active_settings
    application.state.local_application_store = local_store
    application.state.local_clock = local_clock
    application.state.local_application_service = None
    application.state.local_service_lock = Lock()
    application.state.local_risk_store = local_risk_store
    application.state.local_risk_service = None
    application.state.local_risk_service_lock = Lock()
    application.state.local_portfolio_store = local_portfolio_store
    application.state.local_portfolio_catalogue = local_portfolio_catalogue
    application.state.local_portfolio_quotes = local_portfolio_quotes
    application.state.local_portfolio_service = None
    application.state.local_portfolio_service_lock = Lock()
    application.state.local_foundation_store = local_foundation_store
    application.state.local_foundation_service = None
    application.state.local_foundation_service_lock = Lock()

    application.add_middleware(LocalApplicationBoundaryMiddleware)
    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(CORSMiddleware, **get_cors_middleware_kwargs(active_settings))

    application.include_router(health_router)
    legacy_dependencies = [Depends(require_local_legacy_auth)]
    application.include_router(auth_router, dependencies=legacy_dependencies)
    application.include_router(users_router, dependencies=legacy_dependencies)
    application.include_router(demo_router)
    application.include_router(profile_router, dependencies=legacy_dependencies)
    application.include_router(risk_router, dependencies=legacy_dependencies)
    application.include_router(risk_contract_router)
    application.include_router(onboarding_router, dependencies=legacy_dependencies)
    application.include_router(consent_profile_router)
    application.include_router(local_application_router)
    application.include_router(local_portfolio_router)
    application.include_router(local_risk_router)
    application.include_router(local_foundation_router)
    application.include_router(paper_trading_router)
    application.include_router(goals_router)
    application.include_router(privacy_router)
    application.include_router(spending_router)
    application.include_router(ai_assistant_router)
    application.include_router(alerts_router)
    application.include_router(ops_hardening_router)
    application.include_router(release_handover_router)

    @application.get("/", include_in_schema=False)
    def root():
        return {
            "status": "healthy",
            "service": active_settings.app_name,
            "version": active_settings.app_version,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    application.add_exception_handler(FinExException, finex_exception_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )

    @application.on_event("startup")
    async def startup() -> None:
        logger.info(
            "FinEx Backend Started - environment=%s version=%s",
            active_settings.app_env.value,
            active_settings.app_version,
        )

    @application.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("FinEx Backend Stopped")

    return application


app = create_app()
