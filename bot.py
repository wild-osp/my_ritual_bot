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
load_dotenv()

API_KEY = os.getenv("OPENROUTER_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальная переменная для сессии
session = None

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {API_KEY}"})
    return session

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Пришлите фото. Использую Claude 3.5 и FLUX для лучшего результата.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Подключаюсь к платным моделям...")
    http_session = await get_session()
    
    try:
        # 1. Загрузка фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_image = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Анализ через Claude 3.5 Sonnet (платная, очень точная)
        await status.edit_text("🔍 Анализирую внешность (Claude 3.5)...")
        analysis_payload = {
            "model": "anthropic/claude-3.5-sonnet",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this person's face, hair color/style, and age very accurately. Max 15 words."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
        }
        
        async with http_session.post("https://openrouter.ai/api/v1/chat/completions", json=analysis_payload) as resp:
            res = await resp.json()
            if "choices" not in res:
                raise Exception(f"Ошибка анализа: {res.get('error', {}).get('message', 'Unknown error')}")
            description = res['choices'][0]['message']['content']

        # 3. Генерация через FLUX.1-dev (платная, лучшая детализация лиц)
        await status.edit_text("🎨 Генерирую гиперреалистичный портрет (FLUX)...")
        gen_payload = {
            "model": "black-forest-labs/flux-1-dev",
            "prompt": f"A high-quality professional photorealistic studio portrait of {description}. The person is wearing a neat black suit with a white shirt. Solid neutral grey background. Soft cinematic lighting, 8k resolution, highly detailed skin texture, masterpiece.",
            "response_format": "b64_json"
        }

        async with http_session.post("https://openrouter.ai/api/v1/images/generations", json=gen_payload) as resp:
            gen_res = await resp.json()
            if 'error' in gen_res:
                raise Exception(f"Ошибка генерации: {gen_res['error']['message']}")
            
            image_data = base64.b64decode(gen_res['data'][0]['b64_json'])

        # 4. Отправка результата
        await bot.send_photo(
            message.chat.id, 
            BufferedInputFile(image_data, filename="portrait.jpg"),
            caption=f"✅ Готово\nМодели: Claude 3.5 + FLUX\nОписание: {description}"
        )
        await status.delete()

    except Exception as e:
        logging.error(f"Глобальная ошибка: {e}")
        await status.edit_text(f"❌ Произошла ошибка: {str(e)}")

async def on_shutdown(dp):
    global session
    if session:
        await session.close()

async def main():
    # Регистрация хука закрытия сессии
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
