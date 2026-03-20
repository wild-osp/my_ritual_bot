import os
import asyncio
import base64
import logging
import aiohttp
import urllib.parse
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = "https://openrouter.ai/api/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/ritual_bot",
        "X-Title": "Ritual Photo Fix"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Ключ активен, баланс в порядке! Пришлите фото для обработки.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализирую внешность через Gemini...")
    
    try:
        # 1. Анализ фото (Тут твой баланс OpenRouter и тратится)
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair, and face features concisely (max 10 words). Output only text."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=analysis_payload) as resp:
            data = await resp.json()
            if "choices" not in data:
                raise Exception(f"OpenRouter Error: {data}")
            description = data['choices'][0]['message']['content'].strip()
            # Очистка описания от мусора
            description = re.sub(r'[^a-zA-Z0-9 ]', '', description)

        await status.edit_text(f"🎨 Генерирую ритуальный портрет...")

        # 2. Формируем ссылку (Flux модель - самая мощная)
        prompt = f"Professional studio portrait of {description}, formal black suit, white shirt, neutral grey background, high resolution, 8k, realistic"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Используем мощный и быстрый инстанс Flux
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux"

        # 3. Попытка скачивания с повторами (если сервер занят)
        final_image = None
        for attempt in range(3):
            try:
                async with state.session.get(image_url, timeout=25) as img_resp:
                    if img_resp.status == 200:
                        final_image = await img_resp.read()
                        break
                await asyncio.sleep(2) # Пауза перед повтором
            except:
                continue

        if final_image:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(final_image, filename="res.jpg"),
                caption=f"✅ Готово!\n_{description}_"
            )
            await status.delete()
        else:
            # Если скачать не вышло, даем прямую ссылку
            await status.edit_text(f"✅ Готово! Нажмите на ссылку, чтобы открыть фото:\n\n{image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
