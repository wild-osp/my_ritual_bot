import os
import asyncio
import base64
import logging
import io
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv
from PIL import Image # Нужно для изменения размера фото

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY").strip()
STABILITY_KEY = os.getenv("STABILITY_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ RESIZE ---

def resize_image_to_sdxl(image_bytes):
    """Принудительно меняет размер фото до 1024x1024 для совместимости с SDXL"""
    img = Image.open(io.BytesIO(image_bytes))
    # Переводим в RGB (на случай если прислали PNG с прозрачностью)
    img = img.convert("RGB")
    # Ресайз до стандарта SDXL
    img = img.resize((1024, 1024), Image.LANCZOS)
    
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()

# --- ФУНКЦИИ РАБОТЫ С AI ---

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
        if 'choices' not in result: return "elderly person"
        return result['choices'][0]['message']['content'].strip()

async def generate_with_img2img(session, resized_bytes, description):
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_KEY}",
        "Accept": "application/json"
    }
    
    data = aiohttp.FormData()
    data.add_field('text_prompts[0][text]', f"High-quality professional studio portrait of this specific person, wearing a black formal suit, white shirt, solid neutral grey background, sharp focus, 8k")
    data.add_field('text_prompts[0][weight]', '1.0')
    data.add_field('init_image', resized_bytes, filename='init.png', content_type='image/png')
    data.add_field('init_image_mode', 'IMAGE_STRENGTH')
    
    # Сходство лица: чем выше, тем больше похоже (0.48 - очень высокая точность)
    data.add_field('image_strength', '0.48') 
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

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("📸 Бот готов! Теперь я сам меняю размер фото для идеального сходства. Присылайте снимок.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/3 Подготовка изображения...")
    
    async with aiohttp.ClientSession() as session:
        try:
            file = await bot.get_file(message.photo[-1].file_id)
            photo_bytes = await bot.download_file(file.file_path)
            raw_data = photo_bytes.getvalue()
            
            # НОВОЕ: Ресайз перед отправкой
            resized_data = resize_image_to_sdxl(raw_data)
            
            await status.edit_text("⏳ 2/3 Анализ лица...")
            img_b64 = base64.b64encode(resized_data).decode('utf-8')
            desc = await get_face_description(session, img_b64)
            
            await status.edit_text("🎨 3/3 Генерация портрета (Img2Img)...")
            final_image = await generate_with_img2img(session, resized_data, desc)
            
            if final_image:
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(final_image, filename="result.png"),
                    caption=f"✅ Готово. Сходство сохранено."
                )
                await status.delete()
            else:
                await status.edit_text("❌ Ошибка Stability. Проверьте баланс.")
                
        except Exception as e:
            logger.error(f"Error: {e}")
            await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
