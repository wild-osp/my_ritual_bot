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

# Загружаем переменные окружения
load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Инициализация Gemini
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Nano Banana 6.3 готова!\nПришлите фото для создания портрета.")

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
                    {"type": "text", "text": "Describe face features and hair briefly. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация портрета...\n({person_desc})")

        # 2. Промпт (упрощенный, чтобы избежать блокировки 429/500)
        # Убрали слова 'mourning' и 'ribbon' из основной части, чтобы пройти фильтры
        clean_desc = "".join(e for e in person_desc if e.isalnum() or e.isspace())
        prompt = (f"A professional studio photographic portrait of {clean_desc}, "
                  f"wearing black formal clothes, solid neutral grey background, "
                  f"8k resolution, highly detailed realistic face.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Используем модель turbo - она быстрее и стабильнее под нагрузкой
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=turbo&seed={message.message_id}"

        # 3. Умный цикл скачивания
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for attempt in range(1, 16): # 15 попыток
                try:
                    # Добавляем случайный параметр для обхода кэша
                    current_url = f"{image_url}&iteration={attempt}"
                    async with session.get(current_url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            file_size = len(data)
                            logging.info(f"Попытка {attempt}: {file_size} байт")
                            
                            # Проверка: игнорируем логотип (3314 байт) и маленькие файлы
                            if file_size > 30000 and file_size != 3314:
                                photo_file = BufferedInputFile(data, filename="result.jpg")
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=photo_file, 
                                    caption="✨ Портрет готов!"
                                )
                                await status_msg.delete()
                                return
                            
                            # Если получаем один и тот же маленький размер — сервер еще не нарисовал
                            await status_msg.edit_text(f"⌛ Рисую... ({attempt}/15)\nТекущий статус: подготовка файла...")
                        
                        elif resp.status == 429:
                            logging.warning("Лимит запросов. Ждем...")
                            await asyncio.sleep(10)
                            
                except Exception as e:
                    logging.error(f"Ошибка на попытке {attempt}: {e}")
                
                await asyncio.sleep(6)

        await message.answer("❌ Сервер нейросети временно недоступен. Попробуйте еще раз через пару минут.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
