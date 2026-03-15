import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import URLInputFile
from dotenv import load_dotenv

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Клиент OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    logger.info(f"Команда /start от {message.from_user.id}")
    await message.answer("🚀 VIP Бот 9.6 онлайн!\nПришлите фото для ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    logger.info(f"Получено фото от {message.from_user.id}")
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
    try:
        # Скачивание фото
        file = await bot.get_file(message.photo[-1].file_id)
        photo_content = await bot.download_file(file.file_path)
        base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
        
        # 1. Анализ через Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the person's face briefly. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        description = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация портрета...\n({description})")

        # 2. Промпт
        prompt = f"Professional studio portrait of {description}, black formal clothes, grey background, 8k, photorealistic"

        # 3. Запрос к модели FLUX (через OpenRouter)
        # Если flux-schnell не сработает, попробуем просто 'pro' модель
        image_response = await client.chat.completions.create(
            model="google/gemini-2.0-pro-exp-02-15", # Используем Pro версию Gemini, она умеет вызывать инструменты
            messages=[{"role": "user", "content": f"Generate a high-quality image based on this prompt: {prompt}"}]
        )

        res_content = image_response.choices[0].message.content.strip()
        logger.info(f"Ответ сервера: {res_content}")

        if "http" in res_content:
            url = res_content.split("http")[-1].split()[0].strip("()[]")
            url = "http" + url
            await bot.send_photo(message.chat.id, photo=URLInputFile(url), caption="✨ Готово!")
        else:
            # Если всё равно прилетает текст, используем проверенный Pollinations, но с уникальным сидом
            logger.info("OpenRouter вернул текст, переключаюсь на резервный канал...")
            fallback_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=1024&height=1024&model=flux&nologo=true&seed={message.message_id}"
            await bot.send_photo(message.chat.id, photo=URLInputFile(fallback_url), caption="✨ Готово (Резервный канал)")
        
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка в обработчике: {e}")
        await message.answer(f"❌ Произошла ошибка. Попробуйте еще раз.")

async def main():
    logger.info("Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
