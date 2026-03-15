import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Ключи
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ Бот активен. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Обработка...")
    try:
        # 1. Получаем описание через Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe person: age, hair, glasses. 5 words max. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip().replace(" ", "%20")
        
        # 2. Формируем УЛЬТРА-короткую ссылку (чтобы не было 500 ошибки)
        # Мы используем модель flux, она самая качественная
        image_url = f"https://image.pollinations.ai/prompt/professional%20studio%20portrait%20{desc}%20black%20suit%20grey%20background?width=1024&height=1024&model=flux&nologo=true"
        
        # 3. Отправляем результат
        await bot.send_photo(
            message.chat.id, 
            photo=URLInputFile(image_url), 
            caption="✨ Готово!"
        )
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Сбой. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
