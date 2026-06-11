"""Generic async repository base class.

Repositories encapsulate all data-access logic so that services never build raw
SQL/ORM queries directly. Each repository operates on an injected
``AsyncSession`` and is therefore safe to instantiate per-request.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base


class BaseRepository[ModelT: Base]:
    """CRUD helpers shared by all repositories."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, pk: int) -> ModelT | None:
        return await self.session.get(self.model, pk)

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)

    async def delete_by_id(self, pk: int) -> None:
        await self.session.execute(delete(self.model).where(self.model.id == pk))  # type: ignore[attr-defined]

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self.session.execute(select(self.model).limit(limit).offset(offset))
        return list(result.scalars().all())
