"""Alembic env — template async (`alembic init -t async`), chinh 3 cho:

1. Lay URL DB tu app.config (khong hard-code trong alembic.ini).
2. target_metadata = Base.metadata (import app.models de metadata day du).
3. Cac co so sanh + include_object loai VIEW school_track_stats khoi autogenerate.

Template async chay body migration (sync) ben trong async connection qua
`connection.run_sync(do_run_migrations)` — nen giu URL `postgresql+asyncpg://`,
KHONG can URL sync thu hai.
"""

import asyncio
from logging.config import fileConfig

# Import de moi model dang ky vao Base.metadata (autogenerate can thay het bang).
import app.models  # noqa: F401  (import-side-effect co chu dich)
from alembic import context
from app.config import settings
from app.db import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

# Lay connection string tu settings thay vi alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# VIEW nay tao bang op.execute() trong migration, khong phai bang model —
# loai khoi autogenerate de Tuan 2+ khong sinh lenh drop nham.
_AUTOGEN_SKIP_TABLES = {"school_track_stats"}


def _include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    return not (type_ == "table" and name in _AUTOGEN_SKIP_TABLES)


def run_migrations_offline() -> None:
    """Che do offline: chi can URL, sinh SQL ra stdout (khong ket noi DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
