import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

# Настройка логов, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY").strip()
STABILITY_KEY = os.getenv("STABILITY_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальная сессия
async def create_session():
    return aiohttp.ClientSession()

async def get_face_description(session, image_base64):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}"}
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the person's age, facial features, and hair in 10 words. No intro."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }]
    }
    async with session.post(url, headers=headers, json=payload) as resp:
        result = await resp.json()
        return result['choices'][0]['message']['content'].strip()

async def generate_with_img2img(session, original_bytes, description):
    url = f"https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_KEY}",
        "Accept": "application/json"
    }
    
    # Формируем данные через FormData (самый стабильный способ в aiohttp)
    data = aiohttp.FormData()
    data.add_field('text_prompts[0][text]', f"Professional studio portrait of this specific person, black formal suit, white shirt, grey background, 8k, photorealistic")
    data.add_field('text_prompts[0][weight]', '1.0')
    data.add_field('init_image', original_bytes, filename='init.png', content_type='image/png')
    data.add_field('init_image_mode', 'IMAGE_STRENGTH')
    data.add_field('image_strength', '0.40') # Баланс сходства
    data.add_field('cfg_scale', '7')
    data.add_field('samples', '1')
    data.add_field('steps', '30')

    async with session.post(url, headers=headers, data=data) as resp:
        if resp.status != 200:
            err = await resp.text()
            logger.error(f"Stability Error: {err}")
            return None
        res_json = await resp.json()
        return base64.b64decode(res_json['artifacts'][0]['base64'])

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Бот запущен! Пришлите фото (как картинку), и я сделаю ретушь с сохранением сходства лица.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализирую лицо через Gemini...")
    
    async with aiohttp.ClientSession() as session:
        try:
            file = await bot.get_file(message.photo[-1].file_id)
            photo_bytes = await bot.download_file(file.file_path)
            photo_data = photo_bytes.getvalue()
            
            # Анализ
            img_b64 = base64.b64encode(photo_data).decode('utf-8')
            desc = await get_face_description(session, img_b64)
            
            await status.edit_text("🎨 2/2 Генерация Image-to-Image (сохраняю сходство)...")
            
            # Генерация
            final_image = await generate_with_img2img(session, photo_data, desc)
            
            if final_image:
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(final_image, filename="res.png"),
                    caption=f"✅ Готово! Сходство сохранено.\nОписание: {desc}"
                )
                await status.delete()
            else:
                await status.edit_text("❌ Ошибка при создании изображения. Проверьте лимиты Stability AI.")
                
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await status.edit_text(f"❌ Произошла ошибка: {str(e)[:100]}")

# Универсальная ловушка, если команда не распознана
@dp.message()
async def any_message(message: types.Message):
    await message.answer("Я получил ваше сообщение! Чтобы начать ретушь, просто пришлите мне ФОТОГРАФИЮ.")

async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
