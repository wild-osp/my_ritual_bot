import os
import asyncio
import logging
import base64
import urllib.parse
import aiohttp
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот готов! Пришлите фото, и я сделаю ретушь (бесплатно).")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализ (теперь работает стабильно)
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this person's face briefly (age, eyes color, hair style). Max 20 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Отрисовка портрета (около 10-15 сек)...")

        # 2. Подготовка промпта (максимально простого)
        clean_desc = "".join(e for e in person_desc if e.isalnum() or e.isspace())
        prompt = f"Professional memorial portrait of {clean_desc}, formal grey shirt, grey background, black mourning ribbon bottom right, hyperrealistic, 8k"
        
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={message.message_id}&model=flux"

        # 3. Скачиваем картинку, чтобы отправить файл, а не ссылку
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    photo_file = BufferedInputFile(image_data, filename="retouch.jpg")
                    await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!")
                else:
                    await message.answer("❌ Сервер генерации временно перегружен. Попробуйте через минуту.")

        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
