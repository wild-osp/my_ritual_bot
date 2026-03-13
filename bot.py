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
    await message.answer("✅ Бот Nano Banana готов! Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ черт лица...")
    
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
                    {"type": "text", "text": "Describe the person's face briefly. No punctuation. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Генерация (ждем готовности фото)...")

        # 2. Очистка и формирование ссылки
        clean_desc = re.sub(r'[^a-zA-Z\s]', '', person_desc).replace('\n', ' ').strip()
        final_prompt = f"professional memorial portrait of {clean_desc} formal grey shirt grey background mourning ribbon bottom right hyperrealistic 8k"
        encoded_prompt = urllib.parse.quote(final_prompt)
        
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={message.message_id}&model=flux&nologo=true"

        # 3. Цикл ожидания генерации
        final_image_data = None
        async with aiohttp.ClientSession() as session:
            for attempt in range(1, 7):  # Делаем 6 попыток (всего 30 секунд)
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        # Если размер больше 30Кб — это уже не логотип, а наше фото
                        if len(data) > 30000:
                            final_image_data = data
                            break
                logging.info(f"Попытка {attempt}: фото еще рисуется...")
                await asyncio.sleep(5) # Ждем 5 секунд перед следующей проверкой

        # 4. Отправка результата
        if final_image_data:
            photo_file = BufferedInputFile(final_image_data, filename="retouch.jpg")
            await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!")
        else:
            await message.answer("❌ Сервер не успел создать фото. Попробуйте отправить еще раз.")

        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
