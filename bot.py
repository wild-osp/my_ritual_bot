import os
import asyncio
import logging
import base64
import urllib.parse
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Клиент для БЕСПЛАТНОЙ Gemini
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бесплатная Nano Banana запущена!\nПришлите фото для мемориального портрета.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (Бесплатная Gemini)...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Используем БЕСПЛАТНУЮ модель Gemini для анализа
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this person's face very briefly for a portrait. Focus on eyes, hair, and chin. Max 40 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Бесплатная генерация портрета...")

        # 2. Формируем промпт и используем бесплатный движок Pollinations
        raw_prompt = (
            f"Hyper-realistic professional memorial photo of {person_desc}, "
            f"wearing formal grey shirt, neutral studio grey background, "
            f"black mourning ribbon in bottom right corner, sharp focus, 8k."
        )
        
        # Кодируем текст для URL
        encoded_prompt = urllib.parse.quote(raw_prompt)
        # Генерируем ссылку на картинку (каждый раз новая благодаря seed)
        seed = message.message_id 
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={seed}&model=flux"

        # 3. Отправляем результат
        await bot.send_photo(
            message.chat.id, 
            photo=image_url, 
            caption=f"✅ Ретушь готова (бесплатно)!\n\nОписание: {person_desc[:100]}..."
        )
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
