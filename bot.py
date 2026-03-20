import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Твои ключи из .env
API_KEY = os.getenv("OPENROUTER_KEY").strip()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = "https://openrouter.ai/api/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    # Настраиваем сессию с заголовками для платного аккаунта
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/my_retouch_task_bot",
        "X-Title": "Ritual Debug Bot"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🧪 Режим отладки: присылай фото, а я попробую его описать через Gemini 2.0.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Связываюсь с OpenRouter (Gemini 2.0)...")
    
    try:
        # 1. Подготовка фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Запрос к текстовой модели
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Analyze this person. Create a detailed 50-word prompt for an AI image generator to place this exact person in a black formal suit on a grey background. Be very specific about facial features."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                        }
                    ]
                }
            ]
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            
            if "choices" in data:
                ai_text = data['choices'][0]['message']['content']
                await status.edit_text(f"✅ **Связь установлена!**\n\n**Gemini составила такой промпт:**\n\n{ai_text}", parse_mode="Markdown")
            else:
                error_msg = data.get('error', {}).get('message', 'Неизвестная ошибка')
                await status.edit_text(f"❌ Ошибка OpenRouter: {error_msg}")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Системная ошибка: {str(e)}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
