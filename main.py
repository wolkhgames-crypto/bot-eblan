"""Запуск бота: python main.py"""

import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
from handlers import router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx на уровне INFO пишет каждый запрос, это лишний шум
    logging.getLogger("httpx").setLevel(logging.WARNING)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Long polling не работает, если у бота висит вебхук, поэтому снимаем его
    # и выкидываем сообщения, накопившиеся, пока бот был выключен
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.me()
    logging.info("Бот запущен: @%s", me.username)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
