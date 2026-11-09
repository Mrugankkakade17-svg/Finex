from typing import Any, Optional

from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
