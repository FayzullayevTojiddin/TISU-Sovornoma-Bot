from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config import Config
from authMiddleware import SubscriptionMiddleware
from handlers import router
from models import db, ConfidraMudiri, User
import asyncio
import logging

async def main():
    db.connect()
    db.create_tables([ConfidraMudiri, User])

    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher()
    dp.message.middleware(SubscriptionMiddleware())
    dp.include_router(router)

    app = web.Application()
    handler = SimpleRequestHandler(dp, bot, secret_token=Config.WEBHOOK_SECRET)
    handler.register(app, path=Config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        url=Config.WEBHOOK_URL,
        secret_token=Config.WEBHOOK_SECRET
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=Config.WEBHOOK_HOST,
        port=Config.WEBHOOK_PORT
    )
    await site.start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())