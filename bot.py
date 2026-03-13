import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from google import genai
from dotenv import load_dotenv

# Логи в консоль
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Проверка токенов
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logging.error("❌ ОШИБКА: Токены не найдены в переменных окружения!")

# Настройка нового клиента Google
client = genai.Client(api_key=GEMINI_API_KEY)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    logging.info(f"Команда /start от {message.from_user.id}")
    await message.answer("✅ Бот ритуальной ретуши активен! Пришлите фото, и я подготовлю его для печати.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    await message.answer("⌛ Фото получено. Обрабатываю нейросетью Nano Banana...")
    
    # Скачиваем фото
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    try:
        # Запрос к нейросети
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                "Memorial portrait: remove background, neutral grey background, formal grey shirt, add black ribbon in corner.",
                photo_content.getvalue()
            ]
        )
        await message.answer("Ретушь завершена! (В бесплатном API сейчас настраивается возврат картинки)")
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        await message.answer(f"❌ Ошибка нейросети: {e}")

async def main():
    logging.info("🚀 Запуск процесса polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
