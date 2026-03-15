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
    await message.answer("🚀 Nano Banana 5.5: Резервный канал активен. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (Gemini)...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Описание персонажа
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe age, eyes color, and hair briefly. Max 8 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация через резервный канал...\n({person_desc})")

        # 2. Промпт для нового генератора
        prompt = (f"Memorial studio portrait of {person_desc}, dark formal suit, "
                  f"grey background, black mourning ribbon in corner, 8k, realistic portrait.")
        encoded_prompt = urllib.parse.quote(prompt)
        
        # ИСПОЛЬЗУЕМ ДРУГОЙ СЕРВИС (VECSTOCK / PROMPTHERO)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=turbo"

        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Делаем 5 быстрых попыток
            for attempt in range(1, 6):
                try:
                    # Добавляем случайный параметр, чтобы обойти кэш ошибки
                    current_url = f"{image_url}&seed={message.message_id + attempt}"
                    async with session.get(current_url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 30000:
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=BufferedInputFile(data, filename="result.jpg"), 
                                    caption="✨ Ретушь готова (Резервный канал)!"
                                )
                                await status_msg.delete()
                                return
                        logging.warning(f"Попытка {attempt}: Статус {resp.status}")
                except Exception as e:
                    logging.error(f"Ошибка сети: {e}")
                
                await asyncio.sleep(4)

        await message.answer("❌ Оба канала генерации сейчас перегружены. Попробуйте через 15-20 минут.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
