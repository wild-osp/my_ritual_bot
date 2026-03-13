import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Инициализация клиента
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот ритуальной ретуши в сети! Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Пытаюсь связаться с нейросетью...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    # Список моделей для проверки (Google часто меняет доступность)
    models_to_try = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-pro"]
    
    for model_id in models_to_try:
        try:
            logging.info(f"Пробую модель: {model_id}")
            prompt = "Ritual retouch task: extract person, neutral studio grey background, formal grey shirt, black mourning ribbon in corner."

            response = client.models.generate_content(
                model=model_id,
                contents=[
                    genai_types.Part.from_text(text=prompt),
                    genai_types.Part.from_bytes(data=photo_content.getvalue(), mime_type="image/jpeg")
                ]
            )
            
            if response.text:
                await message.answer(f"✨ Результат от {model_id}:\n{response.text}")
                await status_msg.delete()
                return # Выходим из цикла, если всё ок
                
        except Exception as e:
            logging.error(f"Модель {model_id} не ответила: {e}")
            continue # Пробуем следующую модель из списка

    await status_msg.edit_text("❌ Все доступные модели Google (Flash/Pro) вернули ошибку 404. Возможно, ваш API-ключ имеет ограничения по региону.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
