import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Загрузка ключей
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Инициализация клиентов
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ **Ритуальная Ретушь 11.0**\n\nПришлите фото человека, и я создам профессиональный студийный портрет для мемориальных целей.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status_msg = await message.answer("🔍 Шаг 1: Анализ черт лица...")
    
    try:
        # Скачивание и подготовка фото
        file = await bot.get_file(message.photo[-1].file_id)
        photo_content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(photo_content.getvalue()).decode('utf-8')
        
        # 1. Анализ через Gemini
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe age, gender, hair, and face features. Max 12 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }]
        )
        description = analysis.choices[0].message.content.strip()
        logger.info(f"Gemini description: {description}")
        
        await status_msg.edit_text(f"🎨 Шаг 2: Создание портрета...\n({description})")

        # 2. Формируем промпт
        prompt = (f"A hyper-realistic professional studio memorial portrait of {description}, "
                  f"wearing a formal dark suit, neutral grey studio background, "
                  f"cinematic lighting, sharp focus, 8k resolution, masterpiece.")

        # 3. Платная генерация через OpenRouter (Пробуем универсальный ID)
        try:
            # Используем модель, которая на OpenRouter сейчас лучше всего работает с изображениями
            image_gen = await client.chat.completions.create(
                model="openai/dall-e-3", # Если на балансе есть $, это приоритет
                messages=[{"role": "user", "content": prompt}]
            )
            result_url = image_gen.choices[0].message.content.strip()
            
            # Если вернулась ссылка — отправляем
            if "http" in result_url:
                clean_url = result_url.split("http")[-1].split()[0].strip("()[]")
                await bot.send_photo(message.chat.id, photo=URLInputFile("http" + clean_url), caption="✨ Ретушь готова (VIP)")
                await status_msg.delete()
                return
        except Exception as e:
            logger.warning(f"Платный канал недоступен, перехожу на резерв: {e}")

        # 4. Резервный канал (Бесплатный Flux, если платный упал)
        fallback_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=1024&height=1024&model=flux&nologo=true&seed={message.message_id}"
        await bot.send_photo(message.chat.id, photo=URLInputFile(fallback_url), caption="✨ Ретушь готова (Standard)")
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        await message.answer("❌ Не удалось обработать фото. Попробуйте другое изображение.")

async def main():
    logger.info("Бот запущен и готов к работе!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
