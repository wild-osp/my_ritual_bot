import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import URLInputFile
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Настройка клиента
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Бот Nano Banana 9.2 VIP готов!\nТеперь мы работаем через прямой канал OpenRouter.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ фото (Gemini)...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализ через Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe age, hair, eyes, and clothes. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        description = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🎨 Шаг 2: Платная генерация (SDXL)...\n({description})")

        # 2. Промпт для ретуши
        prompt = (f"High-quality professional studio memorial portrait of {description}, "
                  f"wearing a formal dark suit, neutral grey studio background, "
                  f"black mourning ribbon in bottom corner, 8k resolution, photorealistic.")

        # 3. Запрос генерации в OpenRouter
        # Используем SDXL как самую стабильную и дешевую модель
        image_response = await client.chat.completions.create(
            model="stabilityai/sdxl",
            messages=[{"role": "user", "content": prompt}]
        )

        # Вытаскиваем URL из ответа
        # Платные модели на OpenRouter отдают ссылку прямо в контенте
        image_url = image_response.choices[0].message.content.strip()
        
        logging.info(f"Получен ответ от модели: {image_url}")

        if "http" in image_url:
            # Очистка ссылки от лишних символов (иногда модель добавляет скобки)
            clean_url = image_url.split("http")[-1]
            clean_url = "http" + clean_url.split()[0].replace(")", "").replace("]", "").replace(">", "")
            
            await bot.send_photo(
                message.chat.id, 
                photo=URLInputFile(clean_url), 
                caption="✨ Ретушь готова!\nСписано с баланса: ~$0.01"
            )
        else:
            await message.answer(f"⚠️ Ошибка: Модель не прислала ссылку. Ответ: {image_url}")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
