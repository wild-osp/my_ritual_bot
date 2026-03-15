import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def check():
    print("--- ТЕСТ СВЯЗИ НАЧАТ ---")
    try:
        bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
        me = await bot.get_me()
        print(f"✅ УСПЕХ! Бот @{me.username} на связи.")
        print("Теперь закрой этот скрипт (Ctrl+C) и запусти версию v19.0")
    except Exception as e:
        print(f"❌ ОШИБКА СВЯЗИ: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check())
