import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.container import AppContainer
from bot.presentation.handlers import router
from bot.presentation.middleware import ContainerMiddleware


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    container = AppContainer()
    bot = Bot(token=container.app_settings().bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(ContainerMiddleware(container))
    dp.include_router(router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

