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
        "X-Title": "Ritual Photo Bot Final"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Отправьте фото лица.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализирую...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ через базовую Gemini (она точно работает)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe face, hair, and age in 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content']

        await status.edit_text("🎨 Генерирую через резервный канал...")

        # 2. ПРОБУЕМ КАНДИНСКИЙ (Часто работает, когда западные модели блокируют)
        # Если не сработает, попробуем еще одну модель прямо в этом блоке
        gen_models = [
            "propmthelp/kandinsky-3", 
            "bytedance/sdxl-lightning-4step",
            "stabilityai/sdxl"
        ]
        
        final_bytes = None
        
        for model_id in gen_models:
            logger.info(f"Trying model: {model_id}")
            gen_payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"Professional ritual studio portrait of {description}, black suit, grey background, 8k"}]
            }
            
            async with state.session.post(URL, json=gen_payload) as resp:
                gen_data = await resp.json()
                if "choices" in gen_data:
                    content = gen_data['choices'][0]['message']['content']
                    urls = re.findall(r'https?://\S+', content)
                    if urls:
                        img_url = urls[0].strip("()[]\"' ")
                        async with state.session.get(img_url) as img_resp:
                            final_bytes = await img_resp.read()
                            break # Успех!
                else:
                    logger.warning(f"Model {model_id} failed: {gen_data.get('error')}")

        if not final_bytes:
            raise Exception("Все доступные графические модели отклонили запрос. Проверьте настройки лимитов в OpenRouter.")

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_bytes, filename="result.jpg"),
            caption=f"✅ Готово\n{description}"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Ошибка API: {str(e)}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
