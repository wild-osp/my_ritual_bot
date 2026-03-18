import os
import asyncio
import base64
import logging
import aiohttp
import re
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
        "Content-Type": "application/json",
        "X-Title": "Final Ritual Bot"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🤖 Бот готов. Пришлите фото.\n(Убедитесь, что создали НОВЫЙ ключ в OpenRouter)")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Обработка...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ (Gemini 2.0 - работает всегда)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe face, hair, age concisely (10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            if "choices" not in data:
                raise Exception(f"Ошибка ключа/баланса: {data.get('error', {}).get('message')}")
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 Рисую финальный портрет...")

        # 2. Попытка через самую «всеядную» модель
        # Если эта модель выдаст 400 - значит ваш аккаунт OpenRouter заблокирован для графики
        gen_payload = {
            "model": "google/gemini-2.0-pro-exp-02-15", # Эта модель УМЕЕТ генерировать описания для вложенных инструментов
            "messages": [{"role": "user", "content": f"Generate a link to a professional photorealistic portrait of {description}, black suit, grey background. Use image generation tool."}]
        }

        async with state.session.post(URL, json=gen_payload) as resp:
            gen_data = await resp.json()
            logger.info(f"Final Attempt Response: {gen_data}")
            
            if "choices" not in gen_data:
                raise Exception("Ваш ключ OpenRouter не имеет доступа к графическим моделям. Создайте новый ключ.")

            content = gen_data['choices'][0]['message']['content']
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                # Если ссылка не пришла, пробуем ПОСЛЕДНЮЮ бесплатную модель
                await status.edit_text("🔄 Пробую резервный канал...")
                last_resort = {"model": "stabilityai/sdxl", "messages": [{"role": "user", "content": f"Portrait of {description}, black suit"}]}
                async with state.session.post(URL, json=last_resort) as last_resp:
                    last_data = await last_resp.json()
                    if "choices" in last_data:
                        content = last_data['choices'][0]['message']['content']
                        urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                raise Exception("Не удалось получить ссылку на изображение. Проверьте баланс на OpenRouter.")
            
            img_url = urls[0].strip("()[]\"' ")

        # 3. Скачивание
        async with state.session.get(img_url) as img_resp:
            final_bytes = await img_resp.read()

        await bot.send_photo(message.chat.id, BufferedInputFile(final_bytes, filename="res.jpg"))
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ {str(e)}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
