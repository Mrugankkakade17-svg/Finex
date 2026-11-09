from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserModel(BaseModel):
    id: Optional[int] = None
    name: str
    email: EmailStr
    hashed_password: str
    google_id: Optional[str] = None
    picture: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = True
    role: str = "user"
    risk_profile: Optional[str] = None
