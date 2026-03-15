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

# Загружаем переменные из Bothost (TELEGRAM_TOKEN и OPENROUTER_KEY)
load_dotenv()

logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Инициализация клиента
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Nano Banana 5.2 готова к работе!\nПришлите фото для мемориальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица через Gemini...")
    
    # Скачиваем оригинал
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
                    {"type": "text", "text": "Describe age, eyes color, hair and face features. Max 12 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Нейросеть Flux рисует портрет...\nОписание: {person_desc}")

        # 2. Промпт для Pollinations
        prompt = (f"A professional memorial studio portrait of {person_desc}, "
                  f"wearing a formal dark suit or grey shirt, neutral studio grey background, "
                  f"a black diagonal mourning ribbon in the bottom right corner, 8k, sharp focus.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Генерируем URL (используем Flux модель для качества)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={message.message_id}"

        # 3. УМНЫЙ ЦИКЛ ОЖИДАНИЯ
        async with aiohttp.ClientSession() as session:
            for attempt in range(1, 21): # Ждем до 100 секунд (20 раз по 5 сек)
                try:
                    async with session.get(image_url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            file_size = len(data)
                            
                            # Если картинка тяжелее 35 Кб — это точно не логотип
                            if file_size > 35000:
                                photo_file = BufferedInputFile(data, filename="result.jpg")
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=photo_file, 
                                    caption=f"✨ Ретушь готова!\nНайдено на попытке №{attempt}."
                                )
                                await status_msg.delete()
                                return
                            else:
                                logging.info(f"Попытка {attempt}: Получен логотип ({file_size} байт), ждем...")
                except Exception as e:
                    logging.error(f"Ошибка на попытке {attempt}: {e}")
                
                await asyncio.sleep(5)

        await message.answer("❌ Сервер рисовал слишком долго. Попробуйте еще раз.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
