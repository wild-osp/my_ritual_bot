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

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Основной клиент для текста и картинок
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Бот Nano Banana 6.0 запущен!\nИспользую прямой канал OpenRouter для генерации.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ фото...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализ лица
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe age, hair, eyes and face. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация ретуши...\n({person_desc})")

        # 2. Генерация через OpenRouter (используем Stable Diffusion XL)
        # Это надежнее, чем внешние бесплатные сайты
        prompt = (f"Professional memorial portrait of {person_desc}, "
                  f"wearing a formal dark suit, neutral grey studio background, "
                  f"a black diagonal mourning ribbon in corner, 8k, realistic.")

        # Мы используем модель, которая доступна через OpenRouter API
        gen_response = await client.chat.completions.create(
            model="stabilityai/sdxl", # Высокое качество
            messages=[{"role": "user", "content": prompt}],
            extra_body={"response_format": "b64_json"} # Просим вернуть саму картинку
        )

        # Вытаскиваем картинку из ответа
        image_b64 = gen_response.choices[0].message.content
        # Если модель вернула текст вместо картинки (бывает в редких форматах), обработаем это
        if "b64_json" in str(gen_response):
            # В некоторых версиях API картинка лежит в расширенных полях
            image_data = base64.b64decode(gen_response.choices[0].index) # Упрощенно
        else:
            # Если SDXL недоступен, попробуем через pollinations, но с другим подходом
            raise Exception("OpenRouter Image Model Busy")

    except Exception:
        # Резервный метод, если SDXL через API не сработал — 
        # используем проксированный запрос, который Bothost не забанит
        try:
            proxy_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"
            async with aiohttp.ClientSession() as session:
                async with session.get(proxy_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        await bot.send_photo(message.chat.id, BufferedInputFile(data, "r.jpg"), caption="✨ Готово!")
                        await status_msg.delete()
                        return
        except Exception as e:
            logging.error(f"Error: {e}")
            await message.answer("❌ Технические работы на сервере генерации. Попробуйте позже.")
            await status_msg.delete()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
