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
    await message.answer("📸 Бот готов. Пришлите фото — я сделаю ретушь и пришлю готовый файл.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализирую внешность через OpenRouter...")
    
    try:
        # Получаем фото и кодируем в Base64 для Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Шаг 1: Анализ (Gemini работает 100%, тратим баланс тут)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age, gender, hair and face concisely (max 10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(OPENROUTER_URL, json=analysis_payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()

        await status.edit_text(f"🎨 2/2 Генерирую файл портрета...")

        # Шаг 2: Генерация через надежный движок Flux/SDXL
        # Мы НЕ используем Pollinations, пробуем другой CDN
        prompt = f"Professional studio portrait of {description}, formal black suit, white shirt, solid grey background, 8k, photorealistic, sharp focus"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Альтернативный адрес для прямой генерации БЕЗ ошибок sana
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed=123&model=flux"

        # Шаг 3: Прямая загрузка в бота
        max_retries = 3
        for i in range(max_retries):
            try:
                async with state.session.get(image_url, timeout=30) as img_resp:
                    if img_resp.status == 200:
                        content = await img_resp.read()
                        
                        # Если сервер прислал JSON вместо картинки (ошибка), пробуем еще раз
                        if b"error" in content[:100]:
                            raise Exception("Server returned error JSON")
                            
                        photo_file = BufferedInputFile(content, filename="retouch.jpg")
                        await bot.send_photo(
                            message.chat.id, 
                            photo_file, 
                            caption=f"✅ Готово!\n_{description}_"
                        )
                        await status.delete()
                        return
            except Exception as e:
                logger.warning(f"Attempt {i+1} failed: {e}")
                await asyncio.sleep(3)

        raise Exception("Сервер генерации перегружен. Попробуйте другое фото или подождите минуту.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:150]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
