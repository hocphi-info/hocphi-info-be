"""Fixture dung chung cho pytest — 3 tang, dung Alembic that (khong
`Base.metadata.create_all()`) de moi test cung bat loi migration that:

- `_schema` (session, 1 lan): `alembic upgrade head`; teardown `downgrade base`.
- `engine` (session, 1 lan): pool ket noi toi DB test.
- `db` (moi test): 1 `AsyncSession` boc trong SAVEPOINT — test duoc goi
  `session.commit()` binh thuong, roi rollback sach o cuoi, DB tro ve trang
  thai truoc test du chay bao nhieu test cung 1 DB.

QUAN TRONG: ghi de bien moi truong `DATABASE_URL` TRUOC khi import bat ky module
`app.*` nao — de test luon chay tren mot DB rieng (mac dinh them hau to `_test`),
KHONG dung chung DB dev dang chay (alembic `downgrade base` o teardown se xoa
sach schema — nguy hiem neu trung DB dev). CI hoac owner co the set thang
`TEST_DATABASE_URL` de dung dung 1 DB (vi du DB service container CI).
"""

import os


def _resolve_test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    dev_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://hocphi:hocphi@localhost:5432/hocphi"
    )
    prefix, _, dbname = dev_url.rpartition("/")
    return f"{prefix}/{dbname}_test"


os.environ["DATABASE_URL"] = _resolve_test_database_url()

from collections.abc import AsyncGenerator, Generator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


@pytest.fixture(scope="session")
def _schema() -> Generator[None, None, None]:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")


@pytest_asyncio.fixture(scope="session")
async def engine(_schema: None) -> AsyncGenerator[AsyncEngine, None]:
    from app.config import settings

    eng = create_async_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        yield session
        await session.close()
        await trans.rollback()
