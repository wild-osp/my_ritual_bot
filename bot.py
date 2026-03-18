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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/aiogram/aiogram", # Обязательно для некоторых моделей
        "X-Title": "Diagnostic Ritual Bot"
    }
    state.session = aiohttp.ClientSession(headers=headers)
    
    # ПРОВЕРКА БАЛАНСА ПРИ СТАРТЕ
    async with state.session.get("https://openrouter.ai/api/v1/auth/key") as resp:
        key_data = await resp.json()
        logger.info(f"--- DIAGNOSTIC DATA ---")
        logger.info(f"Key Info: {key_data}")
        # Если здесь баланс 0 или ошибка - ключ настроен неверно

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    # Узнаем баланс для пользователя
    async with state.session.get("https://openrouter.ai/api/v1/auth/key") as resp:
        data = await resp.json()
        limit = data.get('limit', 'N/A')
        usage = data.get('usage', 'N/A')
        # В OpenRouter баланс = limit - usage
        await message.answer(f"🛠 Диагностика:\nКлюч активен: {not data.get('is_expired', True)}\nЛимит: {limit}$\nИспользовано: {usage}$")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализ и проверка лимитов...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 1. Анализ (Gemini)
        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Short face description (10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=analysis_payload) as resp:
            data = await resp.json()
            if "choices" not in data:
                raise Exception(f"Ошибка доступа: {data}")
            description = data['choices'][0]['message']['content']

        await status.edit_text(f"🔍 Описание: {description}\n🎨 Пробую генерацию...")

        # 2. ГЕНЕРАЦИЯ С ПОЛНЫМ ЛОГОМ
        # Пробуем по очереди разные форматы ID
        test_models = ["black-forest-labs/flux-1-schnell", "stabilityai/stable-diffusion-xl", "openai/dall-e-3"]
        
        final_url = None
        for model in test_models:
            logger.info(f"Trying model ID: {model}")
            gen_payload = {
                "model": model,
                "messages": [{"role": "user", "content": f"Studio portrait of {description}, black suit, grey background"}]
            }
            
            async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=gen_payload) as resp:
                raw_response = await resp.json()
                logger.info(f"Response for {model}: {raw_response}")
                
                if "choices" in raw_response:
                    content = raw_response['choices'][0]['message']['content']
                    urls = re.findall(r'https?://\S+', content)
                    if urls:
                        final_url = urls[0].strip("()[]\"' ")
                        break
        
        if not final_url:
            raise Exception("Ни одна модель не приняла запрос. Проверь логи консоли!")

        async with state.session.get(final_url) as img_resp:
            image_data = await img_resp.read()

        await bot.send_photo(message.chat.id, BufferedInputFile(image_data, filename="res.jpg"))
        await status.delete()

    except Exception as e:
        logger.error(f"FATAL ERROR: {e}")
        await status.edit_text(f"❌ Ошибка:\n{str(e)}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
