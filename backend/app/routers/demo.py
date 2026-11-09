from fastapi import APIRouter

from app.core.exceptions import FinExException

router = APIRouter(
    prefix="/api/v1/demo",
    tags=["Demo"],
)


@router.get("/error")
def generate_error():

    raise FinExException(
        message="This is a demo exception.",
        error_code="DEMO_ERROR",
        status_code=400,
    )


@router.get("/error500")
def generate_server_error():
    raise FinExException(
        message="An unexpected error occurred.",
        error_code="INTERNAL_SERVER_ERROR",
        status_code=500,
    )
