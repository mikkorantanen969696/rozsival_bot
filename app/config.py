from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    app_env: str
    database_url: str
    bot_token: str
    crypto_token: str
    admin_id: int
    commission_percent: Decimal
    game_timeout_seconds: int
    max_active_games_per_user: int
    min_bet: Decimal
    max_bet: Decimal
    min_withdraw: Decimal
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
    app_env = os.getenv("APP_ENV", "production").strip().lower()
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    crypto_token = os.getenv("CRYPTO_TOKEN", "").strip()

    if not bot_token or not crypto_token:
        raise RuntimeError("BOT_TOKEN and CRYPTO_TOKEN must be set")

    admin_id = int(os.getenv("ADMIN_ID", "0"))
    try:
        commission_percent = Decimal(os.getenv("COMMISSION_PERCENT", os.getenv("COMMISSION", "0")).strip())
        min_bet = Decimal(os.getenv("MIN_BET", "1").strip())
        max_bet = Decimal(os.getenv("MAX_BET", "1000").strip())
        min_withdraw = Decimal(os.getenv("MIN_WITHDRAW", "1").strip())
    except (InvalidOperation, AttributeError):
        raise RuntimeError("COMMISSION_PERCENT, MIN_BET, MAX_BET and MIN_WITHDRAW must be valid numbers")

    game_timeout_seconds = int(os.getenv("GAME_TIMEOUT_SECONDS", "30"))
    max_active_games_per_user = int(os.getenv("MAX_ACTIVE_GAMES_PER_USER", "1"))
    clear_db_on_start = _get_bool(os.getenv("CLEAR_DB_ON_START"))

    if admin_id <= 0:
        raise RuntimeError("ADMIN_ID must be set to a positive integer")
    if commission_percent < 0 or commission_percent > 100:
        raise RuntimeError("COMMISSION_PERCENT must be between 0 and 100")
    if min_bet <= 0 or max_bet <= 0 or min_bet > max_bet:
        raise RuntimeError("MIN_BET and MAX_BET must be positive and MIN_BET <= MAX_BET")
    if min_withdraw <= 0:
        raise RuntimeError("MIN_WITHDRAW must be positive")
    if game_timeout_seconds <= 0:
        raise RuntimeError("GAME_TIMEOUT_SECONDS must be a positive integer")
    if max_active_games_per_user <= 0:
        raise RuntimeError("MAX_ACTIVE_GAMES_PER_USER must be a positive integer")

    return Config(
        app_env=app_env,
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
