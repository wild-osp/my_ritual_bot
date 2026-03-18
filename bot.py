import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
PROXY_URL = os.getenv("PROXY_URL") # Например: http://user:pass@ip:port

# Настройка сессии для Telegram (с прокси, если есть)
session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    # Для OpenRouter прокси обычно не нужен, но если сервер в РФ - может понадобиться
    state.session = aiohttp.ClientSession(
        headers={
            "Authorization": f"Bearer {API_KEY.strip()}",
            "Content-Type": "application/json",
        }
    )

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот запущен. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализирую...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. АНАЛИЗ (Gemini)
        analysis_body = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe person face and hair concisely (10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=analysis_body) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content']

        await status.edit_text(f"🎨 Генерирую образ: {description}...")

        # 2. ГЕНЕРАЦИЯ (Используем SDXL - самый стабильный ID)
        gen_body = {
            "model": "stabilityai/stable-diffusion-xl",
            "prompt": f"Professional photorealistic studio portrait of {description}, wearing a black formal suit, grey background, sharp focus, 8k",
            "response_format": "b64_json"
        }

        # ВАЖНО: SDXL часто требует эндпоинт /images/generations
        async with state.session.post("https://openrouter.ai/api/v1/images/generations", json=gen_body) as resp:
            gen_data = await resp.json()
            
            if "data" not in gen_data:
                # Если не сработало, пробуем через чат-эндпоинт как запасной вариант
                raise Exception(f"API Error: {gen_data.get('error', {}).get('message', 'No data')}")
            
            image_raw = base64.b64decode(gen_data['data'][0]['b64_json'])

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(image_raw, filename="res.jpg"),
            caption=f"✅ Готово\n{description}"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
