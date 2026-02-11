from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.db import dao
from app.i18n import EN, RU, get_lang, parse_referrer_id, t
from app.keyboards.dm import (
    deposit_keyboard,
    dm_main_keyboard,
    invoice_keyboard,
    language_keyboard,
    withdraw_confirm_keyboard,
)
from app.services.finance_service import FinanceService

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")
logger = logging.getLogger(__name__)

_pending_custom_amount: set[int] = set()
_pending_withdraw_amount: set[int] = set()
_pending_withdraw_confirm: dict[int, float] = {}


def _is_admin(user_id: int, config: Config) -> bool:
    return user_id == config.admin_id


@router.message(Command("start"))
async def dm_start(message: Message, session, config: Config):
    if message.chat.type != "private" or not message.from_user:
        return
    referrer_id = parse_referrer_id(message.text, message.from_user)
    await dao.get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        referred_by=referrer_id,
    )
    lang = await get_lang(session, message.from_user.id)
    await message.answer(t("choose_language", lang), reply_markup=language_keyboard())
    await message.answer(
        t("welcome", lang),
        reply_markup=dm_main_keyboard(_is_admin(message.from_user.id, config), lang),
    )


@router.callback_query(F.data == "dm:lang")
async def dm_language_menu(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.message.answer(t("choose_language", lang), reply_markup=language_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("lang:set:"))
async def dm_language_set(callback: CallbackQuery, session, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = callback.data.split(":")[-1].lower()
    lang = RU if lang == RU else EN
    await dao.get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    await dao.set_user_language(session, callback.from_user.id, lang)
    await callback.message.answer(t("lang_saved_ru" if lang == RU else "lang_saved_en", lang))
    await callback.message.answer(
        t("welcome", lang),
        reply_markup=dm_main_keyboard(_is_admin(callback.from_user.id, config), lang),
    )
    await callback.answer()


@router.callback_query(F.data == "dm:balance")
async def dm_balance(callback: CallbackQuery, session, finance: FinanceService):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    await finance.ensure_user(session, callback.from_user.id, callback.from_user.username)
    pending = await dao.get_pending_txs_by_user(session, callback.from_user.id)
    for tx in pending:
        if tx.invoice_id:
            await finance.check_deposit(session, tx.invoice_id)
    balance = await finance.get_balance(session, callback.from_user.id)
    text = f"Your balance: {balance:.2f} USDT 💰" if lang == EN else f"Ваш баланс: {balance:.2f} USDT 💰"
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "dm:deposit")
async def dm_deposit(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    text = "Choose a deposit amount 💳:" if lang == EN else "Выберите сумму пополнения 💳:"
    await callback.message.answer(text, reply_markup=deposit_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "dm:withdraw")
async def dm_withdraw(callback: CallbackQuery, session, finance: FinanceService, config: Config):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    balance = await finance.get_balance(session, callback.from_user.id)
    _pending_withdraw_amount.add(callback.from_user.id)
    _pending_custom_amount.discard(callback.from_user.id)
    _pending_withdraw_confirm.pop(callback.from_user.id, None)
    if lang == EN:
        text = (
            f"Your balance: {balance:.2f} USDT 💰\n"
            f"Enter the withdrawal amount (USDT) 💸:\n"
            f"Minimum: {config.min_withdraw:.2f} USDT"
        )
    else:
        text = (
            f"Ваш баланс: {balance:.2f} USDT 💰\n"
            f"Введите сумму вывода (USDT) 💸:\n"
            f"Минимум: {config.min_withdraw:.2f} USDT"
        )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("dep:"))
async def dm_deposit_amount(callback: CallbackQuery, session, finance: FinanceService):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    _, value = callback.data.split(":", 1)
    if value == "custom":
        _pending_custom_amount.add(callback.from_user.id)
        await callback.message.answer(
            "Enter a deposit amount (USDT) 💬:" if lang == EN else "Введите сумму пополнения (USDT) 💬:"
        )
        await callback.answer()
        return

    amount = float(value)
    if amount <= 0:
        await callback.message.answer("Invalid amount. ❗" if lang == EN else "Некорректная сумма. ❗")
        await callback.answer()
        return

    invoice = await finance.create_deposit(session, callback.from_user.id, amount)
    text = (
        f"Invoice created for {amount} USDT. Pay using the button below 💳"
        if lang == EN
        else f"Инвойс на {amount} USDT создан. Оплатите по кнопке ниже 💳"
    )
    await callback.message.answer(text, reply_markup=invoice_keyboard(invoice.invoice_id, invoice.pay_url, lang))
    await callback.answer()


@router.message()
async def dm_custom_amount(message: Message, session, finance: FinanceService):
    if message.chat.type != "private" or message.from_user is None:
        return
    if message.from_user.id not in _pending_custom_amount and message.from_user.id not in _pending_withdraw_amount:
        return
    lang = await get_lang(session, message.from_user.id)
    try:
        raw = (message.text or "0").strip().replace(",", ".")
        amount = float(raw)
    except ValueError:
        await message.answer("Enter a number. 🔢" if lang == EN else "Введите число. 🔢")
        return

    if amount <= 0:
        await message.answer("Amount must be greater than 0. 📈" if lang == EN else "Сумма должна быть больше 0. 📈")
        return

    if message.from_user.id in _pending_custom_amount:
        _pending_custom_amount.discard(message.from_user.id)
        invoice = await finance.create_deposit(session, message.from_user.id, amount)
        text = (
            f"Invoice created for {amount} USDT. Pay using the button below 💳"
            if lang == EN
            else f"Инвойс на {amount} USDT создан. Оплатите по кнопке ниже 💳"
        )
        await message.answer(text, reply_markup=invoice_keyboard(invoice.invoice_id, invoice.pay_url, lang))
        return

    _pending_withdraw_amount.discard(message.from_user.id)
    balance = await finance.get_balance(session, message.from_user.id)
    if amount > balance:
        await message.answer("Insufficient balance for withdrawal. 💸" if lang == EN else "Недостаточно средств для вывода. 💸")
        return

    _pending_withdraw_confirm[message.from_user.id] = amount
    text = (
        f"Withdraw {amount:.2f} USDT to your CryptoBot account? 💸"
        if lang == EN
        else f"Вывести {amount:.2f} USDT на ваш аккаунт CryptoBot? 💸"
    )
    await message.answer(text, reply_markup=withdraw_confirm_keyboard(lang))


@router.callback_query(F.data == "wd:yes")
async def dm_withdraw_confirm(callback: CallbackQuery, session, finance: FinanceService):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    amount = _pending_withdraw_confirm.pop(callback.from_user.id, None)
    if amount is None:
        await callback.answer("No pending withdrawal. 📭" if lang == EN else "Нет ожидающего вывода. 📭")
        return

    ok, error = await finance.withdraw_to_cryptobot(session, callback.from_user.id, amount)
    if ok:
        await callback.message.answer(
            f"Withdrawal sent: {amount:.2f} USDT ✅"
            if lang == EN
            else f"Вывод отправлен: {amount:.2f} USDT ✅"
        )
    else:
        await callback.message.answer(error or ("Withdrawal failed. ⚠️" if lang == EN else "Вывод не выполнен. ⚠️"))
    await callback.answer()


@router.callback_query(F.data == "wd:no")
async def dm_withdraw_cancel(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    _pending_withdraw_confirm.pop(callback.from_user.id, None)
    await callback.message.answer("Withdrawal canceled. ❌" if lang == EN else "Вывод отменен. ❌")
    await callback.answer()


@router.callback_query(F.data.startswith("dep:check:"))
async def dm_check_deposit(callback: CallbackQuery, session, finance: FinanceService):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    invoice_id = int(callback.data.split(":")[-1])
    try:
        paid = await finance.check_deposit(session, invoice_id)
        if paid:
            await callback.message.answer("Payment confirmed. Balance updated ✅" if lang == EN else "Оплата подтверждена. Баланс обновлен ✅")
        else:
            await callback.message.answer("Payment not found yet. Try again later ⏳" if lang == EN else "Платеж пока не найден. Попробуйте позже ⏳")
        await callback.answer()
    except Exception:
        logger.exception("deposit check failed: invoice_id=%s user_id=%s", invoice_id, callback.from_user.id)
        await callback.message.answer("Payment check failed. Try again later ⚠️" if lang == EN else "Проверка платежа не удалась. Попробуйте позже ⚠️")
        await callback.answer()


@router.callback_query(F.data == "dm:stats")
async def dm_stats(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    user = await dao.get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    if lang == EN:
        text = f"Stats 📊\nGames: {user.total_games}\nWins: {user.wins}\nLosses: {user.losses}"
    else:
        text = f"Статистика 📊\nИгр: {user.total_games}\nПобед: {user.wins}\nПоражений: {user.losses}"
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "dm:ref")
async def dm_referrals(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    user = await dao.get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    bot_user = await callback.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start={user.id}" if bot_user.username else f"/start {user.id}"
    referred_count = await dao.get_referred_count(session, user.id)

    if lang == EN:
        text = (
            "Referral program 👥\n"
            f"Your link: {link}\n"
            f"Invited users: {referred_count}"
        )
    else:
        text = (
            "Реферальная программа 👥\n"
            f"Ваша ссылка: {link}\n"
            f"Приглашено пользователей: {referred_count}"
        )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "dm:rules")
async def dm_rules(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.message.answer(t("rules", lang))
    await callback.answer()


@router.callback_query(F.data == "dm:manual")
async def dm_manual(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.message.answer(t("manual", lang))
    await callback.answer()


@router.callback_query(F.data == "dm:support")
async def dm_support(callback: CallbackQuery, session):
    if callback.message and callback.message.chat.type != "private":
        return
    lang = await get_lang(session, callback.from_user.id)
    await callback.message.answer(t("support", lang))
    await callback.answer()
