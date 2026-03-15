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

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Клиент только для анализа текста/лиц
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Бот Nano Banana 6.1 готов!\nПришлите фото для ритуальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
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
                    {"type": "text", "text": "Describe face, hair and clothing. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Создание портрета...\n({person_desc})")

        # 2. Промпт (убираем спецсимволы, чтобы не было 400 Bad Request)
        clean_desc = "".join(e for e in person_desc if e.isalnum() or e.isspace())
        prompt = f"Professional memorial studio portrait of {clean_desc} wearing formal dark suit and grey background with black mourning ribbon in corner 8k highly detailed"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Используем самый стабильный URL
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={message.message_id}"

        # 3. Загрузка картинки
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            # Даем нейросети 60 секунд на рисование (12 попыток по 5 сек)
            for attempt in range(1, 13):
                try:
                    async with session.get(image_url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 30000: # Проверка, что это не логотип
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=BufferedInputFile(data, filename="result.jpg"), 
                                    caption="✨ Ретушь готова!"
                                )
                                await status_msg.delete()
                                return
                except Exception as e:
                    logging.error(f"Попытка {attempt} не удалась: {e}")
                
                await asyncio.sleep(5)

        await message.answer("❌ Не удалось получить изображение. Попробуйте еще раз через минуту.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
