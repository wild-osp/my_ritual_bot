import os
import asyncio
import base64
import logging
import aiohttp
import replicate
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Загрузка ВСЕХ ключей
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN").strip()
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY").strip()
STABILITY_KEY = os.getenv("STABILITY_KEY").strip()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN").strip()

# Устанавливаем токен для replicate
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- AI ФУНКЦИИ ---

async def get_face_description(image_b64):
    """Анализ только кожи и возраста через Gemini"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}"}
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Describe age, skin texture, and eye wrinkles very briefly (5 words)."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]}]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            return data['choices'][0]['message']['content'].strip()

async def generate_stability_base(desc):
    """Генерация ШАБЛОНА портрета (костюм+фон)"""
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    headers = {"Authorization": f"Bearer {STABILITY_KEY}", "Accept": "application/json"}
    payload = {
        "text_prompts": [
            {"text": f"Highly detailed realistic studio portrait of an {desc} man, wearing a black formal suit and white shirt, solid grey background, cinematic lighting, 8k", "weight": 1},
            {"text": "painting, drawing, illustration, cartoon, fake, blurry", "weight": -1}
        ],
        "cfg_scale": 7, "height": 1024, "width": 1024, "samples": 1, "steps": 30,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200: return None
            data = await resp.json()
            return base64.b64decode(data['artifacts'][0]['base64'])

async def swap_face_replicate(target_img_bytes, source_img_b64):
    """ФИНАЛЬНЫЙ ШАГ: Точный Face Swap через InsightFace (Replicate)"""
    
    # Модель insightface на replicate. Это самый стабильный способ.
    model = "vinesmsuic/swapper:0.1" 
    
    # Replicate API работает через ссылки или base64 данные. Мы отправим base64.
    source_url = f"data:image/jpeg;base64,{source_img_b64}"
    
    # Для target нам нужны base64 данные. Конвертируем байты шаблона.
    target_b64 = base64.b64encode(target_img_bytes).decode('utf-8')
    target_url = f"data:image/jpeg;base64,{target_b64}"

    try:
        # Мы запускаем Replicate через их библиотеку. Это синхронный вызов,
        # поэтому мы "оборачиваем" его в run_in_executor, чтобы не блокировать бота.
        output_url = await asyncio.get_running_loop().run_in_executor(
            None, 
            lambda: replicate.run(
                "vinesmsuic/swapper:ae8399583b4b537c73b06e8b0b533a8a3064402377b069d5a7d745c136324d26",
                input={"target": target_url, "source": source_url}
            )
        )
        
        # Модель возвращает ссылку на итоговую картинку. Скачиваем её байты.
        async with aiohttp.ClientSession() as session:
            async with session.get(output_url) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logger.error(f"Error downloading replicate result: {resp.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Replicate FaceSwap error: {e}")
        return None

# --- ХЕНДЛЕРЫ СООБЩЕНИЙ ---

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    msg = await message.answer("⏳ 1/3 Анализ лица...")
    try:
        # Качаем файл
        file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(file.file_path)
        img_b64 = base64.b64encode(photo_bytes.getvalue()).decode('utf-8')

        # 1. Описание кожи
        desc = await get_face_description(img_b64)

        # 2. Генерация шаблона
        await msg.edit_text("⏳ 2/3 Создаю шаблон портрета (костюм)...")
        stability_template = await generate_stability_base(desc)

        if not stability_template:
            await msg.edit_text("❌ Ошибка Stability AI. Проверьте кредиты.")
            return

        # 3. ТОЧНЫЙ Face Swap
        await msg.edit_text("⏳ 3/3 ТОЧНЫЙ перенос лица (Face Swap)...")
        final_img = await swap_face_replicate(stability_template, img_b64)

        if final_img:
            await bot.send_photo(
                message.chat.id, 
                BufferedInputFile(final_img, filename="nanobanano.png"), 
                caption=f"✅ Готово! Использован InsightFace Swap для максимального сходства.\nМодель: vinesmsuic/swapper"
            )
            await msg.delete()
        else:
            await msg.edit_text("❌ Ошибка InsightFace Face Swap (проверьте Replicate API).")
            
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await msg.edit_text(f"❌ Системная ошибка. Попробуйте еще раз.")

async def main():
    logger.info("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
