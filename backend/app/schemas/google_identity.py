from typing import Optional

from pydantic import BaseModel, EmailStr


class GoogleIdentity(BaseModel):
    """
    Represents a verified Google identity.
    Returned by GoogleOAuthPort.verify_google_token().
    """

    google_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
