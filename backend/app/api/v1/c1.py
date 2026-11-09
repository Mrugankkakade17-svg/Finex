# backend/app/api/v1/c1.py
import uuid

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

# Import our database connection and layers
from app.ports.adapters.lakebase import get_db_session
from app.repositories.c1_repository import C1Repository
from app.schemas.c1 import APIResponse, MetaData, PortfolioCreateRequest, PortfolioResponse
from app.services.c1_service import C1Service

# Create the router for the Portfolio Foundation (POR-01)
router = APIRouter(
    prefix="/api/v1/portfolios",
    tags=["Portfolio Foundation"],
)


@router.post(
    "",
    response_model=APIResponse[PortfolioResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_portfolio(
    payload: PortfolioCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    x_correlation_id: str = Header(
        default_factory=lambda: str(uuid.uuid4()),
        alias="X-Correlation-ID",
    ),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Creates a new manual portfolio for the user.
    """
    # Initialize the repository and service with the active database session
    repo = C1Repository(db)
    service = C1Service(repo)

    # Execute the deterministic business logic
    portfolio = await service.create_user_portfolio(
        user_id=x_user_id,
        name=payload.name,
        p_type=payload.type,
        currency=payload.base_currency,
    )

    # Commit the transaction to the database
    await db.commit()

    # Return the strict FinEx standard envelope
    return APIResponse(
        data=PortfolioResponse(
            portfolio_id=portfolio["portfolio_id"],
            user_id=portfolio["user_id"],
            name=portfolio["name"],
            type=portfolio["type"],
            base_currency=portfolio["base_currency"],
            status=portfolio["status"],
            created_at=portfolio["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
        meta=MetaData(
            correlationId=x_correlation_id,
            dataStatus="LIVE",
        ),
    )
