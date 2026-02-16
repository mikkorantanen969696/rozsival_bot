from __future__ import annotations

import asyncio
import logging

from app.bot.dispatcher import create_dispatcher
from app.config import load_config
from app.db.session import create_engine_and_session, init_db, clear_all_tables


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    )

    config = load_config()
    engine, session_factory = create_engine_and_session(config.database_url)

    if config.clear_db_on_start:
        if config.app_env not in {"dev", "development", "local"}:
            raise RuntimeError("CLEAR_DB_ON_START is allowed only when APP_ENV is dev/development/local")
        await clear_all_tables(engine)

    await init_db(engine)

    dp, bot = create_dispatcher(config, session_factory)

    me = await bot.get_me()
    logging.info("Bot started as @%s (id=%s)", me.username, me.id)

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
