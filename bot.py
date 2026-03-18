import os
import asyncio
import base64
import logging
import aiohttp
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from aiogram.utils.markdown import hlink
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
        "Content-Type": "application/json"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Отправьте фото (ретушь в костюм).")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализ...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Анализ через OpenRouter (этот этап у тебя работает)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe face and age in 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 2/2 Генерация...")

        # Формируем промпт (сделал короче для надежности)
        prompt = f"Portrait of {description}, formal black suit, grey background, 8k, realistic"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Ссылка на генерацию
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed=123"

        # Попытка скачать изображение
        try:
            async with state.session.get(image_url, timeout=20) as img_resp:
                if img_resp.status == 200:
                    final_bytes = await img_resp.read()
                    await bot.send_photo(
                        message.chat.id,
                        BufferedInputFile(final_bytes, filename="res.jpg"),
                        caption=f"✅ Готово!\n_{description}_"
                    )
                    await status.delete()
                    return
                else:
                    raise Exception("Server busy")
        except Exception as e:
            # ЕСЛИ СКАЧАТЬ НЕ ВЫШЛО — ПРОСТО ДАЕМ ССЫЛКУ
            logger.warning(f"Download failed, giving link: {e}")
            await status.edit_text(
                f"✅ Портрет готов!\n\nК сожалению, не удалось загрузить файл напрямую, но вы можете открыть его по ссылке:\n\n🔗 [СМОТРЕТЬ ПОРТРЕТ]({image_url})",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
