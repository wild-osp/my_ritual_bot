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
        "HTTP-Referer": "https://t.me/ritual_retouch_bot",
        "X-Title": "Ritual AI Expert"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Начинаю поиск активной графической модели...")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("🔍 Шаг 1: Анализ лица (Gemini)...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Анализ (Gemini 2.0 работает стабильно)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair and face concisely (10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()

        await status.edit_text(f"🎨 Шаг 2: Поиск рабочей модели генерации...")

        # Список ID моделей для перебора (OpenRouter постоянно их меняет)
        model_variants = [
            "black-forest-labs/flux-schnell", 
            "stabilityai/sdxl", 
            "openai/dall-e-3",
            "google/gemini-2.0-pro-exp-02-15:free" # Резерв, если платные не пускают
        ]

        final_url = None
        for model_id in model_variants:
            logger.info(f"Пробую модель: {model_id}")
            gen_payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"Professional studio portrait of {description}, wearing a black formal suit, solid grey background, 8k resolution, highly detailed."}]
            }

            try:
                async with state.session.post(URL, json=gen_payload) as resp:
                    gen_data = await resp.json()
                    
                    if "choices" in gen_data:
                        content = gen_data['choices'][0]['message']['content']
                        urls = re.findall(r'https?://\S+', content)
                        if urls:
                            final_url = urls[0].strip("()[]\"' ")
                            logger.info(f"Успех с моделью {model_id}!")
                            break
                    else:
                        logger.warning(f"Модель {model_id} отклонила запрос: {gen_data.get('error')}")
            except Exception as e:
                logger.error(f"Ошибка при вызове {model_id}: {e}")

        if not final_url:
            raise Exception("Ни одна графическая модель не приняла ваш API ключ. Проверьте баланс на сайте OpenRouter.")

        # Скачивание
        async with state.session.get(final_url) as img_resp:
            final_bytes = await img_resp.read()

        await bot.send_photo(message.chat.id, BufferedInputFile(final_bytes, filename="res.jpg"))
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ {str(e)[:150]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
