import os
import asyncio
import base64
import logging
import aiohttp
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
# Используем только тот эндпоинт, который у тебя работает
URL = "https://openrouter.ai/api/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Ritual Portrait Bot"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Пришлите фото, и я сделаю ретушь (костюм, серый фон).")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Шаг 1: Анализ лица через OpenRouter...")
    
    try:
        # 1. Получаем фото и кодируем в Base64
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Анализ (Gemini 2.0 Flash - работает на твоем ключе 100%)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face, hair, gender and age very accurately in 15 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=analysis_payload) as resp:
            data = await resp.json()
            if "choices" not in data:
                raise Exception(f"OpenRouter Error: {data.get('error', {}).get('message')}")
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 Шаг 2: Генерация финальной ссылки...")

        # 3. Формируем прямую ссылку на генерацию (Pollinations AI - использует FLUX/SDXL бесплатно)
        # Это спасет нас от ошибок 400/404, так как запрос идет в обход ограничений OpenRouter
        full_prompt = f"Professional photorealistic studio portrait of {description}, wearing a black formal suit, white shirt, solid neutral grey background, high detail, 8k, sharp focus, masterpiece."
        encoded_prompt = urllib.parse.quote(full_prompt)
        
        # Генерируем URL (модель flux включена по умолчанию)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed=42&model=flux"

        # 4. Скачиваем изображение по ссылке (чтобы прислать файл, а не просто текст)
        async with state.session.get(image_url) as img_resp:
            if img_resp.status != 200:
                raise Exception("Не удалось получить изображение с сервера генерации.")
            final_image_bytes = await img_resp.read()

        # 5. Отправка результата пользователю
        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_image_bytes, filename="ritual_portrait.jpg"),
            caption=f"✅ Готово!\n\n🔗 [Прямая ссылка на фото]({image_url})\n\n_Описание: {description}_",
            parse_mode="Markdown"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Произошла ошибка: {str(e)[:200]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
