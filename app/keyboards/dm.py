from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def dm_main_keyboard(is_admin: bool, lang: str):
    is_ru = lang.lower() == "ru"
    rows = [
        [InlineKeyboardButton(text="Balance 💰" if not is_ru else "Баланс 💰", callback_data="dm:balance")],
        [InlineKeyboardButton(text="Deposit ➕" if not is_ru else "Пополнить ➕", callback_data="dm:deposit")],
        [InlineKeyboardButton(text="Stats 📊" if not is_ru else "Статистика 📊", callback_data="dm:stats")],
        [InlineKeyboardButton(text="Referrals 👥" if not is_ru else "Рефералы 👥", callback_data="dm:ref")],
        [InlineKeyboardButton(text="Rules 📜" if not is_ru else "Правила 📜", callback_data="dm:rules")],
        [InlineKeyboardButton(text="How to Play 🎯" if not is_ru else "Как играть 🎯", callback_data="dm:manual")],
        [InlineKeyboardButton(text="Support 🛟" if not is_ru else "Поддержка 🛟", callback_data="dm:support")],
        [InlineKeyboardButton(text="Withdraw 💸" if not is_ru else "Вывести 💸", callback_data="dm:withdraw")],
        [InlineKeyboardButton(text="Language 🌐" if not is_ru else "Язык 🌐", callback_data="dm:lang")],
    ]
    if is_admin:
        rows.append(
            [InlineKeyboardButton(text="Admin Panel 🛠️" if not is_ru else "Админ-панель 🛠️", callback_data="dm:admin")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def deposit_keyboard(lang: str):
    is_ru = lang.lower() == "ru"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.5", callback_data="dep:0.5"),
                InlineKeyboardButton(text="1", callback_data="dep:1"),
                InlineKeyboardButton(text="5", callback_data="dep:5"),
            ],
            [
                InlineKeyboardButton(text="10", callback_data="dep:10"),
                InlineKeyboardButton(text="50", callback_data="dep:50"),
                InlineKeyboardButton(text="100", callback_data="dep:100"),
            ],
            [InlineKeyboardButton(text="Custom amount ✍️" if not is_ru else "Своя сумма ✍️", callback_data="dep:custom")],
        ]
    )


def invoice_keyboard(invoice_id: int, pay_url: str, lang: str):
    is_ru = lang.lower() == "ru"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Pay 💳" if not is_ru else "Оплатить 💳", url=pay_url)],
            [InlineKeyboardButton(text="I paid ✅" if not is_ru else "Я оплатил ✅", callback_data=f"dep:check:{invoice_id}")],
        ]
    )


def withdraw_confirm_keyboard(lang: str):
    is_ru = lang.lower() == "ru"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Withdraw to my CryptoBot account ✅" if not is_ru else "Вывести на мой CryptoBot ✅",
                    callback_data="wd:yes",
                )
            ],
            [InlineKeyboardButton(text="Cancel ❌" if not is_ru else "Отмена ❌", callback_data="wd:no")],
        ]
    )


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang:set:ru"),
                InlineKeyboardButton(text="English 🇬🇧", callback_data="lang:set:en"),
            ],
        ]
    )
