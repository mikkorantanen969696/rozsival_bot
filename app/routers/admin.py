from __future__ import annotations

from datetime import datetime

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
            [InlineKeyboardButton(text="Active games рџ•№пёЏ" if not is_ru else "РђРєС‚РёРІРЅС‹Рµ РёРіСЂС‹ рџ•№пёЏ", callback_data="admin:active")],
            [InlineKeyboardButton(text="System stats рџ“€" if not is_ru else "РЎРёСЃС‚РµРјРЅС‹Рµ РјРµС‚СЂРёРєРё рџ“€", callback_data="admin:stats")],
            [InlineKeyboardButton(text="Average bet рџЋІ" if not is_ru else "РЎСЂРµРґРЅСЏСЏ СЃС‚Р°РІРєР° рџЋІ", callback_data="admin:avg_bet")],
            [InlineKeyboardButton(text="Available to withdraw рџ’ё" if not is_ru else "Р”РѕСЃС‚СѓРїРЅРѕ Рє РІС‹РІРѕРґСѓ рџ’ё", callback_data="admin:available")],
            [InlineKeyboardButton(text="Ledger рџ“’" if not is_ru else "Р›РµРґР¶РµСЂ рџ“’", callback_data="admin:ledger")],
            [InlineKeyboardButton(text="Withdrawals рџ’ё" if not is_ru else "Р’С‹РІРѕРґС‹ рџ’ё", callback_data="admin:withdrawals")],
            [InlineKeyboardButton(text="Referral structure рџ‘Ґ" if not is_ru else "Р РµС„. СЃС‚СЂСѓРєС‚СѓСЂР° рџ‘Ґ", callback_data="admin:ref_metrics")],
        ]
    )


def _stop_keyboard(game_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Stop рџ›‘", callback_data=f"admin:stop:{game_id}")],
        ]
    )


def _withdrawal_keyboard(withdrawal_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Approve вњ…", callback_data=f"admin:wd:approve:{withdrawal_id}"),
                InlineKeyboardButton(text="Reject вќЊ", callback_data=f"admin:wd:reject:{withdrawal_id}"),
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
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    games = await dao.get_active_games(session)
    if not games:
        await callback.message.answer("No active games. рџ’¤" if lang == "en" else "РќРµС‚ Р°РєС‚РёРІРЅС‹С… РёРіСЂ. рџ’¤")
        await callback.answer()
        return

    await callback.message.answer("Active games (tap to stop): рџ§Ї" if lang == "en" else "РђРєС‚РёРІРЅС‹Рµ РёРіСЂС‹ (РЅР°Р¶РјРёС‚Рµ РґР»СЏ РѕСЃС‚Р°РЅРѕРІРєРё): рџ§Ї")
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
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    game_id = int(callback.data.split(":")[-1])
    game = await session.get(Game, game_id)
    if not game:
        await callback.answer("Game not found. вќ“" if lang == "en" else "РРіСЂР° РЅРµ РЅР°Р№РґРµРЅР°. вќ“")
        return
    await games.cancel_game(session, game_id)
    await callback.message.answer(
        f"Game #{game_id} stopped (soft cancel). рџ›‘"
        if lang == "en"
        else f"РРіСЂР° #{game_id} РѕСЃС‚Р°РЅРѕРІР»РµРЅР° (РјСЏРіРєР°СЏ РѕС‚РјРµРЅР°). рџ›‘"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    balance, users_count = await dao.get_system_balance_and_users(session)
    text = (
        f"System balance: {balance:.2f} USDT рџ’°\nUsers: {users_count} рџ‘Ґ"
        if lang == "en"
        else f"РЎРёСЃС‚РµРјРЅС‹Р№ Р±Р°Р»Р°РЅСЃ: {balance:.2f} USDT рџ’°\nРџРѕР»СЊР·РѕРІР°С‚РµР»РµР№: {users_count} рџ‘Ґ"
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:avg_bet")
async def admin_avg_bet(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    avg_bet = await dao.get_avg_bet(session)
    await callback.message.answer(
        f"Average bet: {avg_bet:.2f} USDT рџЋІ" if lang == "en" else f"РЎСЂРµРґРЅСЏСЏ СЃС‚Р°РІРєР°: {avg_bet:.2f} USDT рџЋІ"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:available")
async def admin_available(callback: CallbackQuery, session, config: Config, finance: FinanceService):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    system_balance, _ = await dao.get_system_balance_and_users(session)
    app_balance = await finance.get_app_balance_usdt()
    available = max(0.0, app_balance - system_balance)
    if lang == "en":
        text = (
            f"App balance (CryptoBot): {app_balance:.2f} USDT рџЏ¦\n"
            f"Players balance: {system_balance:.2f} USDT рџ’°\n"
            f"Available to withdraw: {available:.2f} USDT рџ’ё"
        )
    else:
        text = (
            f"Р‘Р°Р»Р°РЅСЃ РїСЂРёР»РѕР¶РµРЅРёСЏ (CryptoBot): {app_balance:.2f} USDT рџЏ¦\n"
            f"Р‘Р°Р»Р°РЅСЃ РёРіСЂРѕРєРѕРІ: {system_balance:.2f} USDT рџ’°\n"
            f"Р”РѕСЃС‚СѓРїРЅРѕ Рє РІС‹РІРѕРґСѓ: {available:.2f} USDT рџ’ё"
        )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:ledger")
async def admin_ledger(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    entries = await dao.get_recent_ledger(session, limit=20)
    if not entries:
        await callback.message.answer("Ledger is empty. рџ“­" if lang == "en" else "Р›РµРґР¶РµСЂ РїСѓСЃС‚. рџ“­")
        await callback.answer()
        return
    lines = ["Recent operations рџ“’:" if lang == "en" else "РџРѕСЃР»РµРґРЅРёРµ РѕРїРµСЂР°С†РёРё рџ“’:"]
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
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    withdrawals = await dao.list_recent_withdrawals(session, limit=20)
    if not withdrawals:
        await callback.message.answer("No withdrawals found. рџ“­" if lang == "en" else "Р’С‹РІРѕРґС‹ РЅРµ РЅР°Р№РґРµРЅС‹. рџ“­")
        await callback.answer()
        return
    await callback.message.answer("Recent withdrawals:" if lang == "en" else "РџРѕСЃР»РµРґРЅРёРµ РІС‹РІРѕРґС‹:")
    for w in withdrawals:
        status = w.status.value
        text = f"#{w.id} user={w.user_id} amount={float(w.amount):.2f} USDT status={status}"
        if status == "approved":
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Refund в™»пёЏ", callback_data=f"admin:wd:refund:{w.id}")],
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
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    structure = await dao.get_referral_structure(session)
    if not structure:
        await callback.message.answer(
            "No referral data yet. рџ“­" if lang == "en" else "Р”Р°РЅРЅС‹С… РїРѕ СЂРµС„РµСЂР°Р»Р°Рј РїРѕРєР° РЅРµС‚. рџ“­"
        )
        await callback.answer()
        return

    header = "Referral structure рџ‘Ґ:" if lang == "en" else "Р РµС„РµСЂР°Р»СЊРЅР°СЏ СЃС‚СЂСѓРєС‚СѓСЂР° рџ‘Ґ:"
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
                f"{referrer_name} (id={referrer_id}) -> {referred_name} (id={referred_id}) | РїСЂРёРЅРµСЃ: {commission_sum:.2f} USDT"
            )
    for chunk in _chunk_lines(lines):
        await callback.message.answer(chunk)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:wd:approve:"))
async def admin_withdraw_approve(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.answer(
        "Manual approval is disabled. Withdrawals are auto-processed."
        if lang == "en"
        else "Р СѓС‡РЅРѕРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ РѕС‚РєР»СЋС‡РµРЅРѕ. Р’С‹РІРѕРґС‹ РѕР±СЂР°Р±Р°С‚С‹РІР°СЋС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё."
    )


@router.callback_query(F.data.startswith("admin:wd:reject:"))
async def admin_withdraw_reject(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.answer(
        "Manual rejection is disabled. Withdrawals are auto-processed."
        if lang == "en"
        else "Р СѓС‡РЅРѕРµ РѕС‚РєР»РѕРЅРµРЅРёРµ РѕС‚РєР»СЋС‡РµРЅРѕ. Р’С‹РІРѕРґС‹ РѕР±СЂР°Р±Р°С‚С‹РІР°СЋС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё."
    )


@router.callback_query(F.data.startswith("admin:wd:refund:"))
async def admin_withdraw_refund(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    if not _is_admin(callback, config):
        await callback.answer("Access denied. рџљ«")
        return
    lang = await get_lang(session, callback.from_user.id)
    withdrawal_id = int(callback.data.split(":")[-1])
    withdrawal = await dao.get_withdrawal(session, withdrawal_id)
    if not withdrawal:
        await callback.answer("Withdrawal not found. вќ“" if lang == "en" else "Р’С‹РІРѕРґ РЅРµ РЅР°Р№РґРµРЅ. вќ“")
        return
    if withdrawal.status != WithdrawalStatus.approved:
        await callback.answer(
            "Only approved withdrawals can be refunded. в›”"
            if lang == "en"
            else "Р’РѕР·РІСЂР°С‚ РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРЅС‹С… РІС‹РІРѕРґРѕРІ. в›”"
        )
        return
    await dao.set_withdrawal_status(session, withdrawal_id, WithdrawalStatus.refunded, datetime.utcnow())
    await dao.update_user_balance(session, withdrawal.user_id, float(withdrawal.amount))
    await dao.add_ledger_entry(session, withdrawal.user_id, float(withdrawal.amount), "withdraw_refund", None)
    await callback.message.answer(
        f"Withdrawal #{withdrawal_id} refunded. в™»пёЏ" if lang == "en" else f"Р’С‹РІРѕРґ #{withdrawal_id} РІРѕР·РІСЂР°С‰РµРЅ. в™»пёЏ"
    )
    await callback.answer()


