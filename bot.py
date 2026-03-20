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
        "X-Title": "Ritual AI Expert"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов к работе. Пришлите фото для ритуальной ретуши.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализирую лицо через Gemini...")
    
    try:
        # 1. Анализ (уже проверено, работает!)
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe this person's face for AI generation. Use 15-20 words, focus on age, wrinkles, and unique features. No intro."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()
            # Чистим описание для URL
            clean_desc = re.sub(r'[^a-zA-Z0-9 ]', '', description)

        await status.edit_text("🎨 2/2 Генерирую файл портрета (Flux)...")

        # 2. Формируем промпт для генерации
        full_prompt = f"Professional studio portrait of {clean_desc}, wearing black formal suit, white shirt, neutral grey background, 8k, photorealistic"
        encoded_prompt = urllib.parse.quote(full_prompt)
        
        # Используем путь /p/ и модель flux (этот вариант самый живучий)
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={os.urandom(2).hex()}"

        # 3. Попытка скачать и отправить файл
        try:
            async with state.session.get(image_url, timeout=35) as img_resp:
                if img_resp.status == 200:
                    img_data = await img_resp.read()
                    
                    # Если вдруг пришла текстовая ошибка вместо картинки
                    if len(img_data) < 5000:
                        raise Exception("Ошибка сервера генерации")

                    await bot.send_photo(
                        message.chat.id,
                        BufferedInputFile(img_data, filename="result.jpg"),
                        caption="✅ Ретушь готова"
                    )
                    await status.delete()
                    return
        except Exception as e:
            logger.warning(f"Download failed, giving link: {e}")
            # Если не скачалось, даем ссылку, но ПРАВИЛЬНУЮ
            await status.edit_text(
                f"✅ Портрет готов!\n\nНе удалось загрузить файл в Telegram, но вы можете скачать его по ссылке:\n\n🔗 [ОТКРЫТЬ ПОРТРЕТ]({image_url})",
                parse_mode="Markdown"
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
