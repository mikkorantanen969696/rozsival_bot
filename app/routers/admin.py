from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import Config
from app.db import dao
from app.db.models import Game, WithdrawalStatus
from app.i18n import get_lang, t
from app.services.finance_service import FinanceService
from app.services.game_service import GameService

router = Router()
router.callback_query.filter(F.message.chat.type == "private")


def _is_admin(callback: CallbackQuery, config: Config) -> bool:
    return callback.from_user and callback.from_user.id == config.admin_id


def _admin_keyboard(lang: str):
    is_ru = lang == "ru"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Active games 🕹️" if not is_ru else "Активные игры 🕹️", callback_data="admin:active")],
            [InlineKeyboardButton(text="System stats 📈" if not is_ru else "Системные метрики 📈", callback_data="admin:stats")],
            [InlineKeyboardButton(text="Average bet 🎲" if not is_ru else "Средняя ставка 🎲", callback_data="admin:avg_bet")],
            [InlineKeyboardButton(text="Available to withdraw 💸" if not is_ru else "Доступно к выводу 💸", callback_data="admin:available")],
            [InlineKeyboardButton(text="Ledger 📒" if not is_ru else "Леджер 📒", callback_data="admin:ledger")],
            [InlineKeyboardButton(text="Withdrawals 💸" if not is_ru else "Выводы 💸", callback_data="admin:withdrawals")],
            [InlineKeyboardButton(text="Referral structure 👥" if not is_ru else "Реф. структура 👥", callback_data="admin:ref_metrics")],
        ]
    )


def _stop_keyboard(game_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Stop 🛑", callback_data=f"admin:stop:{game_id}")],
        ]
    )


def _withdrawal_keyboard(withdrawal_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Approve ✅", callback_data=f"admin:wd:approve:{withdrawal_id}"),
                InlineKeyboardButton(text="Reject ❌", callback_data=f"admin:wd:reject:{withdrawal_id}"),
            ],
        ]
    )

def _chunk_lines(lines: list[str], limit: int = 3500) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + (1 if current else 0)
        if current and current_len + line_len > limit:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
            continue
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks

@router.callback_query(F.data == "dm:admin")
async def admin_panel(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer(t("access_denied", "en"))
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.message.answer(t("admin_panel", lang), reply_markup=_admin_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "admin:active")
async def admin_active(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    games = await dao.get_active_games(session)
    if not games:
        await callback.message.answer("No active games. 💤" if lang == "en" else "Нет активных игр. 💤")
        await callback.answer()
        return

    await callback.message.answer("Active games (tap to stop): 🧯" if lang == "en" else "Активные игры (нажмите для остановки): 🧯")
    for game in games:
        await callback.message.answer(
            f"#{game.id} {game.player1_id} vs {game.player2_id} [{game.status.value}]",
            reply_markup=_stop_keyboard(game.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:stop:"))
async def admin_stop(callback: CallbackQuery, session, config: Config, games: GameService):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    game_id = int(callback.data.split(":")[-1])
    game = await session.get(Game, game_id)
    if not game:
        await callback.answer("Game not found. ❌" if lang == "en" else "Игра не найдена. ❌")
        return
    await games.cancel_game(session, game_id)
    await callback.message.answer(
        f"Game #{game_id} stopped (soft cancel). 🛑"
        if lang == "en"
        else f"Игра #{game_id} остановлена (мягкая отмена). 🛑"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    balance, users_count = await dao.get_system_balance_and_users(session)
    text = (
        f"System balance: {balance:.2f} USDT 💰\nUsers: {users_count} 👥"
        if lang == "en"
        else f"Системный баланс: {balance:.2f} USDT 💰\nПользователей: {users_count} 👥"
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:avg_bet")
async def admin_avg_bet(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    avg_bet = await dao.get_avg_bet(session)
    await callback.message.answer(
        f"Average bet: {avg_bet:.2f} USDT 🎲" if lang == "en" else f"Средняя ставка: {avg_bet:.2f} USDT 🎲"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:available")
async def admin_available(callback: CallbackQuery, session, config: Config, finance: FinanceService):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    system_balance, _ = await dao.get_system_balance_and_users(session)
    app_balance = await finance.get_app_balance_usdt()
    available = max(Decimal("0"), app_balance - Decimal(str(system_balance)))
    if lang == "en":
        text = (
            f"App balance (CryptoBot): {app_balance:.2f} USDT 🏦\n"
            f"Players balance: {system_balance:.2f} USDT 💰\n"
            f"Available to withdraw: {available:.2f} USDT 💸"
        )
    else:
        text = (
            f"Баланс приложения (CryptoBot): {app_balance:.2f} USDT 🏦\n"
            f"Баланс игроков: {system_balance:.2f} USDT 💰\n"
            f"Доступно к выводу: {available:.2f} USDT 💸"
        )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:ledger")
async def admin_ledger(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    entries = await dao.get_recent_ledger(session, limit=20)
    if not entries:
        await callback.message.answer("Ledger is empty. 📭" if lang == "en" else "Леджер пуст. 📭")
        await callback.answer()
        return
    lines = ["Recent operations 📒:" if lang == "en" else "Последние операции 📒:"]
    for e in entries:
        lines.append(f"#{e.id} user={e.user_id} {e.amount:+.2f} {e.reason} game={e.game_id or '-'}")
    for chunk in _chunk_lines(lines):
        await callback.message.answer(chunk)
    await callback.answer()


@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    withdrawals = await dao.list_recent_withdrawals(session, limit=20)
    if not withdrawals:
        await callback.message.answer("No withdrawals found. 📭" if lang == "en" else "Выводы не найдены. 📭")
        await callback.answer()
        return
    await callback.message.answer("Recent withdrawals:" if lang == "en" else "Последние выводы:")
    for w in withdrawals:
        status = w.status.value
        text = f"#{w.id} user={w.user_id} amount={float(w.amount):.2f} USDT status={status}"
        if status == "approved":
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Refund ♻️", callback_data=f"admin:wd:refund:{w.id}")],
                ]
            )
        else:
            kb = None
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin:ref_metrics")
async def admin_ref_metrics(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    structure = await dao.get_referral_structure(session)
    if not structure:
        await callback.message.answer(
            "No referral data yet. 📭" if lang == "en" else "Данных по рефералам пока нет. 📭"
        )
        await callback.answer()
        return

    header = "Referral structure 👥:" if lang == "en" else "Реферальная структура 👥:"
    lines = [header]
    for referrer_id, referrer_username, referred_id, referred_username, commission_sum in structure:
        referrer_name = f"@{referrer_username}" if referrer_username else str(referrer_id)
        referred_name = f"@{referred_username}" if referred_username else str(referred_id)
        if lang == "en":
            lines.append(
                f"{referrer_name} (id={referrer_id}) -> {referred_name} (id={referred_id}) | brought: {commission_sum:.2f} USDT"
            )
        else:
            lines.append(
                f"{referrer_name} (id={referrer_id}) -> {referred_name} (id={referred_id}) | принес: {commission_sum:.2f} USDT"
            )
    for chunk in _chunk_lines(lines):
        await callback.message.answer(chunk)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:wd:approve:"))
async def admin_withdraw_approve(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.answer(
        "Manual approval is disabled. Withdrawals are auto-processed."
        if lang == "en"
        else "Ручное подтверждение отключено. Выводы обрабатываются автоматически."
    )


@router.callback_query(F.data.startswith("admin:wd:reject:"))
async def admin_withdraw_reject(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.answer(
        "Manual rejection is disabled. Withdrawals are auto-processed."
        if lang == "en"
        else "Ручное отклонение отключено. Выводы обрабатываются автоматически."
    )


@router.callback_query(F.data.startswith("admin:wd:refund:"))
async def admin_withdraw_refund(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. 🚫")
        return
    lang = await get_lang(session, callback.from_user.id)
    withdrawal_id = int(callback.data.split(":")[-1])
    withdrawal = await dao.get_withdrawal(session, withdrawal_id)
    if not withdrawal:
        await callback.answer("Withdrawal not found. ❌" if lang == "en" else "Вывод не найден. ❌")
        return
    if withdrawal.status != WithdrawalStatus.approved:
        await callback.answer(
            "Only approved withdrawals can be refunded. ⛔"
            if lang == "en"
            else "Возврат доступен только для подтвержденных выводов. ⛔"
        )
        return
    await dao.set_withdrawal_status(session, withdrawal_id, WithdrawalStatus.refunded, datetime.utcnow())
    await dao.update_user_balance(session, withdrawal.user_id, withdrawal.amount)
    await dao.add_ledger_entry(session, withdrawal.user_id, withdrawal.amount, "withdraw_refund", None)
    await callback.message.answer(
        f"Withdrawal #{withdrawal_id} refunded. ♻️" if lang == "en" else f"Вывод #{withdrawal_id} возвращен. ♻️"
    )
    await callback.answer()


