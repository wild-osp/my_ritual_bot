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

# Загружаем переменные
load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Настройка клиента OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Бот Nano Banana 6.2 готов!\nОтправьте фото, и я начну ретушь.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
    # 1. Получаем фото от пользователя
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # Анализ через Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe face, hair and eyes. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Генерация...\n({person_desc})")

        # 2. Формируем запрос для картинки
        clean_desc = "".join(e for e in person_desc if e.isalnum() or e.isspace())
        prompt = f"Professional memorial studio portrait of {clean_desc} wearing formal dark suit and grey background with black mourning ribbon in corner 8k"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # URL генератора (используем стабильный путь)
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={message.message_id}"

        # 3. Цикл скачивания с логированием размера
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for attempt in range(1, 21): # До 20 попыток (около 100 секунд)
                try:
                    # Кэш-бастинг, чтобы не получать старый результат
                    current_url = f"{image_url}&cb={attempt}"
                    async with session.get(current_url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            file_size = len(data)
                            
                            # Логируем в консоль и обновляем статус в ТГ каждые 3 попытки
                            logging.info(f"Попытка {attempt}: Размер файла {file_size} байт")
                            
                            if file_size > 35000: # Если больше 35 Кб — это фото, а не лого
                                photo_file = BufferedInputFile(data, filename="result.jpg")
                                await bot.send_photo(
                                    message.chat.id, 
                                    photo=photo_file, 
                                    caption=f"✨ Ретушь готова!\n(Размер: {file_size // 1024} Кб)"
                                )
                                await status_msg.delete()
                                return
                            else:
                                if attempt % 2 == 0:
                                    await status_msg.edit_text(f"⌛ Рисую... Попытка {attempt}/20\n(Текущий вес: {file_size} байт)")
                        else:
                            logging.warning(f"Попытка {attempt}: Код {resp.status}")
                except Exception as e:
                    logging.error(f"Ошибка на попытке {attempt}: {e}")
                
                await asyncio.sleep(5)

        await message.answer("❌ Превышено время ожидания. Попробуйте отправить другое фото.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
