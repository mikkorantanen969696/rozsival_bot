from __future__ import annotations

from aiogram.types import User as TgUser

from app.db import dao

RU = "ru"
EN = "en"


TEXTS: dict[str, dict[str, str]] = {
    "choose_language": {
        RU: "Выберите язык / Choose language 👇",
        EN: "Choose language / Выберите язык 👇",
    },
    "lang_saved_ru": {
        RU: "Язык переключен на Русский ✅",
        EN: "Language switched to Russian ✅",
    },
    "lang_saved_en": {
        RU: "Язык переключен на English ✅",
        EN: "Language switched to English ✅",
    },
    "welcome": {
        RU: "Добро пожаловать в Dice Bot! Выберите действие 👇",
        EN: "Welcome to Dice Bot! Choose an action 👇",
    },
    "access_denied": {
        RU: "Доступ запрещен. 🚫",
        EN: "Access denied. 🚫",
    },
    "admin_panel": {
        RU: "Админ-панель 🛠️",
        EN: "Admin panel 🛠️",
    },
    "support": {
        RU: "Поддержка: напишите @testoviyaccount 🛟",
        EN: "Support: message @testoviyaccount 🛟",
    },
    "rules": {
        RU: "Правила 📜\n1. Игра только в группе через /game.\n2. Ходите по очереди и кидайте 🎲.\n3. Если вышло время хода, это поражение ⏳.\n4. В платных играх удерживается комиссия 💸.",
        EN: "Rules 📜\n1. Group games only via /game.\n2. Take turns and roll 🎲.\n3. Turn timeout = loss ⏳.\n4. Paid games take a commission from the winnings 💸.",
    },
    "manual": {
        RU: "Как играть 🎯\n1. В группе: /game @username\n2. Выберите тип игры, ставку и раунды.\n3. Дождитесь принятия вызова.\n4. Кидайте 🎲 по очереди.",
        EN: "How to Play 🎯\n1. In a group: /game @username\n2. Pick game type, bet, and rounds.\n3. Wait for acceptance.\n4. Roll 🎲 in turn.",
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    value = TEXTS.get(key, {}).get(lang.lower()) or TEXTS.get(key, {}).get(EN) or key
    return value.format(**kwargs)


async def get_lang(session, user_id: int) -> str:
    lang = await dao.get_user_language(session, user_id)
    return RU if lang.lower() == RU else EN


def parse_referrer_id(text: str | None, current_user: TgUser | None) -> int | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if not payload.isdigit():
        return None
    referrer_id = int(payload)
    if current_user and current_user.id == referrer_id:
        return None
    return referrer_id
