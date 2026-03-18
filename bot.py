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
        "X-Title": "Ritual Photo Expert"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот запущен. Работаем через Gemini 2.0.\nПришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Обработка нейросетью...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Весь процесс в ОДНОМ запросе к Gemini 2.0
        # Мы просим её проанализировать и СРАЗУ сгенерировать ответ
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Analyze this person's face. Then, generate and provide a direct URL to a professional photorealistic 8k studio portrait of THIS person wearing a formal black suit, white shirt, on a solid neutral grey background. Output ONLY the resulting image URL."
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
            if "choices" not in data:
                raise Exception(f"API Error: {data}")
            
            answer = data['choices'][0]['message']['content']
            
            # Ищем ссылку в ответе Gemini
            import re
            urls = re.findall(r'https?://\S+', answer)
            
            if not urls:
                # Если Gemini просто описала, но не дала ссылку, пробуем запасной бесплатный сервис с другим синтаксисом
                clean_desc = answer.replace('\n', ' ')[:100]
                image_url = f"https://image.pollinations.ai/prompt/portrait%20of%20{clean_desc}%20black%20suit%20grey%20background?nologo=true"
            else:
                image_url = urls[0].strip("()[]\"' ")

        # Скачиваем результат
        async with state.session.get(image_url) as img_resp:
            if img_resp.status == 200:
                final_bytes = await img_resp.read()
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(final_bytes, filename="retouch.jpg"),
                    caption="✅ Ретушь готова"
                )
            else:
                await message.answer(f"✅ Готово! Посмотрите результат по ссылке:\n{image_url}")
        
        await status.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:150]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
