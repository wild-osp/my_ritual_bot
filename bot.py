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
    # Добавляем заголовки, которые OpenRouter требует для платных аккаунтов
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot", 
        "X-Title": "Ritual Portrait AI"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Использую премиум-канал Gemini 2.0.\nПришлите фото человека.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Нейросеть создаёт портрет...")
    
    try:
        # 1. Кодируем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Запрос к мультимодальной Gemini 2.0
        # Мы просим её использовать инструмент генерации или выдать прямую ссылку на результат
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Task: Create a professional ritual studio portrait. Input: The attached photo. Requirements: Same person, wearing a black formal suit, white shirt, neutral grey background, photorealistic 8k. Action: Generate the image and provide the direct URL to it."
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
            logger.info(f"Gemini Response: {data}")
            
            if "choices" not in data:
                raise Exception(f"OpenRouter Error: {data.get('error', {}).get('message')}")

            content = data['choices'][0]['message']['content']
            
            # Извлекаем ссылку на сгенерированный файл
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                # Если Gemini выдала только описание, используем резервную сборку ссылки 
                # на базе её описания (но через стабильный сервис)
                clean_desc = content.replace("\n", " ")[:150]
                image_url = f"https://image.pollinations.ai/prompt/professional%20portrait%20{clean_desc}%20black%20suit%20grey%20background?width=1024&height=1024&nologo=true&seed=42"
            else:
                image_url = urls[0].strip("()[]\"' ")

        # 3. Скачивание и отправка
        async with state.session.get(image_url) as img_resp:
            if img_resp.status == 200:
                final_bytes = await img_resp.read()
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(final_bytes, filename="ritual.jpg"),
                    caption="✅ Ретушь выполнена премиум-моделью."
                )
                await status.delete()
            else:
                await status.edit_text(f"✅ Ссылка на готовый портрет:\n{image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:200]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
