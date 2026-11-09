from typing import Optional

from pydantic import BaseModel, EmailStr


class ProfileResponse(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    risk_profile: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    risk_profile: Optional[str] = None
