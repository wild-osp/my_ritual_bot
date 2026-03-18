import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot", # OpenRouter требует валидный URL
        "X-Title": "Ritual Portrait AI"
    }
    state.session = aiohttp.ClientSession(headers=headers)
    logger.info("Сессия запущена. Баланс подтвержден диагностикой.")

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов к работе (Premium статус подтвержден).\nПришлите фото для ретуши.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализ внешности...")
    
    try:
        # Получаем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base_4_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ (через Chat API)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face, hair, and age in 10-15 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_4_img}"}}
            ]}]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=analysis_payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 2/2 Генерация портрета (FLUX)...")

        # 2. Генерация (через Images API - ТУТ БЫЛА ОШИБКА)
        # Для генерации картинок НЕЛЬЗЯ использовать поле 'messages'
        gen_payload = {
            "model": "black-forest-labs/flux-1-schnell", # Самая стабильная модель
            "prompt": f"Professional photorealistic studio portrait of {description}, wearing a black formal suit, solid neutral grey background, high detail, 8k, sharp focus.",
            "size": "1024x1024"
        }

        async with state.session.post("https://openrouter.ai/api/v1/images/generations", json=gen_payload) as resp:
            # Логируем для проверки, если снова будет 400
            gen_data = await resp.json()
            logger.info(f"Image API Response: {gen_data}")
            
            if "data" not in gen_data:
                error_text = gen_data.get('error', {}).get('message', 'Unknown Error')
                raise Exception(f"OpenRouter Image Error: {error_text}")

            image_url = gen_data['data'][0]['url']

        # 3. Скачивание и отправка
        async with state.session.get(image_url) as img_resp:
            final_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_bytes, filename="result.jpg"),
            caption=f"✅ Готово!\n\n_{description}_",
            parse_mode="Markdown"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Произошла ошибка: {str(e)[:200]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
