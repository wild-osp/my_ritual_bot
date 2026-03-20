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
    await message.answer("📸 Бот готов. Использую прямой канал генерации. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ 1/2 Анализ лица...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # ШАГ 1: Gemini анализирует фото (это работает 100%)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair, face features in 8 words. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content'].strip()

        await status.edit_text("🎨 2/2 Создаю файл портрета...")

        # ШАГ 2: Генерация через сверхстабильный источник (Vercel/Flux API)
        # Убираем все лишнее, оставляем суть.
        prompt = f"Professional portrait of {description}, black suit, grey background, photorealistic"
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Новый источник (быстрый и без 'fetch failed')
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={os.urandom(4).hex()}&model=flux-pro"

        # ШАГ 3: Прямое получение файла
        async with state.session.get(image_url, timeout=40) as img_resp:
            if img_resp.status == 200:
                content = await img_resp.read()
                
                # Проверка: если пришел текст вместо картинки - это ошибка
                if len(content) < 5000: 
                    raise Exception("Сервер вернул пустой файл. Попробуйте снова.")

                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(content, filename="ritual.jpg"),
                    caption=f"✅ Готово!\n_{description}_"
                )
                await status.delete()
            else:
                raise Exception(f"Сервер занят (Статус {img_resp.status})")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}. Попробуйте еще раз.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
