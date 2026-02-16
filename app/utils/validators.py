from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.config import Config


def validate_bet(amount: str, config: Config) -> tuple[bool, str | None, Decimal | None]:
    try:
        value = Decimal(amount)
    except (InvalidOperation, ValueError):
        return False, "Bet must be a number. 🔢", None

    if value < config.min_bet:
        return False, f"Minimum bet is {config.min_bet}. 📉", None
    if value > config.max_bet:
        return False, f"Maximum bet is {config.max_bet}. 📈", None

    return True, None, value
