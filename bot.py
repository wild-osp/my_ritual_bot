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
    state.session = aiohttp.ClientSession(headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/ritual_bot"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🚀 Режим повышенной стабильности включен. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Шаг 1: Анализ лица (Gemini)...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base_4_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Анализ (тратим баланс на Gemini)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age and face features in 5 words. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_4_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()
            # Убираем всё, кроме букв и цифр для URL
            clean_desc = re.sub(r'[^a-zA-Z0-9 ]', '', description)

        await status.edit_text("🎨 Шаг 2: Генерация через FLUX...")

        # ВАЖНО: Используем модель FLUX, а не SANA
        image_url = f"https://image.pollinations.ai/prompt/portrait%20of%20{urllib.parse.quote(clean_desc)}%20in%20black%20suit%20grey%20background%208k%20highly%20detailed?model=flux&width=1024&height=1024&nologo=true&seed={os.urandom(2).hex()}"

        # Скачиваем результат
        async with state.session.get(image_url, timeout=45) as img_resp:
            if img_resp.status == 200:
                content = await img_resp.read()
                # Если вместо картинки пришел JSON с ошибкой - ловим это
                if b"error" in content[:100]:
                    raise Exception("Сервер прислал ошибку вместо фото")
                
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(content, filename="ritual.jpg"),
                    caption=f"✅ Готово!\n_{description}_"
                )
                await status.delete()
            else:
                await status.edit_text(f"⚠️ Сервер временно перегружен. Попробуйте по прямой ссылке через минуту:\n\n{image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
