"""Alembic environment (async). Reads DATABASE_URL from Eyohe settings."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from eyohe.core.config import get_settings
from eyohe.core.db import Base
from eyohe.models import *  # noqa: F403 - register all tables

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite+aiosqlite:///") and not url.startswith("sqlite+aiosqlite:////"):
        from eyohe.core.config import REPO_ROOT

        path = url.split("///", 1)[1]
        if not path.startswith(":memory:"):
            p = (REPO_ROOT / path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite+aiosqlite:///{p}"
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Render custom column types as their portable SQLAlchemy equivalents."""
    from eyohe.core.db import UTCDateTime

    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _url()
    connectable = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
