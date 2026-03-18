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

# Конфиг
API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    state.session = aiohttp.ClientSession(headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Ritual Photo Bot"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🤖 Бот готов. Пришлите фото, я сделаю ретушь через SDXL.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Шаг 1: Анализ лица...")
    
    try:
        # Получаем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ (Gemini - самая дешевая и быстрая для зрения)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face features, hair and age very briefly (max 10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(BASE_URL, json=analysis_payload) as resp:
            res_data = await resp.json()
            if "choices" not in res_data:
                raise Exception(f"Ошибка анализа: {res_data}")
            description = res_data['choices'][0]['message']['content']

        await status.edit_text(f"⏳ Шаг 2: Генерация портрета...")

        # 2. Генерация (SDXL через чат-интерфейс)
        gen_payload = {
            "model": "stabilityai/stable-diffusion-xl",
            "messages": [{"role": "user", "content": f"Generate a professional photo portrait of {description}, wearing a black suit, solid grey background, photorealistic, 8k"}]
        }

        async with state.session.post(BASE_URL, json=gen_payload) as resp:
            gen_data = await resp.json()
            logger.info(f"Full Gen Response: {gen_data}")
            
            if "choices" not in gen_data:
                err = gen_data.get('error', {}).get('message', 'Неизвестная ошибка')
                raise Exception(f"Ошибка OpenRouter: {err}")

            # Ищем URL в ответе (OpenRouter возвращает его в поле content)
            content = gen_data['choices'][0]['message']['content']
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                raise Exception("AI не выдал ссылку на картинку. Возможно, недостаточно средств.")
            
            final_url = urls[0].strip("()[]\"' ")

        # 3. Скачивание результата
        async with state.session.get(final_url) as img_resp:
            image_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(image_bytes, filename="result.jpg"),
            caption=f"✅ Готово!\n_{description}_",
            parse_mode="Markdown"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:200]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
