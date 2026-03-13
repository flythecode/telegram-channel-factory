import asyncio

from app.bot.app import build_bot, build_dispatcher
from app.core.config import settings


async def main():
    dispatcher = build_dispatcher()
    bot = build_bot()
    if settings.runtime_mode != 'live':
        print('Bot layer configured in non-live mode; dispatcher assembled successfully.')
        return
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
