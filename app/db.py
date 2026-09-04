"""Trai tim cua tang async: Base (class cha moi model), engine (pool ket noi),
SessionLocal (factory tao session), get_session() (dependency cap session cho route).

Tuong duong Go: `sql.DB` la pool, moi request mo 1 `Tx`. O day `AsyncSession` la
"don vi cong viec" — mo 1 cai / request, dong khi request xong.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Class cha cho moi model SQLAlchemy. `Base.metadata` gom mo ta tat ca bang —
    Alembic doc chinh cai nay de so sanh voi DB that."""


# Pool ket noi. `pool_pre_ping=True`: kiem tra connection con song truoc khi dung
# (tranh loi khi Postgres container restart giua chung).
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.sql_echo,
)

# Factory tao AsyncSession.
# `expire_on_commit=False` BAT BUOC voi async: mac dinh True se "het han" moi
# thuoc tinh sau commit() -> lan truy cap ke tiep lazy-load -> loi MissingGreenlet.
# `autoflush=False`: khong tu flush truoc moi query — flush tuong minh khi can.
SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency cua FastAPI: `session: AsyncSession = Depends(get_session)`.

    `async with` mo session; `yield` giao cho route dung; khi route xong (hoac ne
    loi) khoi `async with` thoat -> session.close() tu chay. Giong `defer
    session.Close()` cua Go.
    """
    async with SessionLocal() as session:
        yield session
