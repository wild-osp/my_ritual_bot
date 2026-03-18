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
    # ВАЖНО: Добавляем обязательные заголовки OpenRouter
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot_link", # Замени на ссылку на своего бота
        "X-Title": "Ritual Retouch Bot v2"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Баланс обнаружен! Использую премиум-модель FLUX для вашего фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Шаг 1: Глубокий анализ лица...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Используем Gemini 2.0 Flash для анализа (самая стабильная)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Precisely describe the person's face, hair, and age. Output only description, max 15 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=analysis_payload) as resp:
            data = await resp.json()
            if "choices" not in data:
                raise Exception(f"OpenRouter Auth Error: {data.get('error', {}).get('message')}")
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 Шаг 2: Генерация через FLUX (Premium)...")

        # ГЕНЕРАЦИЯ: Если есть $5, FLUX Schnell - лучший выбор по цене/качеству
        gen_payload = {
            "model": "black-forest-labs/flux-1-schnell",
            "messages": [{"role": "user", "content": f"A professional high-quality photorealistic studio portrait of {description}, wearing a black formal suit, solid grey background, sharp focus, 8k resolution, highly detailed skin."}]
        }

        async with state.session.post(URL, json=gen_payload) as resp:
            gen_data = await resp.json()
            logger.info(f"FLUX Response: {gen_data}")
            
            if "choices" not in gen_data:
                # Если 5 долларов не помогли, значит проблема в ID модели. Пробуем резервный SDXL
                logger.warning("FLUX failed, trying SDXL...")
                gen_payload["model"] = "stabilityai/stable-diffusion-xl"
                async with state.session.post(URL, json=gen_payload) as resp_retry:
                    gen_data = await resp_retry.json()

            if "choices" not in gen_data:
                raise Exception(f"Ошибка баланса/модели: {gen_data.get('error', {}).get('message')}")

            content = gen_data['choices'][0]['message']['content']
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                raise Exception("AI не вернул прямую ссылку на изображение.")
            
            img_url = urls[0].strip("()[]\"' ")

        # Скачивание и отправка
        async with state.session.get(img_url) as img_resp:
            final_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_bytes, filename="res.jpg"),
            caption=f"✅ Готово!\n\n_{description}_",
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
