"""
dat02_models.py

S1-DAT-02 – SQLAlchemy ORM models for the Lakebase/Postgres operational tables.

Tables defined here:
    finex.users
    finex.user_profiles
    finex.portfolio_holdings

Design notes:
    * UUID primary keys stored as TEXT (matches c1_repository.py convention).
    * All timestamps default to UTC via server_default.
    * These models are imported by Alembic env.py through the shared Base.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.ports.adapters.lakebase import Base


class User(Base):
    """Operational user record – Lakebase/Postgres."""

    __tablename__ = "users"
    __table_args__ = {"schema": "finex"}

    user_id = Column(Text, primary_key=True)
    email = Column(String(320), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(50), server_default="user")
    risk_profile = Column(String(50), nullable=True)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class UserProfile(Base):
    """Extended profile information for a user."""

    __tablename__ = "user_profiles"
    __table_args__ = {"schema": "finex"}

    profile_id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class PortfolioHolding(Base):
    """Individual holding within a portfolio."""

    __tablename__ = "portfolio_holdings"
    __table_args__ = {"schema": "finex"}

    holding_id = Column(Text, primary_key=True)
    portfolio_id = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    instrument_symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_buy_price = Column(Float, nullable=False)
    current_value = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
