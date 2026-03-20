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
    # Заголовки для ПЛАТНОГО аккаунта (как у тебя)
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/my_retouch_task_bot",
        "X-Title": "Ritual AI Pro"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🚀 Бот переведен на платный канал OpenRouter. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализ лица (Gemini 2.0)...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ (Тратим твои $5 на качественное зрение)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age, gender, hair and face features in 10 words. Concise."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=analysis_payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()

        await status.edit_text(f"🎨 Генерирую через FLUX (Платный канал)...")

        # 2. Генерация через FLUX (самый стабильный ID для OpenRouter)
        gen_payload = {
            "model": "black-forest-labs/flux-schnell", # Короткий ID для платных ключей
            "messages": [
                {
                    "role": "user", 
                    "content": f"Professional photorealistic 8k studio portrait of {description}, wearing a black formal suit, white shirt, solid neutral grey background, sharp focus, masterpiece."
                }
            ]
        }

        async with state.session.post(URL, json=gen_payload) as resp:
            gen_data = await resp.json()
            logger.info(f"FLUX Response: {gen_data}")
            
            if "choices" not in gen_data:
                # Если FLUX не сработал, пробуем SDXL как запасной
                logger.warning("FLUX failed, trying SDXL...")
                gen_payload["model"] = "stabilityai/sdxl"
                async with state.session.post(URL, json=gen_payload) as resp2:
                    gen_data = await resp2.json()

            if "choices" in gen_data:
                content = gen_data['choices'][0]['message']['content']
                urls = re.findall(r'https?://\S+', content)
                if not urls:
                    raise Exception("Модель не вернула ссылку на изображение.")
                image_url = urls[0].strip("()[]\"' ")
            else:
                # Последний шанс: если OpenRouter не рисует, используем Pollinations, но с МОДЕЛЬЮ FLUX
                import urllib.parse
                logger.warning("OpenRouter drawing failed, using Fallback Flux...")
                image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(description)}%20black%20suit%20grey%20background?model=flux&width=1024&height=1024&nologo=true"

        # 3. Скачивание и отправка
        async with state.session.get(image_url) as img_resp:
            if img_resp.status == 200:
                img_bytes = await img_resp.read()
                await bot.send_photo(
                    message.chat.id, 
                    BufferedInputFile(img_bytes, filename="res.jpg"),
                    caption=f"✅ Готово!\n_{description}_"
                )
                await status.delete()
            else:
                await status.edit_text(f"✅ Готово! Ссылка на результат:\n{image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
