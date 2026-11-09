# backend/app/repositories/dat02_repository.py
"""
S1-DAT-02 – Repository for operational tables (users, user_profiles,
portfolio_holdings) stored in Lakebase/Postgres.

Follows the same security pattern as c1_repository.py:
    * Parameterised SQL via sqlalchemy.text()
    * Every user-owned query constrains by user_id
    * Uses the existing AsyncSession from lakebase.py
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class Dat02Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------

    async def create_user(
        self,
        email: str,
        password_hash: str,
        name: str,
        role: str = "user",
        risk_profile: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a new user.  Returns the stored row."""
        uid = user_id or str(uuid.uuid4())
        query = text(
            """
            INSERT INTO finex.users (
                user_id, email, password_hash, name, role,
                risk_profile, is_active, created_at, updated_at
            )
            VALUES (
                :uid, :email, :pw, :name, :role,
                :risk, TRUE, NOW(), NOW()
            )
            ON CONFLICT (user_id) DO NOTHING
            RETURNING
                user_id, email, name, role, risk_profile,
                is_active, created_at, updated_at
            """
        )
        result = await self.session.execute(
            query,
            {
                "uid": uid,
                "email": email,
                "pw": password_hash,
                "name": name,
                "role": role,
                "risk": risk_profile,
            },
        )
        row = result.fetchone()
        if row is None:
            # ON CONFLICT hit – row already exists; fetch and return it
            return await self.get_user_by_id(uid) or {}
        return dict(row._mapping)

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single user by their UUID."""
        query = text(
            """
            SELECT user_id, email, name, role, risk_profile,
                   is_active, created_at, updated_at
            FROM finex.users
            WHERE user_id = :uid
            """
        )
        result = await self.session.execute(query, {"uid": user_id})
        row = result.fetchone()
        return dict(row._mapping) if row else None

    # ------------------------------------------------------------------
    # user_profiles
    # ------------------------------------------------------------------

    async def create_user_profile(
        self,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a user profile.  Idempotent via ON CONFLICT."""
        pid = profile_id or str(uuid.uuid4())
        query = text(
            """
            INSERT INTO finex.user_profiles (
                profile_id, user_id, first_name, last_name, phone,
                date_of_birth, address, city, country,
                created_at, updated_at
            )
            VALUES (
                :pid, :uid, :fn, :ln, :phone,
                :dob, :addr, :city, :country,
                NOW(), NOW()
            )
            ON CONFLICT (profile_id) DO NOTHING
            RETURNING
                profile_id, user_id, first_name, last_name, phone,
                date_of_birth, address, city, country,
                created_at, updated_at
            """
        )
        result = await self.session.execute(
            query,
            {
                "pid": pid,
                "uid": user_id,
                "fn": first_name,
                "ln": last_name,
                "phone": phone,
                "dob": date_of_birth,
                "addr": address,
                "city": city,
                "country": country,
            },
        )
        row = result.fetchone()
        if row is None:
            return await self.get_user_profile(pid, user_id) or {}
        return dict(row._mapping)

    async def get_user_profile(self, profile_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a profile ensuring the caller owns it (user_id constraint)."""
        query = text(
            """
            SELECT profile_id, user_id, first_name, last_name, phone,
                   date_of_birth, address, city, country,
                   created_at, updated_at
            FROM finex.user_profiles
            WHERE profile_id = :pid
              AND user_id = :uid
            """
        )
        result = await self.session.execute(query, {"pid": profile_id, "uid": user_id})
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def get_profiles_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all profiles owned by user_id."""
        query = text(
            """
            SELECT profile_id, user_id, first_name, last_name, phone,
                   date_of_birth, address, city, country,
                   created_at, updated_at
            FROM finex.user_profiles
            WHERE user_id = :uid
            ORDER BY created_at
            """
        )
        result = await self.session.execute(query, {"uid": user_id})
        return [dict(r._mapping) for r in result.fetchall()]

    # ------------------------------------------------------------------
    # portfolio_holdings
    # ------------------------------------------------------------------

    async def create_holding(
        self,
        user_id: str,
        portfolio_id: str,
        instrument_symbol: str,
        quantity: float,
        avg_buy_price: float,
        current_value: Optional[float] = None,
        holding_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a portfolio holding.  Idempotent via ON CONFLICT."""
        hid = holding_id or str(uuid.uuid4())
        query = text(
            """
            INSERT INTO finex.portfolio_holdings (
                holding_id, portfolio_id, user_id,
                instrument_symbol, quantity, avg_buy_price,
                current_value, created_at, updated_at
            )
            VALUES (
                :hid, :pid, :uid,
                :sym, :qty, :price,
                :cv, NOW(), NOW()
            )
            ON CONFLICT (holding_id) DO NOTHING
            RETURNING
                holding_id, portfolio_id, user_id,
                instrument_symbol, quantity, avg_buy_price,
                current_value, created_at, updated_at
            """
        )
        result = await self.session.execute(
            query,
            {
                "hid": hid,
                "pid": portfolio_id,
                "uid": user_id,
                "sym": instrument_symbol,
                "qty": quantity,
                "price": avg_buy_price,
                "cv": current_value,
            },
        )
        row = result.fetchone()
        if row is None:
            return await self.get_holding_by_id(hid, user_id) or {}
        return dict(row._mapping)

    async def get_holding_by_id(self, holding_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single holding, constrained by user_id for isolation."""
        query = text(
            """
            SELECT holding_id, portfolio_id, user_id,
                   instrument_symbol, quantity, avg_buy_price,
                   current_value, created_at, updated_at
            FROM finex.portfolio_holdings
            WHERE holding_id = :hid
              AND user_id = :uid
            """
        )
        result = await self.session.execute(query, {"hid": holding_id, "uid": user_id})
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def get_holdings_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all holdings owned by user_id."""
        query = text(
            """
            SELECT holding_id, portfolio_id, user_id,
                   instrument_symbol, quantity, avg_buy_price,
                   current_value, created_at, updated_at
            FROM finex.portfolio_holdings
            WHERE user_id = :uid
            ORDER BY created_at
            """
        )
        result = await self.session.execute(query, {"uid": user_id})
        return [dict(r._mapping) for r in result.fetchall()]
