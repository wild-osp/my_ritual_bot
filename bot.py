import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

# Логирование в консоль
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Загрузка токенов
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
STABILITY_KEY = os.getenv("STABILITY_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- AI ФУНКЦИИ ---

async def get_description(image_b64):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}"}
    prompt = "Detailed 50-word description of this elderly person's specific facial features, wrinkles, and eyes for AI generation. No intro."
    
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]}]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            return data['choices'][0]['message']['content']

async def generate_image(description):
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    headers = {"Authorization": f"Bearer {STABILITY_KEY}", "Accept": "application/json"}
    
    payload = {
        "text_prompts": [
            {"text": f"Hyper-realistic studio photo portrait of {description}. wearing black suit, white shirt, grey background, 8k, sharp focus", "weight": 1},
            {"text": "cartoon, anime, young, youthful, blurry, painting, drawing", "weight": -1}
        ],
        "cfg_scale": 9, "height": 1024, "width": 1024, "samples": 1, "steps": 40,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200: return None
            data = await resp.json()
            return base64.b64decode(data['artifacts'][0]['base64'])

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def start(message: types.Message):
    logger.info("Команда /start получена")
    await message.answer("✅ Бот запущен! Пришлите фото для ритуальной ретуши.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    msg = await message.answer("⏳ Начинаю работу...")
    try:
        # Качаем файл
        file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(file.file_path)
        img_b64 = base64.b64encode(photo_bytes.getvalue()).decode('utf-8')

        await msg.edit_text("⏳ 1/2 Анализ лица...")
        desc = await get_description(img_b64)

        await msg.edit_text("⏳ 2/2 Генерация портрета...")
        final_img = await generate_image(desc)

        if final_img:
            await bot.send_photo(message.chat.id, BufferedInputFile(final_img, filename="res.png"), caption="Готово!")
            await msg.delete()
        else:
            await msg.edit_text("❌ Ошибка генерации (проверьте ключи).")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await msg.edit_text(f"❌ Произошла ошибка: {str(e)}")

# Ловушка для любого текста
@dp.message()
async def echo(message: types.Message):
    logger.info(f"Получен текст: {message.text}")
    await message.answer("Я вижу ваш текст, но мне нужно ФОТО для работы.")

# --- ЗАПУСК ---

async def main():
    logger.info("Запуск polling...")
    # Удаляем вебхуки перед запуском, чтобы не было конфликтов
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
