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

# Инициализируем клиент БЕЗ жесткого указания v1, 
# чтобы библиотека сама выбрала актуальный путь
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот готов! Отправьте фото для ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Обработка нейросетью...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    try:
        # Используем полное имя модели. Иногда это решает проблему 404.
        # Если не сработает, заменим на "models/gemini-1.5-flash-latest"
        model_id = "gemini-1.5-flash" 
        
        prompt = (
            "Ritual retouch: extract person, neutral studio grey background, "
            "formal grey shirt, black mourning ribbon in corner."
        )

        response = client.models.generate_content(
            model=model_id,
            contents=[
                genai_types.Part.from_text(text=prompt),
                genai_types.Part.from_bytes(data=photo_content.getvalue(), mime_type="image/jpeg")
            ]
        )
        
        if response.text:
            await message.answer(f"✨ Результат:\n{response.text}")
        else:
            await message.answer("Нейросеть ответила, но текст пуст.")
            
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        # Если ошибка 404 повторится, бот сам предложит решение в тексте
        await message.answer(f"❌ Ошибка 404 или API: {e}\nПопробуйте перезапустить бота через минуту.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
