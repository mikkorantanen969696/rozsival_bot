from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import CallbackQuery, Message, MessageEntity
from sqlalchemy import select, update

from app.config import Config
from app.db import dao
from app.db.models import Game, GameStatus, GameType, LedgerEntry, User
from app.keyboards.game import (
    cancel_existing_game_keyboard,
    challenge_keyboard,
    draft_bet_keyboard,
    draft_confirm_keyboard,
    draft_rounds_keyboard,
    draft_type_keyboard,
)
from app.services.game_service import GameService
from app.utils.validators import validate_bet

router = Router()
router.message.filter(F.chat.type.in_({"group", "supergroup"}))
router.callback_query.filter(F.message.chat.type.in_({"group", "supergroup"}))
logger = logging.getLogger(__name__)


def _parse_username(text: str) -> str | None:
    parts = text.split()
    if len(parts) < 2:
        return None
    username = parts[1].strip()
    if not username.startswith("@"):
        return None
    return username


def _extract_text_mention(message: Message) -> int | None:
    if not message.entities:
        return None
    for entity in message.entities:
        if entity.type == "text_mention" and entity.user:
            return entity.user.id
    return None


def _format_user(user) -> str:
    username = getattr(user, "username", None)
    if username:
        return f"@{username}"
    full_name = getattr(user, "full_name", "player")
    user_id = getattr(user, "id", None)
    if user_id:
        return f"<a href=\"tg://user?id={user_id}\">{full_name}</a>"
    return "player"


async def _get_active_game_for_user(session, chat_id: int, user_id: int) -> Game | None:
    stmt = select(Game).where(
        Game.chat_id == chat_id,
        Game.status == GameStatus.active,
        (Game.player1_id == user_id) | (Game.player2_id == user_id),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _handle_game_command(message: Message, command: CommandObject, session, games: GameService, config: Config):
    logger.info("game cmd: chat=%s type=%s text=%r", message.chat.id, message.chat.type, message.text)
    if not message.from_user:
        await message.reply("Commands from anonymous admins are not supported. Send from your own account. 🙈")
        return

    reply_user = message.reply_to_message.from_user if message.reply_to_message else None
    mention_id = _extract_text_mention(message)

    raw_args = (command.args or "").strip()
    username = _parse_username(f"/game {raw_args}")

    if reply_user and reply_user.id == message.from_user.id:
        await message.answer("You can't play with yourself. 🙅")
        return

    if username and message.from_user.username and f"@{message.from_user.username}" == username:
        await message.answer("You can't play with yourself. 🙅")
        return

    opponent_id = reply_user.id if reply_user else mention_id
    if not username and not opponent_id:
        await message.answer("Usage: /game @username or reply to your opponent's message. ℹ️")
        return

    can_start = await games.can_start_game(session, message.from_user.id)
    if not can_start:
        active_games = await dao.get_active_games_for_user(session, message.from_user.id)
        if active_games:
            await message.answer(
                "You already have an active game. Cancel it? 🧹",
                reply_markup=cancel_existing_game_keyboard(active_games[0].id),
            )
        return

    await games.create_draft(session, message.from_user.id, username, opponent_id)
    await message.answer("Choose a game type 🎮:", reply_markup=draft_type_keyboard())


@router.message(Command("game", ignore_case=True, ignore_mention=True))
async def game_start(message: Message, command: CommandObject, session, games: GameService, config: Config):
    await _handle_game_command(message, command, session, games, config)


@router.message(F.entities)
async def debug_any_command(message: Message):
    if not message.entities:
        return
    if any(entity.type == "bot_command" for entity in message.entities):
        logger.info("bot_command entity: chat=%s text=%r entities=%r", message.chat.id, message.text, message.entities)


@router.callback_query(F.data.startswith("draft:"))
async def draft_update(callback: CallbackQuery, session, games: GameService, config: Config):
    if not callback.from_user:
        return

    draft = await games.get_draft(session, callback.from_user.id)
    if not draft:
        await callback.answer("Draft not found. 📝")
        return

    parts = callback.data.split(":", 2)
    action = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""

    if action == "type":
        draft.game_type = GameType(value)
        await games.save_draft(session, callback.from_user.id, draft)
        await callback.message.answer("Type selected. Choose rounds 🎯:", reply_markup=draft_rounds_keyboard())
    elif action == "rounds":
        rounds_value = int(value)
        draft.rounds_to_win = rounds_value
        await games.save_draft(session, callback.from_user.id, draft)
        if draft.game_type == GameType.paid:
            await callback.message.answer("Choose a bet 💵:", reply_markup=draft_bet_keyboard())
        else:
            await callback.message.answer("Ready. Send challenge? 🚀", reply_markup=draft_confirm_keyboard())
    elif action == "bet":
        draft.bet = Decimal(value)
        await games.save_draft(session, callback.from_user.id, draft)
        await callback.message.answer("Ready. Send challenge? 🚀", reply_markup=draft_confirm_keyboard())
    elif action == "send":
        if not draft.is_ready():
            await callback.answer("Fill in all parameters. ✍️")
            return

        if draft.game_type == GameType.paid:
            ok, error, bet_value = validate_bet(str(draft.bet or ""), config)
            if not ok or bet_value is None:
                await callback.message.answer(error or "Invalid bet. ❗")
                await callback.answer()
                return
            draft.bet = bet_value

        opponent_chat = None
        if draft.opponent_id:
            try:
                member = await callback.bot.get_chat_member(callback.message.chat.id, draft.opponent_id)
                opponent_chat = member.user
            except Exception:
                opponent_chat = None
        if opponent_chat is None:
            opponent_username = draft.opponent_username
            try:
                opponent_chat = await callback.bot.get_chat(opponent_username)
            except Exception:
                await callback.message.answer(
                    "Could not find the player by @username. "
                    "Ask them to open DM with the bot and send /start, "
                    "or challenge them by replying to their message. 🧭"
                )
                await games.clear_draft(session, callback.from_user.id)
                await callback.answer()
                return

        if opponent_chat.id == callback.from_user.id:
            await callback.message.answer("You can't play with yourself. 🙅")
            await games.clear_draft(session, callback.from_user.id)
            await callback.answer()
            return

        await games.ensure_user(session, callback.from_user.id, callback.from_user.username)
        await games.ensure_user(session, opponent_chat.id, getattr(opponent_chat, "username", None))

        can_start_opponent = await games.can_start_game(session, opponent_chat.id)
        if not can_start_opponent:
            await callback.message.answer("Your opponent already has an active game. ⛔")
            await games.clear_draft(session, callback.from_user.id)
            await callback.answer()
            return

        game = await games.create_game_from_draft(
            session,
            chat_id=callback.message.chat.id,
            player1_id=callback.from_user.id,
            player2_id=opponent_chat.id,
            draft=draft,
        )
        await games.clear_draft(session, callback.from_user.id)
        opponent_name = opponent_chat.username or opponent_chat.full_name or "player"
        opponent_mention = f"<a href=\"tg://user?id={opponent_chat.id}\">{opponent_name}</a>"
        initiator = _format_user(callback.from_user)
        opponent = _format_user(opponent_chat)
        await callback.message.answer(
            f"Challenge from {initiator} to {opponent}. ⚔️",
            reply_markup=challenge_keyboard(game.id),
        )
    elif action == "cancel":
        await games.clear_draft(session, callback.from_user.id)
        await callback.message.answer("Draft canceled. 🧹")

    await callback.answer()




@router.callback_query(F.data.startswith("game:accept:"))
async def game_accept(callback: CallbackQuery, session, games: GameService, config: Config):
    game_id = int(callback.data.split(":")[-1])
    game = await session.get(Game, game_id)
    if not game or game.status != GameStatus.pending:
        await callback.answer("Game not found. ❓")
        return

    if callback.from_user.id != game.player2_id:
        await callback.answer("You are not invited to this game. 🚫")
        return

    p1_games = await dao.get_active_games_for_user(session, game.player1_id)
    if any(existing.id != game.id for existing in p1_games):
        await callback.message.answer("Your opponent already has an active game. ⛔")
        await callback.answer()
        return

    p2_games = await dao.get_active_games_for_user(session, game.player2_id)
    if any(existing.id != game.id for existing in p2_games):
        await callback.message.answer("You already have an active game. ⛔")
        await callback.answer()
        return

    activate_stmt = (
        update(Game)
        .where(Game.id == game.id, Game.status == GameStatus.pending)
        .values(
            status=GameStatus.active,
            current_turn_user_id=game.player1_id,
            turn_deadline=datetime.utcnow() + timedelta(seconds=config.game_timeout_seconds),
        )
    )
    activate_result = await session.execute(activate_stmt)
    if activate_result.rowcount != 1:
        await session.rollback()
        await callback.answer("Game is already processed. ❗")
        return

    if game.type == GameType.paid:
        lock_p1 = await session.execute(
            update(User)
            .where(User.id == game.player1_id, User.balance >= game.bet)
            .values(balance=User.balance - game.bet)
        )
        lock_p2 = await session.execute(
            update(User)
            .where(User.id == game.player2_id, User.balance >= game.bet)
            .values(balance=User.balance - game.bet)
        )
        if lock_p1.rowcount != 1 or lock_p2.rowcount != 1:
            await session.rollback()
            p1_balance = await dao.get_user_balance(session, game.player1_id)
            p2_balance = await dao.get_user_balance(session, game.player2_id)
            await callback.message.answer("Insufficient funds. Check DM. 💸")
            if p1_balance < game.bet:
                need = game.bet - p1_balance
                await callback.bot.send_message(
                    game.player1_id,
                    f"Insufficient funds for the game. Top up at least {need:.2f} USDT. 💳",
                )
            if p2_balance < game.bet:
                need = game.bet - p2_balance
                await callback.bot.send_message(
                    game.player2_id,
                    f"Insufficient funds for the game. Top up at least {need:.2f} USDT. 💳",
                )
            await callback.answer()
            return

        session.add(LedgerEntry(user_id=game.player1_id, amount=-game.bet, reason="bet_lock", game_id=game.id))
        session.add(LedgerEntry(user_id=game.player2_id, amount=-game.bet, reason="bet_lock", game_id=game.id))
        game.funds_locked = True

    await session.commit()
    await callback.message.answer(
        f"Game started! <a href=\"tg://user?id={game.player1_id}\">Player</a> to move. 🎲"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("game:decline:"))
async def game_decline(callback: CallbackQuery, session):
    game_id = int(callback.data.split(":")[-1])
    game = await session.get(Game, game_id)
    if not game or game.status != GameStatus.pending:
        await callback.answer()
        return
    if callback.from_user.id != game.player2_id:
        await callback.answer("You are not invited to this game. 🚫")
        return

    game.status = GameStatus.cancelled
    await session.commit()
    await callback.message.answer("Challenge declined. ❌")
    await callback.answer()


@router.callback_query(F.data.startswith("game:cancel:"))
async def game_cancel(callback: CallbackQuery, session, games: GameService):
    game_id = int(callback.data.split(":")[-1])
    game = await session.get(Game, game_id)
    if not game or callback.from_user.id not in {game.player1_id, game.player2_id}:
        await callback.answer("Access denied. 🚫")
        return
    await games.cancel_game(session, game_id)
    await callback.message.answer("Game canceled. 🧹")
    await callback.answer()


@router.message(F.dice)
async def game_dice(message: Message, session, games: GameService):
    if not message.from_user:
        await message.reply("Message has no author. Disable anonymous admin mode. 🙈")
        return
    if not message.dice or message.dice.emoji != "🎲":
        return

    try:
        game = await _get_active_game_for_user(session, message.chat.id, message.from_user.id)
        if not game:
            logger.info("dice ignored: no active game for user=%s chat=%s", message.from_user.id, message.chat.id)
            return

        rounds_to_win = max(1, game.rounds_to_win or 1)
        if game.player1_score >= rounds_to_win or game.player2_score >= rounds_to_win:
            winner_id = game.player1_id if game.player1_score >= game.player2_score else game.player2_id
            await games.finish_game(session, game, winner_id)
            await message.answer(
                f"Game over! Winner: <a href=\"tg://user?id={winner_id}\">Player</a> 🏆\n"
                f"Score: {game.player1_score}:{game.player2_score} 📊",
                reply_markup=games.make_rematch_keyboard(game.id),
            )
            return

        if game.current_turn_user_id != message.from_user.id:
            await message.reply("It's the other player's turn. ⏳")
            return

        text, finished, info = await games.handle_roll(session, game, message.from_user.id, message.dice.value)
        await asyncio.sleep(2)
        if info and info.get("phase") == "first":
            await message.reply(f"{text}\nRolled: {info['value']} 🎲")
        elif info and info.get("phase") == "tie":
            await message.reply(f"{text}\nRolls: {info['first']} and {info['second']} 🎲")
        elif info and info.get("phase") == "round":
            await message.reply(
                f"{text}\nRolls: {info['first']} and {info['second']} 🎲\n"
                f"Score: {game.player1_score}:{game.player2_score} 📊"
            )
        else:
            await message.reply(text)

        if finished:
            winner_id = (
                info.get("winner_id")
                if info and info.get("winner_id")
                else (game.player1_id if game.player1_score > game.player2_score else game.player2_id)
            )
            await games.finish_game(session, game, winner_id)
            await message.answer(
                f"Game over! Winner: <a href=\"tg://user?id={winner_id}\">Player</a> 🏆\n"
                f"Score: {game.player1_score}:{game.player2_score} 📊",
                reply_markup=games.make_rematch_keyboard(game.id),
            )
    except Exception:
        logger.exception("dice handler error: chat=%s user=%s", message.chat.id, message.from_user.id)


@router.edited_message(F.dice)
async def edited_dice(message: Message, session, games: GameService):
    if not message.from_user:
        await message.reply("Message has no author. Disable anonymous admin mode. 🙈")
        return

    game = await _get_active_game_for_user(session, message.chat.id, message.from_user.id)
    if not game or game.status != GameStatus.active:
        return

    winner_id = game.player1_id if message.from_user.id == game.player2_id else game.player2_id
    await games.finish_game(session, game, winner_id, reason="edited")
    await message.answer(
        f"⚠️ Roll edit detected. Winner: <a href=\"tg://user?id={winner_id}\">Player</a> 🕵️",
        reply_markup=games.make_rematch_keyboard(game.id),
    )


@router.callback_query(F.data.startswith("game:rematch:"))
async def game_rematch(callback: CallbackQuery, session, games: GameService):
    game_id = int(callback.data.split(":")[-1])
    game = await session.get(Game, game_id)
    if not game or game.status != GameStatus.finished:
        await callback.answer("Game not found. ❓")
        return

    if callback.from_user.id not in {game.player1_id, game.player2_id}:
        await callback.answer("You are not a participant in this game. 🚫")
        return

    votes = await games.add_rematch_vote(session, game_id, callback.from_user.id)
    if votes < 2:
        await callback.answer("Waiting for the second player. ⏳")
        return

    await games.clear_rematch_votes(session, game_id)
    new_game = await games.rematch(session, game)
    await callback.message.answer(
        "Rematch! Tap accept 🔁:",
        reply_markup=challenge_keyboard(new_game.id),
    )
    await callback.answer()
