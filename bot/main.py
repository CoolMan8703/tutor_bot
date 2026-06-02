import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher
from database import init_db
from bot.handlers import admin, client

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Глобальный экземпляр бота (используется для уведомлений из API)
bot = None


async def main():
    global bot
    await init_db()
    print("✅ База данных инициализирована")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(client.router)
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    if not BOT_TOKEN or "YOUR_BOT_TOKEN" in BOT_TOKEN:
        print("❌ Укажите BOT_TOKEN в файле .env!")
        sys.exit(1)
    asyncio.run(main())
