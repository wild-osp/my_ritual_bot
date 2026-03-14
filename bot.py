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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Ключ от OpenRouter (который у тебя уже есть и работает)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🍌 Nano Banana 5.0 (Стабильная версия) запущена!\nРегистрация не требуется. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (OpenRouter)...")
    
    # 1. Получаем фото
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 2. Анализ черт лица
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe age, hair and facial features briefly. Max 10 words. No punctuation."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = analysis.choices[0].message.content.strip()
        await status_msg.edit_text("⌛ Шаг 2: Генерация ретуши (может занять до 40 сек)...")

        # 3. Подготовка промпта
        clean_desc = re.sub(r'[^a-zA-Z\s]', '', person_desc)
        prompt = (f"A high-quality professional studio memorial portrait of {clean_desc}, "
                  f"wearing a formal grey shirt, neutral studio grey background, "
                  f"a black diagonal mourning ribbon in the bottom right corner, 8k, sharp focus.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Генерируем URL (используем модель Flux для лучшего качества)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={message.message_id}"

        # 4. УМНЫЙ ЦИКЛ ОЖИДАНИЯ (Logo Filter)
        final_image_data = None
        # Мы будем имитировать браузер, чтобы сервер не выдавал заглушку
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        async with aiohttp.ClientSession(headers=headers) as session:
            for attempt in range(1, 15): # Пробуем 15 раз (всего 75 секунд)
                try:
                    async with session.get(image_url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            # ГЛАВНАЯ ПРОВЕРКА: логотип весит меньше 30 Кб. 
                            # Настоящее фото в высоком разрешении весит минимум 100-500 Кб.
                            if len(data) > 40000: 
                                final_image_data = data
                                logging.info(f"✅ Фото получено на попытке {attempt}! Размер: {len(data)} байт.")
                                break
                            else:
                                logging.info(f"⌛ Попытка {attempt}: Получен логотип (размер {len(data)}), ждем дальше...")
                except Exception as e:
                    logging.error(f"Ошибка при скачивании: {e}")
                
                await asyncio.sleep(6) # Ждем 6 секунд перед следующей попыткой

        # 5. Отправка результата
        if final_image_data:
            photo_file = BufferedInputFile(final_image_data, filename="retouch.jpg")
            await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!\nИспользована связка Gemini + Flux.")
        else:
            await message.answer("❌ Сервер генерации слишком долго не отвечал. Попробуйте отправить фото еще раз.")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer("❌ Ошибка при обработке. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
