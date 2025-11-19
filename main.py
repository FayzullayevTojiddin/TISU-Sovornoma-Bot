from aiogram import Bot, Dispatcher
from config import Config
import asyncio
import logging
from authMiddleware import SubscriptionMiddleware
from handlers import router
from models import db, ConfidraMudiri, User


async def main():
    db.connect()
    db.create_tables([ConfidraMudiri, User])
    print("Database connected and tables exist.")
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher()
    dp.message.middleware(SubscriptionMiddleware())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())