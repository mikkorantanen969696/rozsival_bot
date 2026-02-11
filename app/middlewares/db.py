from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory):
        super().__init__()
        self._session_factory = session_factory

    async def __call__(self, handler, event: TelegramObject, data: dict):
        async with self._session_factory() as session:
            data['session'] = session
            return await handler(event, data)
