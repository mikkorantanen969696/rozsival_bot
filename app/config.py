from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    database_url: str
    bot_token: str
    crypto_token: str
    admin_id: int
    commission_percent: float
    game_timeout_seconds: int
    max_active_games_per_user: int
    min_bet: float
    max_bet: float
    min_withdraw: float
    clear_db_on_start: bool


def _get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_database_url(database_url: str) -> str:
    sqlite_prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return database_url
    if not os.path.isdir("/data"):
        return database_url

    db_path = database_url[len(sqlite_prefix):]
    if not db_path or db_path.startswith("/"):
        return database_url

    normalized = db_path.replace("\\", "/").lstrip("./")
    if normalized.lower().startswith("data/"):
        normalized = normalized[5:]
    if not normalized:
        normalized = "gionta.db"

    target = (Path("/data") / normalized).as_posix()
    return f"{sqlite_prefix}{target}"


def load_config() -> Config:
    load_dotenv()

    default_db_url = "sqlite+aiosqlite:///./data/gionta.db"
    if os.path.isdir("/data"):
        default_db_url = "sqlite+aiosqlite:////data/gionta.db"
    database_url = os.getenv("DATABASE_URL", default_db_url).strip()
    database_url = _normalize_database_url(database_url)
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    crypto_token = os.getenv("CRYPTO_TOKEN", "").strip()

    if not bot_token or not crypto_token:
        raise RuntimeError("BOT_TOKEN and CRYPTO_TOKEN must be set")

    admin_id = int(os.getenv("ADMIN_ID", "0"))
    commission_percent = float(os.getenv("COMMISSION_PERCENT", os.getenv("COMMISSION", "0")))
    game_timeout_seconds = int(os.getenv("GAME_TIMEOUT_SECONDS", "30"))
    max_active_games_per_user = int(os.getenv("MAX_ACTIVE_GAMES_PER_USER", "1"))
    min_bet = float(os.getenv("MIN_BET", "1"))
    max_bet = float(os.getenv("MAX_BET", "1000"))
    min_withdraw = float(os.getenv("MIN_WITHDRAW", "1"))
    clear_db_on_start = _get_bool(os.getenv("CLEAR_DB_ON_START"))

    if admin_id <= 0:
        raise RuntimeError("ADMIN_ID must be set to a positive integer")

    return Config(
        database_url=database_url,
        bot_token=bot_token,
        crypto_token=crypto_token,
        admin_id=admin_id,
        commission_percent=commission_percent,
        game_timeout_seconds=game_timeout_seconds,
        max_active_games_per_user=max_active_games_per_user,
        min_bet=min_bet,
        max_bet=max_bet,
        min_withdraw=min_withdraw,
        clear_db_on_start=clear_db_on_start,
    )
