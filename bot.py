import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Клиент Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот ритуальной ретуши активен! Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Фото получено. Работаю...")
    
    # Скачиваем фото
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    try:
        # ПРАВИЛЬНАЯ СТРУКТУРА: Список объектов Part
        prompt_part = genai_types.Part.from_text(text="Memorial portrait task: extract the person, place on neutral grey background, change clothes to formal grey shirt, add black diagonal mourning ribbon in bottom right corner.")
        image_part = genai_types.Part.from_bytes(data=photo_content.getvalue(), mime_type="image/jpeg")

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[genai_types.Content(role="user", parts=[prompt_part, image_part])]
        )
        
        if response.text:
            await message.answer(f"✨ Ответ нейросети:\n{response.text}")
        else:
            await message.answer("Нейросеть обработала запрос, но не вернула текст.")
            
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    logging.info("🚀 Сброс вебхуков и запуск...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
