import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Загрузка ключей
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY").strip()
STABILITY_KEY = os.getenv("STABILITY_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Храним сессию для запросов
class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    state.session = aiohttp.ClientSession()

async def on_shutdown():
    if state.session:
        await state.session.close()

async def get_face_description(image_base64):
    """Шаг 1: Анализ лица через Gemini 2.0 (OpenRouter)"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the person's age, facial features, and hair in 10-15 words. No intro."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }]
    }
    async with state.session.post(url, headers=headers, json=payload) as resp:
        result = await resp.json()
        return result['choices'][0]['message']['content'].strip()

async def generate_ritual_portrait(description):
    """Шаг 2: Генерация картинки через Stability AI API (SDXL)"""
    # Используем проверенную модель SDXL 1.0
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_KEY}",
        "Accept": "application/json" # Получаем JSON с base64 картинкой
    }
    prompt = f"Professional photorealistic studio portrait of {description}, wearing a black formal suit, white shirt, solid dark grey background, cinematic lighting, 8k resolution, highly detailed."
    
    payload = {
        "text_prompts": [{"text": prompt, "weight": 1}],
        "cfg_scale": 7,
        "height": 1024,
        "width": 1024,
        "samples": 1,
        "steps": 30,
    }

    async with state.session.post(url, headers=headers, json=payload) as resp:
        if resp.status != 200:
            error_data = await resp.text()
            logger.error(f"Stability AI Error: {error_data}")
            return None
        
        data = await resp.json()
        # Достаем картинку из ответа (она там в base64)
        image_base64 = data['artifacts'][0]['base64']
        return base64.b64decode(image_base64)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот настроен! Пришлите фото, и я сделаю профессиональный портрет в черном костюме.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализирую черты лица...")
    
    try:
        # Получаем фото от пользователя
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        img_b64 = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Текстовое описание
        description = await get_face_description(img_b64)
        await status.edit_text(f"🎨 2/2 Создаю портрет: {description}...")

        # 2. Генерация изображения
        final_image_bytes = await generate_ritual_portrait(description)

        if final_image_bytes:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(final_image_bytes, filename="result.png"),
                caption="✅ Ретушь готова. Использованы Gemini 2.0 и SDXL."
            )
            await status.delete()
        else:
            await status.edit_text("❌ Ошибка при создании картинки. Проверьте баланс на Stability AI.")

    except Exception as e:
        logger.error(f"Общая ошибка: {e}")
        await status.edit_text(f"❌ Произошла ошибка. Попробуйте еще раз.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
