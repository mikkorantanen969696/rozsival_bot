from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.db import dao
from app.db.models import CommissionEntry, Game, GameStatus, GameType, LedgerEntry, User
from app.keyboards.game import game_rematch_keyboard
from app.services.finance_service import FinanceService
from app.utils.timeouts import TIMEOUT_CHECK_INTERVAL


@dataclass
class DraftGame:
    opponent_username: str | None
    opponent_id: int | None = None
    game_type: GameType | None = None
    bet: float | None = None
    rounds_to_win: int | None = None

    def is_ready(self) -> bool:
        if self.game_type is None or self.rounds_to_win is None:
            return False
        if self.game_type == GameType.paid and self.bet is None:
            return False
        return True


class GameService:
    def __init__(self, session_factory, finance: FinanceService, config: Config):
        self._session_factory = session_factory
        self._finance = finance
        self._config = config
        self._drafts: dict[int, DraftGame] = {}
        self._rematch_votes: dict[int, set[int]] = {}
        self._bot: Bot | None = None

    def start_timeout_watcher(self, bot: Bot) -> None:
        self._bot = bot
        asyncio.create_task(self._timeout_loop())

    async def _timeout_loop(self) -> None:
        while True:
            await asyncio.sleep(TIMEOUT_CHECK_INTERVAL)
            async with self._session_factory() as session:
                games = await dao.get_active_games(session)
                now = datetime.utcnow()
                for game in games:
                    if game.status != GameStatus.active or not game.turn_deadline:
                        continue
                    if now >= game.turn_deadline:
                        await self._handle_timeout(session, game)

    async def _handle_timeout(self, session: AsyncSession, game: Game) -> None:
        if not game.current_turn_user_id:
            return
        winner_id = game.player1_id if game.current_turn_user_id == game.player2_id else game.player2_id
        await self.finish_game(session, game, winner_id, reason="timeout")
        if self._bot:
            await self._bot.send_message(
                game.chat_id,
                f"⏳ Turn timed out. Winner: <a href=\"tg://user?id={winner_id}\">Player</a> 🏆",
            )

    def get_draft(self, user_id: int) -> DraftGame | None:
        return self._drafts.get(user_id)

    def create_draft(self, user_id: int, opponent_username: str | None, opponent_id: int | None) -> DraftGame:
        draft = DraftGame(opponent_username=opponent_username, opponent_id=opponent_id)
        self._drafts[user_id] = draft
        return draft

    def clear_draft(self, user_id: int) -> None:
        self._drafts.pop(user_id, None)

    async def ensure_user(self, session: AsyncSession, user_id: int, username: str | None):
        return await self._finance.ensure_user(session, user_id, username)

    async def can_start_game(self, session: AsyncSession, user_id: int) -> bool:
        games = await dao.get_active_games_for_user(session, user_id)
        return len(games) < self._config.max_active_games_per_user

    async def create_game_from_draft(
        self,
        session: AsyncSession,
        chat_id: int,
        player1_id: int,
        player2_id: int,
        draft: DraftGame,
    ) -> Game:
        bet = draft.bet or 0
        return await dao.create_game(
            session=session,
            chat_id=chat_id,
            player1_id=player1_id,
            player2_id=player2_id,
            game_type=draft.game_type or GameType.free,
            bet=bet,
            rounds_to_win=draft.rounds_to_win or 1,
        )

    async def start_game(self, session: AsyncSession, game: Game) -> None:
        game.status = GameStatus.active
        game.current_turn_user_id = game.player1_id
        game.turn_deadline = datetime.utcnow() + timedelta(seconds=self._config.game_timeout_seconds)
        await session.commit()

    async def handle_roll(
        self, session: AsyncSession, game: Game, user_id: int, value: int
    ) -> tuple[str, bool, dict | None]:
        if game.last_roll_user_id is None:
            game.last_roll_user_id = user_id
            game.last_roll_value = value
            game.current_turn_user_id = game.player1_id if user_id == game.player2_id else game.player2_id
            game.turn_deadline = datetime.utcnow() + timedelta(seconds=self._config.game_timeout_seconds)
            await session.commit()
            return ("First roll accepted. Second player's turn. 🎲", False, {"phase": "first", "value": value})

        if game.last_roll_user_id == user_id:
            return ("It's the other player's turn. ⏳", False, None)

        first_value = game.last_roll_value or 0
        first_user_id = game.last_roll_user_id
        if value == first_value:
            game.last_roll_user_id = None
            game.last_roll_value = None
            game.current_turn_user_id = first_user_id
            game.turn_deadline = datetime.utcnow() + timedelta(seconds=self._config.game_timeout_seconds)
            await session.commit()
            return ("Round tie. Re-roll. 🎲", False, {"phase": "tie", "first": first_value, "second": value})

        winner_id = user_id if value > first_value else first_user_id

        if winner_id == game.player1_id:
            game.player1_score += 1
        else:
            game.player2_score += 1

        game.last_roll_user_id = None
        game.last_roll_value = None
        game.current_turn_user_id = winner_id
        game.turn_deadline = datetime.utcnow() + timedelta(seconds=self._config.game_timeout_seconds)
        await session.commit()

        finished = game.player1_score >= game.rounds_to_win or game.player2_score >= game.rounds_to_win
        return (
            "Round complete. ✅",
            finished,
            {"phase": "round", "first": first_value, "second": value, "winner_id": winner_id},
        )

    async def finish_game(self, session: AsyncSession, game: Game, winner_id: int, reason: str = "win") -> None:
        game.status = GameStatus.finished
        game.turn_deadline = None

        winner = await session.get(User, winner_id)
        if winner is None:
            await session.commit()
            return

        loser_id = game.player1_id if winner_id == game.player2_id else game.player2_id

        await session.execute(update(User).where(User.id == game.player1_id).values(total_games=User.total_games + 1))
        await session.execute(update(User).where(User.id == game.player2_id).values(total_games=User.total_games + 1))
        await session.execute(update(User).where(User.id == winner_id).values(wins=User.wins + 1))
        await session.execute(update(User).where(User.id == loser_id).values(losses=User.losses + 1))

        if game.type == GameType.paid and game.bet > 0:
            bet_value = Decimal(str(game.bet))
            prize = bet_value * Decimal("2")
            commission_rate = Decimal(str(self._config.commission_percent)) / Decimal("100")
            commission = prize * commission_rate
            payout = prize - commission
            commission_per_player = commission / Decimal("2")
            await session.execute(update(User).where(User.id == winner_id).values(balance=User.balance + float(payout)))
            session.add(LedgerEntry(user_id=winner_id, amount=float(payout), reason="payout", game_id=game.id))
            session.add(
                CommissionEntry(
                    user_id=game.player1_id,
                    game_id=game.id,
                    amount=float(commission_per_player),
                )
            )
            session.add(
                CommissionEntry(
                    user_id=game.player2_id,
                    game_id=game.id,
                    amount=float(commission_per_player),
                )
            )
            game.funds_locked = False

        await session.commit()

    async def cancel_game(self, session: AsyncSession, game_id: int) -> None:
        game = await session.get(Game, game_id)
        if not game or game.status == GameStatus.finished:
            return
        if game.type == GameType.paid and game.funds_locked and game.bet > 0:
            await session.execute(
                update(User).where(User.id == game.player1_id).values(balance=User.balance + float(game.bet))
            )
            await session.execute(
                update(User).where(User.id == game.player2_id).values(balance=User.balance + float(game.bet))
            )
            session.add(LedgerEntry(user_id=game.player1_id, amount=float(game.bet), reason="refund", game_id=game.id))
            session.add(LedgerEntry(user_id=game.player2_id, amount=float(game.bet), reason="refund", game_id=game.id))
            game.funds_locked = False
        game.status = GameStatus.cancelled
        await session.commit()

    async def rematch(self, session: AsyncSession, game: Game) -> Game:
        new_game = await dao.create_game(
            session,
            chat_id=game.chat_id,
            player1_id=game.player1_id,
            player2_id=game.player2_id,
            game_type=game.type,
            bet=game.bet,
            rounds_to_win=game.rounds_to_win,
        )
        return new_game

    def add_rematch_vote(self, game_id: int, user_id: int) -> int:
        votes = self._rematch_votes.setdefault(game_id, set())
        votes.add(user_id)
        return len(votes)

    def clear_rematch_votes(self, game_id: int) -> None:
        self._rematch_votes.pop(game_id, None)

    def make_rematch_keyboard(self, game_id: int) -> InlineKeyboardMarkup:
        return game_rematch_keyboard(game_id)
