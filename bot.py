import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from google import genai
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def main():
    # Проверка ключей прямо в логах
    if not TELEGRAM_TOKEN:
        logging.error("❌ ТОКЕН ТЕЛЕГРАМ НЕ НАЙДЕН!")
        return
    
    logging.info(f"🚀 Запуск бота с токеном: {TELEGRAM_TOKEN[:5]}***")
    
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Этот блок удалит старые привязки (вебхуки), которые могут мешать
    await bot.delete_webhook(drop_pending_updates=True)

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        logging.info("✅ Получена команда /start")
        await message.answer("Бот работает! Пришлите фото.")

    @dp.message(F.photo)
    async def photo_handler(message: types.Message):
        logging.info("📸 Получено фото")
        await message.answer("Начинаю ретушь...")

    logging.info("📡 Начинаю слушать серверы Telegram (Polling)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"💥 Критическая ошибка: {e}")
