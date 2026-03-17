import os
import asyncio
import logging
import base64
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ Бот готов к работе. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Обработка черт лица...")
    try:
        # 1. Анализ фото
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair, glasses. 5 words max. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        # ОЧИСТКА: Убираем запятые, точки и лишние пробелы
        description = response.choices[0].message.content.strip()
        clean_desc = re.sub(r'[^\w\s]', '', description).replace(" ", "%20")
        
        logging.info(f"Чистое описание: {clean_desc}")
        await status.edit_text("🎨 Создаю портрет в костюме...")

        # 2. Формируем ссылку БЕЗ лишних знаков
        image_url = f"https://image.pollinations.ai/prompt/Professional%20studio%20portrait%20of%20{clean_desc}%20wearing%20formal%20black%20suit%20grey%20background?nologo=true&width=1024&height=1024"

        # 3. Отправка (Передаем ссылку Телеграму, пусть он сам её подтянет)
        await bot.send_photo(
            message.chat.id, 
            photo=URLInputFile(image_url), 
            caption=f"✨ Готово!\nОписание: {description}"
        )
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await status.edit_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
