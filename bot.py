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

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana готов. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe face features and hair briefly. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация...\n({person_desc})")

        # Базовый промпт без лишнего мусора
        clean_desc = "".join(c for c in person_desc if c.isalnum() or c.isspace())
        prompt = f"Professional memorial portrait of {clean_desc}, formal clothes, grey background, black ribbon, 8k"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Ссылка на генерацию (упростили параметры для стабильности)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for attempt in range(1, 15):
                try:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 30000:
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=BufferedInputFile(data, filename="result.jpg"), 
                                    caption="✨ Ваша ретушь готова!"
                                )
                                await status_msg.delete()
                                return
                        elif resp.status == 500:
                            logging.error(f"Сервер Pollinations перегружен (500). Попытка {attempt}")
                except Exception as e:
                    logging.error(f"Сбой сети: {str(e)}")
                
                await asyncio.sleep(7)

        await message.answer("❌ Сервер генерации сейчас перегружен. Попробуйте это же фото еще раз через пару минут.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
