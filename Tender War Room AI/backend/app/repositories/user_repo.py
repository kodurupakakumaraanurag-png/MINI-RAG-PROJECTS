from typing import Any, Dict, Optional, Union
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.core.security import get_password_hash


class UserRepository:
    async def get(self, db: AsyncSession, id: UUID) -> Optional[User]:
        result = await db.execute(select(User).filter(User.id == id))
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).filter(User.email == email))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, username: str, email: str, password: str, role: UserRole) -> User:
        db_obj = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=role
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: User, obj_in: Dict[str, Any]
    ) -> User:
        for field in obj_in:
            if field == "password":
                setattr(db_obj, "hashed_password", get_password_hash(obj_in[field]))
            elif hasattr(db_obj, field):
                setattr(db_obj, field, obj_in[field])
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


user_repository = UserRepository()
