import os
import asyncio
import logging
import base64
import urllib.parse
import re
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
    await message.answer("✅ Бот Nano Banana (V3) запущен!\nПришлите фото для мемориальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (Gemini)...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализ лица
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Briefly describe age, hair color, and eye color. Max 10 words. No punctuation."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Генерация портрета (Stable Diffusion)...")

        # 2. Подготовка промпта
        clean_desc = re.sub(r'[^a-zA-Z\s]', '', person_desc).replace('\n', ' ').strip()
        prompt = (f"A hyper-realistic professional memorial portrait of {clean_desc}, "
                  f"wearing a formal grey shirt, neutral studio grey background, "
                  f"a black diagonal mourning ribbon in the bottom right corner, 8k resolution, sharp focus.")
        
        # 3. Используем резервный шлюз генерации (Image-Generation-Tool)
        encoded_prompt = urllib.parse.quote(prompt)
        # Смена на более стабильный источник (используем стабильный сид)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&private=true&enhance=true"

        # 4. Скачивание с увеличенным ожиданием и проверкой
        final_image_data = None
        async with aiohttp.ClientSession() as session:
            # Даем серверу до 45 секунд, но проверяем реже
            for attempt in range(1, 10):
                try:
                    async with session.get(image_url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            # Если размер > 50Кб, значит это полноценное фото
                            if len(data) > 50000:
                                final_image_data = data
                                break
                except Exception:
                    pass
                logging.info(f"Ожидание генерации {attempt}/10...")
                await asyncio.sleep(5)

        if final_image_data:
            photo_file = BufferedInputFile(final_image_data, filename="retouch.jpg")
            await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!")
            await status_msg.delete()
        else:
            # Если Pollinations совсем лег, даем прямую ссылку
            await message.answer(f"❌ Сервер перегружен. Вы можете скачать результат по прямой ссылке позже:\n{image_url}")
            await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте отправить другое фото.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
