import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 1. Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# 2. Проверка токенов
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

if not TELEGRAM_TOKEN:
    logger.error("❌ ОШИБКА: TELEGRAM_TOKEN не найден в переменных окружения!")
if not OPENROUTER_KEY:
    logger.error("❌ ОШИБКА: OPENROUTER_KEY не найден в переменных окружения!")

# 3. Инициализация
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ Бот Nano Banana снова в строю!\nПришлите фото, я готов к ретуши.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ фото...")
    
    try:
        # Получаем фото
        file = await bot.get_file(message.photo[-1].file_id)
        photo_content = await bot.download_file(file.file_path)
        base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
        
        # Описание через Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Briefly describe this person's face. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация через Flux...\n({desc})")

        # Прямая ссылка на Pollinations (бесплатная, но через стабильный шлюз)
        prompt = f"Professional studio portrait of {desc}, black suit, grey background, realistic, 8k"
        image_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true&model=flux&seed={message.message_id}"

        await bot.send_photo(message.chat.id, photo=URLInputFile(image_url), caption="✨ Ретушь готова!")
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
