import os
import asyncio
import base64
import logging
import aiohttp
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
# ТОЛЬКО ЭТОТ URL РАБОТАЕТ НА OPENROUTER
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
        "X-Title": "Ritual AI Retouch"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Баланс подтвержден. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализ лица...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ (Gemini) - это у нас уже работало
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face and hair in 10 words for a portrait."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=analysis_payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content']

        await status.edit_text(f"🎨 Генерирую через FLUX...")

        # 2. ГЕНЕРАЦИЯ (Через Chat Completions, но спец-формат)
        # ВНИМАНИЕ: Используем 'black-forest-labs/flux-1-schnell' как проверенный ID
        gen_payload = {
            "model": "black-forest-labs/flux-1-schnell",
            "messages": [
                {
                    "role": "user", 
                    "content": f"Generate a high-quality professional photorealistic studio portrait of {description}, wearing a black suit, solid grey background, sharp focus, 8k resolution."
                }
            ],
            "extra_body": {
                "response_format": {"type": "json_object"}
            }
        }

        async with state.session.post(URL, json=gen_payload) as resp:
            gen_data = await resp.json()
            logger.info(f"FLUX Chat Response: {gen_data}")
            
            if "choices" not in gen_data:
                err = gen_data.get('error', {}).get('message', 'Unknown')
                raise Exception(f"OpenRouter Error: {err}")

            # OpenRouter для FLUX в чате возвращает ссылку прямо в тексте сообщения
            content = gen_data['choices'][0]['message']['content']
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                # Если ссылка не в тексте, проверяем поле 'url' в вложениях (редко, но бывает)
                raise Exception(f"AI не прислал ссылку. Ответ: {content[:100]}")
            
            image_url = urls[0].strip("()[]\"' ")

        # 3. Скачивание
        async with state.session.get(image_url) as img_resp:
            final_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_bytes, filename="res.jpg"),
            caption=f"✅ Готово!\n_{description}_",
            parse_mode="Markdown"
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
