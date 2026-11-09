from typing import Optional

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: int

    name: str

    email: EmailStr

    risk_profile: Optional[str] = None
