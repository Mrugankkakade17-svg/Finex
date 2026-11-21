from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, EmailStr


class UserModel(BaseModel):
    id: Optional[Union[int, str]] = None
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

    @property
    def user_id(self) -> str:
        return str(self.id) if self.id is not None else ""

    @property
    def password_hash(self) -> str:
        return self.hashed_password
