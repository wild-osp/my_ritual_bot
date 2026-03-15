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

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 VIP Бот 9.3 активен!\nМодели обновлены, каналы открыты.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (Gemini)...")
    
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
                    {"type": "text", "text": "Describe face, hair, and clothes. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        description = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация через Imagen 3...\n({description})")

        # 2. Промпт
        prompt = (f"A professional studio memorial portrait of {description}, "
                  f"wearing a formal dark suit, solid grey background, "
                  f"sharp focus, photorealistic, 8k resolution.")

        # 3. Запрос генерации (Используем Google Imagen 3 - она очень стабильна)
        image_response = await client.chat.completions.create(
            model="google/imagen-3", # Сменили на супер-стабильную модель
            messages=[{"role": "user", "content": prompt}]
        )

        image_url = image_response.choices[0].message.content.strip()
        logging.info(f"URL: {image_url}")

        if "http" in image_url:
            # Чистим ссылку от возможных артефактов
            url = image_url.split("http")[-1]
            url = "http" + url.split()[0].replace(")", "").replace("]", "").replace(">", "")
            
            await bot.send_photo(
                message.chat.id, 
                photo=URLInputFile(url), 
                caption=f"✨ Портрет готов!\nОписание: {description}"
            )
        else:
            await message.answer(f"⚠️ Ошибка модели: {image_url}")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
