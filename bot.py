import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хендлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Получена команда /start от {message.from_user.id}")
    await message.answer("✅ Бот ожил! Связь установлена.")

# Хендлер на любое текстовое сообщение
@dp.message(F.text)
async def echo_message(message: types.Message):
    logger.info(f"Получен текст: {message.text}")
    await message.reply(f"Вы написали: {message.text}. Пришлите фото, когда будете готовы.")

# Хендлер на фото (минимальный)
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    logger.info("Фото получено!")
    await message.answer("📸 Фото вижу. Сейчас попробую настроить ретушь...")

async def main():
    logger.info("Запуск бота...")
    # Удаляем старые сообщения, которые накопились, пока бот лежал
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
