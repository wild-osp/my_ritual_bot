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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Nano Banana 7.4 (Multi-Engine) готова!")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("🔍 Шаг 1: Анализ через Gemini...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe face, hair, and clothing. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        logger.info(f"Описание: {person_desc}")
        
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация портрета...\n({person_desc})")

        # Промпт без лишних знаков
        clean_desc = "".join(e for e in person_desc if e.isalnum() or e.isspace())
        prompt = f"Professional studio portrait of {clean_desc}, black formal suit, grey background, realistic, 8k"
        encoded_prompt = urllib.parse.quote(prompt)

        # Список моделей от мощных к простым
        models = ["flux", "turbo", "rt"] 
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for current_model in models:
                logger.info(f"Пробую модель: {current_model}")
                await status_msg.edit_text(f"⏳ Пробую модель: {current_model}...")
                
                image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model={current_model}&seed={message.message_id}"
                
                for attempt in range(1, 6): # По 5 попыток на каждую модель
                    try:
                        async with session.get(f"{image_url}&v={attempt}", timeout=30) as resp:
                            data = await resp.read()
                            file_size = len(data)
                            
                            logger.info(f"Модель {current_model}, Попытка {attempt}: Статус {resp.status}, Размер {file_size}")

                            if resp.status == 200 and file_size > 35000:
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=BufferedInputFile(data, filename="r.jpg"), 
                                    caption=f"✨ Готово!\nМодель: {current_model}"
                                )
                                await status_msg.delete()
                                return
                    except Exception as e:
                        logger.error(f"Ошибка: {e}")
                    
                    await asyncio.sleep(5)
            
        await message.answer("❌ Все модели перегружены. Попробуйте позже.")
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
