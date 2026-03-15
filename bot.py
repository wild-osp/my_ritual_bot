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

# Настройка подробного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

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
    await message.answer("🚀 Nano Banana 7.3 (Debug Mode) запущена!\nОтправьте фото для анализа и ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("🔍 Шаг 1: Анализ через Gemini...")
    logger.info("Получено фото, начинаю обработку...")
    
    # Скачиваем фото
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
                    {"type": "text", "text": "Identify age, gender, hair, and eye color. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        logger.info(f"Gemini описание: {person_desc}")
        
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация портрета...\nОписание: {person_desc}")

        # 2. Формируем промпт
        prompt = (f"A professional memorial studio portrait of {person_desc}, "
                  f"wearing black formal clothes, solid grey background, "
                  f"black diagonal mourning ribbon in corner, 8k resolution, realistic.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Принудительно используем модель flux для лучшего качества
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={message.message_id}"

        # 3. Цикл отладки и получения картинки
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for attempt in range(1, 26): # 25 попыток по 6 секунд = 150 секунд ожидания
                try:
                    # Кэш-бастинг (добавляем уникальный параметр, чтобы сервер не отдавал старый файл)
                    current_url = f"{image_url}&v={attempt}"
                    
                    async with session.get(current_url, timeout=40) as resp:
                        content_type = resp.headers.get('Content-Type', 'unknown')
                        data = await resp.read()
                        file_size = len(data)
                        
                        logger.info(f"Попытка {attempt}: Статус {resp.status}, Размер {file_size} байт, Тип: {content_type}")
                        
                        # Обновляем статус пользователю
                        if attempt % 2 == 0:
                            await status_msg.edit_text(
                                f"⏳ Генерация (Попытка {attempt}/25)\n"
                                f"📥 Получено: {file_size // 1024} Кб\n"
                                f"⚙️ Статус сервера: {resp.status}"
                            )

                        # Если размер больше 40 Кб — это уже не логотип и не пустой ответ
                        if resp.status == 200 and file_size > 40000:
                            logger.info(f"✅ Успех! Картинка получена на попытке {attempt}")
                            photo_file = BufferedInputFile(data, filename="retouch.jpg")
                            await bot.send_photo(
                                message.chat.id, 
                                photo=photo_file, 
                                caption=f"✨ Ретушь готова!\nПопыток: {attempt}\nРазмер: {file_size // 1024} Кб"
                            )
                            await status_msg.delete()
                            return
                        
                        # Если сервер выдал ошибку 429 или 500 — делаем паузу дольше
                        if resp.status in [429, 500, 503]:
                            logger.warning(f"Сервер перегружен ({resp.status}), ждем дольше...")
                            await asyncio.sleep(10)
                            continue

                except Exception as e:
                    logger.error(f"Ошибка внутри цикла на попытке {attempt}: {str(e)}")
                
                await asyncio.sleep(6)

        await message.answer("⚠️ Время ожидания истекло. Сервер не успел сгенерировать файл высокого качества. Попробуйте еще раз.")
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:100]}")

async def main():
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
