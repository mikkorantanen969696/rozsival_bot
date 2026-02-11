from __future__ import annotations
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.db.base import Base


def create_engine_and_session(database_url: str):
    if database_url.startswith("sqlite+aiosqlite:///"):
        db_path = database_url.replace("sqlite+aiosqlite:///", "", 1)
        db_file = Path(db_path)
        if str(db_file.parent) not in {"", "."}:
            db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        dialect = conn.engine.dialect.name
        if dialect == "sqlite":
            await _sqlite_migrations(conn)
        else:
            await _postgres_migrations(conn)


async def clear_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        dialect = conn.engine.dialect.name
        if dialect == "sqlite":
            await conn.execute(text("DELETE FROM commission_entries"))
            await conn.execute(text("DELETE FROM withdrawals"))
            await conn.execute(text("DELETE FROM ledger"))
            await conn.execute(text("DELETE FROM transactions"))
            await conn.execute(text("DELETE FROM games"))
            await conn.execute(text("DELETE FROM users"))
        else:
            await conn.execute(
                text(
                    "TRUNCATE TABLE commission_entries, withdrawals, ledger, games, transactions, users "
                    "RESTART IDENTITY CASCADE"
                )
            )


async def _postgres_migrations(conn: Any) -> None:
    await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS funds_locked BOOLEAN DEFAULT FALSE"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(3) DEFAULT 'en'"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT NULL"))
    await conn.execute(text("ALTER TABLE IF EXISTS withdrawals ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP NULL"))
    await conn.execute(text("ALTER TABLE IF EXISTS withdrawals ADD COLUMN IF NOT EXISTS asset VARCHAR(10) DEFAULT 'USDT'"))
    await conn.execute(text("ALTER TABLE IF EXISTS withdrawals ADD COLUMN IF NOT EXISTS spend_id VARCHAR(64) NULL"))
    await conn.execute(text("ALTER TABLE IF EXISTS withdrawals ADD COLUMN IF NOT EXISTS transfer_id INTEGER NULL"))
    await conn.execute(text("ALTER TABLE IF EXISTS withdrawals ADD COLUMN IF NOT EXISTS error VARCHAR(255) NULL"))


async def _sqlite_migrations(conn: Any) -> None:
    user_columns = await _get_sqlite_columns(conn, "users")
    if "language" not in user_columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN language VARCHAR(3) DEFAULT 'en'"))
    if "referred_by" not in user_columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN referred_by BIGINT NULL"))

    game_columns = await _get_sqlite_columns(conn, "games")
    if "funds_locked" not in game_columns:
        await conn.execute(text("ALTER TABLE games ADD COLUMN funds_locked BOOLEAN DEFAULT FALSE"))

    wd_columns = await _get_sqlite_columns(conn, "withdrawals")
    if "processed_at" not in wd_columns:
        await conn.execute(text("ALTER TABLE withdrawals ADD COLUMN processed_at TIMESTAMP NULL"))
    if "asset" not in wd_columns:
        await conn.execute(text("ALTER TABLE withdrawals ADD COLUMN asset VARCHAR(10) DEFAULT 'USDT'"))
    if "spend_id" not in wd_columns:
        await conn.execute(text("ALTER TABLE withdrawals ADD COLUMN spend_id VARCHAR(64) NULL"))
    if "transfer_id" not in wd_columns:
        await conn.execute(text("ALTER TABLE withdrawals ADD COLUMN transfer_id INTEGER NULL"))
    if "error" not in wd_columns:
        await conn.execute(text("ALTER TABLE withdrawals ADD COLUMN error VARCHAR(255) NULL"))


async def _get_sqlite_columns(conn: Any, table_name: str) -> set[str]:
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {str(row[1]) for row in result.all()}
