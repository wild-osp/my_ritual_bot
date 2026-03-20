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

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    state.session = aiohttp.ClientSession()

async def on_shutdown():
    if state.session:
        await state.session.close()

async def get_face_description(image_base64):
    """Gemini 2.0 (OpenRouter) анализирует черты лица"""
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
                {"type": "text", "text": "Describe the person's age, facial features, and hair in 10 words. No intro."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }]
    }
    async with state.session.post(url, headers=headers, json=payload) as resp:
        result = await resp.json()
        return result['choices'][0]['message']['content'].strip()

async def generate_with_img2img(original_bytes, description):
    """Генерация ЧЕРЕЗ IMAGE-TO-IMAGE для сохранения схожести"""
    # Используем эндпоинт ИМЕННО ДЛЯ IMAGE-TO-IMAGE
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_KEY}",
        "Accept": "application/json"
    }
    
    # Текст, описывающий ИЗМЕНЕНИЯ, которые мы хотим
    prompt = f"Professional studio portrait of this specific person wearing a high-quality black formal suit and white shirt, solid neutral grey background, cinematic lighting, 8k resolution, photorealistic, sharp focus"

    # Параметры для Image-to-Image
    # image_strength=0.35 — это КЛЮЧЕВОЙ параметр. Чем он выше (до 1), тем больше картинка похожа на оригинал.
    # Значение 0.35-0.4 — хороший баланс между сохранением лица и изменением костюма.
    data = {
        "text_prompts[0][text]": prompt,
        "text_prompts[0][weight]": 1,
        "cfg_scale": 7,
        "samples": 1,
        "steps": 30,
        "init_image_mode": "IMAGE_STRENGTH",
        "image_strength": 0.38, # КЛЮЧ: Настройка "силы" оригинала (0.0 - 1.0)
    }

    # Для Image-to-Image мы отправляем файл через multipart/form-data
    with aiohttp.MultipartWriter('form-data') as mpwriter:
        for key, value in data.items():
            mpwriter.append_part(value, content_type='text/plain', headers={'Content-Disposition': f'form-data; name="{key}"'})
        
        mpwriter.append_part(original_bytes, content_type='image/png', headers={'Content-Disposition': f'form-data; name="init_image"; filename="origin.png"'})

        # Настраиваем запрос
        url_mp = f"{url}?{mpwriter.headers['Content-Type'].split(';', 1)[1].strip()}"
        async with state.session.post(url, headers=headers, data=mpwriter) as resp:
            if resp.status != 200:
                error_data = await resp.text()
                logger.error(f"Stability AI Error: {error_data}")
                return None
            
            data = await resp.json()
            # Достаем base64 результат
            image_base64 = data['artifacts'][0]['base64']
            return base64.b64decode(image_base64)

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализирую внешность...")
    
    try:
        # Качаем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        # Конвертируем в base64 только для Gemini
        img_b64 = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ лица
        description = await get_face_description(img_b64)
        await status.edit_text("🎨 Применяю Image-to-Image ретушь (Сохраняю лицо)...")

        # 2. Генерация через Image-to-Image
        final_image_bytes = await generate_with_img2img(file_bytes.getvalue(), description)

        if final_image_bytes:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(final_image_bytes, filename="ritual.png"),
                caption="✅ Ретушь готова. Использована технология Image-to-Image (сохранение схожести)."
            )
            await status.delete()
        else:
            await status.edit_text("❌ Ошибка генерации. Проверьте кредиты на Stability AI.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Системная ошибка. Попробуйте снова.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
