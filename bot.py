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
        "Content-Type": "application/json"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Режим коротких ссылок включен. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализ лица...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Запрос к Gemini: просим СУПЕР короткое описание
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe this person in 4 words only. No punctuation. Example: elderly bald man glasses"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()
            # Очистка: только латиница и пробелы
            description = re.sub(r'[^a-zA-Z ]', '', description)

        await status.edit_text("🎨 2/2 Генерация фото...")

        # Формируем максимально короткую и чистую ссылку
        prompt_text = f"portrait of {description} in black suit on grey background 8k"
        encoded_prompt = urllib.parse.quote(prompt_text)
        
        # Ссылка БЕЗ лишних параметров, чтобы не злить сервер
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=1024&nologo=true&seed={os.urandom(2).hex()}"

        # Попытка скачать
        async with state.session.get(image_url, timeout=40) as img_resp:
            if img_resp.status == 200:
                img_data = await img_resp.read()
                if len(img_data) > 10000: # Проверка, что это картинка, а не текст ошибки
                    await bot.send_photo(
                        message.chat.id,
                        BufferedInputFile(img_data, filename="res.jpg"),
                        caption=f"✅ Готово!\n_{description}_"
                    )
                    await status.delete()
                    return

        # Если не скачалось, даем ссылку текстом
        await status.edit_text(f"✅ Готово! Нажмите, чтобы открыть:\n\n{image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка. Попробуйте еще раз.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
