from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import Config
from app.middlewares.db import DbSessionMiddleware
from app.routers.admin import router as admin_router
from app.routers.dm_profile import router as dm_router
from app.routers.group_game import router as game_router
from app.services.game_service import GameService
from app.services.finance_service import FinanceService
from app.crypto.client import CryptoClient


def create_dispatcher(config: Config, session_factory):
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    crypto = CryptoClient(config.crypto_token)
    finance = FinanceService(session_factory, crypto, config)
    game_service = GameService(session_factory, finance, config)

    dp.update.middleware(DbSessionMiddleware(session_factory))

    dp['config'] = config
    dp['finance'] = finance
    dp['games'] = game_service

    dp.include_router(dm_router)
    dp.include_router(game_router)
    dp.include_router(admin_router)

    game_service.start_timeout_watcher(bot)

    async def on_shutdown(bot: Bot) -> None:
        await game_service.stop_timeout_watcher()
        await finance.close()

    dp.shutdown.register(on_shutdown)

    return dp, bot
