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

# Ключи
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY").strip()
STABILITY_KEY = os.getenv("STABILITY_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ФУНКЦИИ РАБОТЫ С AI ---

async def get_face_description(session, image_base64):
    """Шаг 1: Анализ лица через Gemini 2.0 (OpenRouter)"""
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
        if 'choices' not in result:
            logger.error(f"OpenRouter Error: {result}")
            return "elderly person"
        return result['choices'][0]['message']['content'].strip()

async def generate_with_img2img(session, original_bytes, description):
    """Шаг 2: Генерация Image-to-Image через Stability AI"""
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_KEY}",
        "Accept": "application/json"
    }
    
    data = aiohttp.FormData()
    data.add_field('text_prompts[0][text]', f"Professional studio portrait of this specific person, wearing a black formal suit, white shirt, solid neutral grey background, 8k resolution, photorealistic, sharp focus")
    data.add_field('text_prompts[0][weight]', '1.0')
    data.add_field('init_image', original_bytes, filename='init.png', content_type='image/png')
    data.add_field('init_image_mode', 'IMAGE_STRENGTH')
    
    # Сила сохранения оригинала (0.45 — для максимального сходства)
    data.add_field('image_strength', '0.45') 
    
    # Принудительные размеры для SDXL
    data.add_field('width', '1024')
    data.add_field('height', '1024')
    
    data.add_field('cfg_scale', '8')
    data.add_field('samples', '1')
    data.add_field('steps', '30')

    async with session.post(url, headers=headers, data=data) as resp:
        if resp.status != 200:
            err_text = await resp.text()
            logger.error(f"Stability Error: {err_text}")
            return None
        res_json = await resp.json()
        return base64.b64decode(res_json['artifacts'][0]['base64'])

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("📸 Бот готов! Пришлите фото, и я сделаю портрет в костюме с сохранением черт лица.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализирую лицо...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # ИСПРАВЛЕНИЕ: используем file_id и скачиваем корректно
            file_id = message.photo[-1].file_id
            file = await bot.get_file(file_id)
            
            # ИСПРАВЛЕНИЕ: здесь был атрибут .path, теперь .file_path
            photo_bytes = await bot.download_file(file.file_path)
            photo_data = photo_bytes.getvalue()
            
            img_b64 = base64.b64encode(photo_data).decode('utf-8')
            desc = await get_face_description(session, img_b64)
            
            await status.edit_text(f"🎨 2/2 Сохраняю сходство и меняю костюм...")
            
            final_image = await generate_with_img2img(session, photo_data, desc)
            
            if final_image:
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(final_image, filename="result.png"),
                    caption=f"✅ Готово.\nОписание: {desc}"
                )
                await status.delete()
            else:
                await status.edit_text("❌ Ошибка генерации. Проверьте кредиты на Stability AI.")
                
        except Exception as e:
            logger.error(f"Ошибка обработчика: {e}")
            await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

@dp.message()
async def any_msg(message: types.Message):
    await message.answer("Просто пришлите мне ФОТОГРАФИЮ человека.")

# --- ЗАПУСК ---

async def main():
    logger.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
