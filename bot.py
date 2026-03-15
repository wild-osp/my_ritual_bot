import os
import asyncio
import logging
import base64
import aiohttp
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import BufferedInputFile, URLInputFile
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Инициализация клиента OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("⭐ Бот Nano Banana 9.0 (VIP SDXL) запущен!\nИспользую приоритетный платный канал. Качество и стабильность гарантированы.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("🔍 Шаг 1: Анализ лица (Gemini)...")
    
    # Получаем фото от пользователя
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализ лица через Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe face features, hair, and eye color for a professional portrait. Max 12 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        description = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🚀 Шаг 2: Платная генерация SDXL...\n({description})")

        # 2. Формируем качественный промпт
        prompt = (f"High-quality professional studio memorial portrait of {description}, "
                  f"wearing a formal dark suit, neutral grey studio background, "
                  f"sharp focus, highly detailed, photorealistic, 8k resolution.")

        # 3. Прямой запрос на генерацию картинки в OpenRouter
        # Модель SDXL на OpenRouter принимает текстовый промпт и возвращает ссылку на изображение
        image_response = await client.chat.completions.create(
            model="stabilityai/sdxl",
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Вытаскиваем результат (URL картинки)
        image_url = image_response.choices[0].message.content.strip()
        
        # Проверяем, что получили URL, а не текст ошибки
        if "http" in image_url:
            await bot.send_photo(
                message.chat.id, 
                photo=URLInputFile(image_url), 
                caption=f"✨ Ретушь готова!\nИспользована модель: SDXL\nОписание: {description}"
            )
        else:
            # Если модель вернула текст вместо ссылки
            await message.answer(f"⚠️ Ошибка модели: {image_url}")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
