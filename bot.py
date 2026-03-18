import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
# Используем стабильный эндпоинт чата
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
    await message.answer("📸 Бот готов. Пришлите фото для автоматической ретуши.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Обработка через Gemini 2.0...")
    
    try:
        # 1. Подготовка фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. ОДИН ЗАПРОС к Gemini 2.0 Flash
        # Эта модель мультимодальная - она сама видит и сама решит, как описать
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "This is a photo for a professional ritual portrait. Describe the person's face, hair and appearance in detail (age, gender, features). Output ONLY the description."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                    ]
                }
            ]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            if "choices" not in data:
                raise Exception(f"OpenRouter Error: {data}")
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 Создаю финальный портрет...")

        # 3. ГЕНЕРАЦИЯ (Используем OpenAI DALL-E 3 через OpenRouter)
        # Если SDXL и FLUX не работают, DALL-E 3 - это 'тяжелая артиллерия', которая работает всегда.
        gen_payload = {
            "model": "openai/dall-e-3", 
            "messages": [{"role": "user", "content": f"A highly realistic, professional studio funeral portrait of {description}. The person is wearing a black suit, white shirt. Neutral grey background. Sharp focus, high quality photography, 8k resolution."}]
        }

        async with state.session.post(URL, json=gen_payload) as resp:
            gen_data = await resp.json()
            logger.info(f"DALL-E Response: {gen_data}")
            
            if "choices" not in gen_data:
                # Если DALL-E 3 тоже 'не валиден' (что вряд ли), пробуем последнюю надежду - Kandinsky
                raise Exception(f"Генерация не удалась: {gen_data.get('error', {}).get('message', 'No data')}")
            
            # Извлекаем ссылку
            import re
            content = gen_data['choices'][0]['message']['content']
            urls = re.findall(r'https?://\S+', content)
            if not urls:
                raise Exception("Ссылка на фото не найдена в ответе.")
            
            final_url = urls[0].strip("()[]\"' ")

        # 4. Скачивание и отправка
        async with state.session.get(final_url) as img_resp:
            final_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_bytes, filename="result.jpg"),
            caption="✅ Ретушь завершена успешно."
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Системная ошибка: {str(e)[:150]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
