import os
import asyncio
import logging
import base64
import aiohttp
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

# Загружаем переменные (нужен только TELEGRAM_TOKEN и OPENROUTER_KEY)
load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Инициализация клиента OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Nano Banana 7.1 готова!\nПришлите фото для ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
    # Получаем фото
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
                    {"type": "text", "text": "Describe face, hair, and clothing. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация портрета...\n({person_desc})")

        # 2. Промпт для генерации
        prompt = (f"A professional high-quality memorial studio portrait of {person_desc}, "
                  f"wearing black formal clothes, solid neutral grey background, "
                  f"sharp focus, photorealistic, 8k resolution.")

        # 3. ГЕНЕРАЦИЯ КАРТИНКИ через OpenRouter (модель Stable Diffusion XL)
        # Мы используем Pollinations как прокси, но через более стабильный метод
        image_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true&model=flux"

        async with aiohttp.ClientSession() as session:
            # Делаем 10 попыток с паузой (серверу нужно время на прорисовку)
            for attempt in range(1, 11):
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        # Если картинка больше 40кб — это успех
                        if len(data) > 40000:
                            photo_file = BufferedInputFile(data, filename="result.jpg")
                            await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!")
                            await status_msg.delete()
                            return
                
                await status_msg.edit_text(f"⌛ Рисую... Попытка {attempt}/10")
                await asyncio.sleep(8)

        await message.answer("❌ Сервер рисования всё еще занят. Попробуйте другое фото.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
