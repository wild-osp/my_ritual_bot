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
    await message.answer("🚀 VIP Бот 9.4 (DALL-E 3) активен!\nТеперь генерация будет максимально качественной.")

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
                    {"type": "text", "text": "Describe the face and hair of this person in detail. Max 12 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        description = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация через DALL-E 3...\n({description})")

        # 2. Промпт для DALL-E (она любит подробности)
        prompt = (f"A professional hyper-realistic studio memorial portrait of {description}. "
                  f"The person is wearing a formal black suit and white shirt. "
                  f"Background is a solid neutral grey studio backdrop. "
                  f"In the bottom corner, a subtle black diagonal mourning ribbon. "
                  f"8k resolution, cinematic lighting, photorealistic masterpiece.")

        # 3. Запрос генерации (DALL-E 3 - золотой стандарт)
        image_response = await client.chat.completions.create(
            model="openai/dall-e-3", 
            messages=[{"role": "user", "content": prompt}]
        )

        image_url = image_response.choices[0].message.content.strip()
        logging.info(f"DALL-E URL: {image_url}")

        if "http" in image_url:
            # Очистка ссылки отMarkdown-разметки, если она есть
            url = image_url.replace("(", "").replace(")", "").replace("[", "").replace("]", "").replace(" ", "")
            if "http" in url:
                url = "http" + url.split("http")[-1]

            await bot.send_photo(
                message.chat.id, 
                photo=URLInputFile(url), 
                caption=f"✨ Портрет готов!\nИспользована модель: DALL-E 3"
            )
        else:
            await message.answer(f"⚠️ Ошибка DALL-E: {image_url}")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
