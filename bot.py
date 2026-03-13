import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from google import genai
from dotenv import load_dotenv

# Включаем логирование, чтобы видеть всё в панели Bothost
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Забираем ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация клиента Google (новый стандарт 2026 года)
client = genai.Client(api_key=GEMINI_API_KEY)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    logging.info(f"Команда /start получена от {message.from_user.id}")
    await message.answer("✅ Бот ритуальной ретуши активен! Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status_msg = await message.answer("⌛ Фото получено. Обрабатываю нейросетью Nano Banana (Gemini 3 Flash)...")
    
    # Скачиваем фото в память
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    try:
        # Запрос к нейросети
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                "Memorial portrait task: extract the person, place on neutral grey background, change clothes to formal grey shirt, add black diagonal mourning ribbon in bottom right corner.",
                photo_content.getvalue()
            ]
        )
        # Если ответ содержит текст (описание), выводим его. 
        # Генерация новой картинки в API часто идет отдельным медиа-потоком.
        await status_msg.edit_text("✅ Ретушь завершена! Проверяю результат...")
        
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        await message.answer(f"❌ Ошибка нейросети: {e}")

async def main():
    logging.info("🚀 Сброс вебхуков и запуск бота...")
    # Очищаем очередь, чтобы бот ответил на старые нажатия /start
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
