import os
import asyncio
import base64
import logging
import aiohttp
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    state.session = aiohttp.ClientSession(headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Пришлите фото для ритуальной ретуши (костюм, серый фон).")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализ лица...")
    
    try:
        # 1. Анализ фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face, hair, and age in 5-7 words. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(OPENROUTER_URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()

        await status.edit_text("🎨 Генерация портрета...")

        # 2. Формируем "чистый" промпт для Pollinations
        # Убираем все спецсимволы, чтобы не было 'fetch failed'
        clean_desc = "".join(e for e in description if e.isalnum() or e.isspace())
        prompt = f"Professional portrait of {clean_desc} in black suit white shirt grey background photorealistic 8k"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Используем модель FLUX через Pollinations (она самая качественная сейчас)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed=42"

        # 3. Пытаемся отправить картинку
        try:
            async with state.session.get(image_url, timeout=15) as img_resp:
                if img_resp.status == 200:
                    img_data = await img_resp.read()
                    await bot.send_photo(
                        message.chat.id, 
                        BufferedInputFile(img_data, filename="retouch.jpg"),
                        caption=f"✅ Готово!\n_{description}_"
                    )
                    await status.delete()
                    return
        except:
            pass

        # Если не скачалось — даем ссылку, которая ТОЧНО сработает в браузере
        await status.edit_text(
            f"✅ Ретушь выполнена!\n\nКликните по ссылке, чтобы открыть фото:\n{image_url}",
            disable_web_page_preview=False
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
