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

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY").strip()
STABILITY_KEY = os.getenv("STABILITY_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ФУНКЦИИ РАБОТЫ С AI ---

async def get_detailed_face_description(image_base64):
    """Gemini 2.0 анализирует черты лица для сверхточной текстовой генерации"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}"}
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": "Task: Create a highly detailed, 50-word text prompt describing this specific person's face for an AI image generator. Focus ONLY on their age, face geometry, deep wrinkles, eye shape, nose shape, and mouth. Do not include introductory or concluding remarks. The goal is maximum resemblance."
                },
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            result = await resp.json()
            if 'choices' not in result:
                logger.error(f"OpenRouter Error: {result}")
                return "highly detailed photorealistic portrait of an extremely elderly man"
            return result['choices'][0]['message']['content'].strip()

async def generate_photorealistic_portrait(description):
    """Генерация ЧЕРЕЗ TEXT-TO-IMAGE с максимальным фотореализмом на основе описания Gemini"""
    # Эндпоинт для TEXT-TO-IMAGE
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_KEY}",
        "Accept": "application/json"
    }
    
    # Текст промпта (мы объединяем описание лица с костюмом и фоном)
    # prompt = (
    #     f"Highly detailed professional studio photographic portrait of {description}. "
    #     f"They are wearing a black formal suit and white shirt, solid neutral grey background, cinematic lighting, 8k resolution, photorealistic masterpiece, sharp focus, Leica M lens style."
    # )
    
    payload = {
        "text_prompts": [
            {
                "text": f"highly detailed photographic masterpiece portrait of {description}. wearing black suit and white shirt, solid grey background, cinematic lighting, photorealistic, 8k", 
                "weight": 1
            },
            {
                "text": "painting, drawing, illustration, cartoon, caricature, youthful, young, fake, blurry",
                "weight": -1 # Негативный промпт, чтобы убрать "омоложение"
            }
        ],
        "cfg_scale": 9, # Немного выше, чтобы он жестче следовал промпту
        "height": 1024,
        "width": 1024,
        "samples": 1,
        "steps": 40, # Больше шагов для качества
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                logger.error(f"Stability Error: {err_text}")
                return None
            res_json = await resp.json()
            return base64.b64decode(res_json['artifacts'][0]['base64'])

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализирую лицо через Gemini...")
    
    try:
        # Качаем фото
        file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(file.file_path)
        img_b64 = base64.b64encode(photo_bytes.getvalue()).decode('utf-8')

        # 1. Сверхподробное описание лица
        detailed_desc = await get_detailed_face_description(img_b64)
        
        await status.edit_text(f"🎨 2/2 Создаю портрет (SDXL Text-to-Image)... Описание: {detailed_desc[:100]}...")
        
        # 2. Генерация изображения на основе текста
        final_image = await generate_photorealistic_portrait(detailed_desc)
        
        if final_image:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(final_image, filename="ritual.png"),
                caption=f"✅ Готово! Ретушь на основе подробного описания лица."
            )
            await status.delete()
        else:
            await status.edit_text("❌ Ошибка при создании изображения. Проверьте кредиты на Stability AI.")
            
    except Exception as e:
        logger.error(f"Ошибка обработчика: {e}")
        await status.edit_text(f"❌ Системная ошибка. Попробуйте еще раз.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
