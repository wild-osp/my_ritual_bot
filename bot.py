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

# Загружаем переменные (TELEGRAM_TOKEN и OPENROUTER_KEY) из Bothost
load_dotenv()

# Настройка логирования
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
    await message.answer("🚀 Nano Banana 5.6 готова к работе!\nПришлите фото для мемориальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ фото через Gemini...")
    
    # Получаем фото
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Запрос к Gemini для описания
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Briefly describe hair, eyes, and clothes. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация портрета...\n(Описание: {person_desc})")

        # 2. Подготовка промпта
        # Очищаем описание от лишних символов
        clean_desc = "".join(c for c in person_desc if c.isalnum() or c.isspace())
        prompt = (f"A high-quality professional memorial studio portrait of {clean_desc}, "
                  f"wearing a formal dark suit, neutral grey studio background, "
                  f"a black diagonal mourning ribbon in the bottom right corner, 8k, realistic.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Используем прямой путь к API
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={message.message_id}"

        # 3. Цикл получения картинки с защитой от 429
        connector = aiohttp.TCPConnector(ssl=False)
        # Заголовки, чтобы сервер не видел в нас бота
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        async with aiohttp.ClientSession(connector=connector) as session:
            for attempt in range(1, 11): # 10 попыток
                try:
                    async with session.get(image_url, headers=headers, timeout=60) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 30000:
                                photo_file = BufferedInputFile(data, filename="result.jpg")
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=photo_file, 
                                    caption="✨ Ретушь выполнена успешно!"
                                )
                                await status_msg.delete()
                                return
                            else:
                                logging.info(f"Попытка {attempt}: Ждем генерацию...")
                        
                        elif resp.status == 429:
                            logging.warning(f"Попытка {attempt}: Лимит (429). Ждем 15 секунд...")
                            await asyncio.sleep(15) # Увеличенная пауза при лимите
                            continue
                        
                        else:
                            logging.error(f"Попытка {attempt}: Статус {resp.status}")
                            
                except Exception as e:
                    logging.error(f"Ошибка в цикле: {str(e)}")
                
                # Обычная пауза между запросами
                await asyncio.sleep(8)

        await message.answer("❌ Сервер перегружен. Попробуйте еще раз через пару минут.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
