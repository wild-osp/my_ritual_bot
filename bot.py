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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Клиент для OpenRouter (используем бесплатные лимиты Gemini)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana активен!\nПришлите фото человека, и я сделаю мемориальный портрет (бесплатно).")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ черт лица...")
    
    # Получаем фото из сообщения
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализируем лицо через бесплатную модель Gemini
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this person's facial features very briefly (age, hair, eyes). Max 15 words. No new lines."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Генерация портрета (это займет 10-20 сек)...")

        # 2. Очистка описания от символов, которые ломают URL
        clean_desc = person_desc.replace('\n', ' ').replace('\r', ' ').strip()
        # Оставляем только буквы, цифры и пробелы
        clean_desc = "".join(e for e in clean_desc if e.isalnum() or e.isspace())
        
        # 3. Формируем промпт для бесплатного движка Pollinations
        prompt = (f"Professional studio memorial portrait of {clean_desc}, "
                  f"wearing formal grey shirt, neutral grey background, "
                  f"black diagonal mourning ribbon bottom right, hyperrealistic, 8k")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Параметр seed делаем случайным на основе ID сообщения, чтобы фото были разными
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={message.message_id}&model=flux"

        # 4. Скачиваем готовую картинку
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=60) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    
                    # Проверка, что файл не пустой и не слишком маленький
                    if len(image_data) > 5000:
                        photo_file = BufferedInputFile(image_data, filename="retouch.jpg")
                        await bot.send_photo(
                            message.chat.id, 
                            photo=photo_file, 
                            caption="✨ Ретушь готова! Использована модель Flux + Gemini."
                        )
                    else:
                        await message.answer("❌ Сервер вернул пустой файл. Попробуйте еще раз.")
                else:
                    await message.answer(f"❌ Ошибка генерации (Код {resp.status}). Попробуйте позже.")

        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:150]}")

async def main():
    logging.info("🚀 Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
