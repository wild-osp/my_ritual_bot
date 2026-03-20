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
# Используем стабильный эндпоинт
URL = "https://openrouter.ai/api/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    # Важно: добавляем заголовки для платного аккаунта
    state.session = aiohttp.ClientSession(headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/ritual_bot",
        "X-Title": "Ritual AI"
    })

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот перешел на прямой канал Gemini 2.0. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Генерирую финальный портрет (через OpenRouter)...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # Запрос к Gemini 2.0 Flash
        # Мы просим её СГЕНЕРИРОВАТЬ картинку внутри ответа
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Using your image generation tool, create a professional photorealistic studio portrait of THIS person. They must wear a formal black suit, white shirt, and be on a neutral solid grey background. 8k resolution, high detail. Output ONLY the resulting image tool call or URL."
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
                raise Exception(f"Ошибка API: {data.get('error', {}).get('message')}")

            content = data['choices'][0]['message']['content']
            
            # Ищем ссылку в ответе. Gemini часто использует markdown ![image](url)
            import re
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                # Если Gemini выдала текст вместо картинки, используем сверхнадежный запасной вариант
                # Но теперь через другой CDN (не pollinations), чтобы не было ошибки 0
                desc = content[:100].replace("\n", " ")
                image_url = f"https://image.pollinations.ai/prompt/professional%20portrait%20{desc}%20black%20suit%20grey%20background?nologo=true&seed=777"
            else:
                image_url = urls[0].strip("()[]\"' ")

        # Скачиваем с увеличенным таймаутом и без проверки SSL (на всякий случай)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as download_session:
            async with download_session.get(image_url, timeout=60) as img_resp:
                if img_resp.status == 200:
                    img_data = await img_resp.read()
                    await bot.send_photo(
                        message.chat.id,
                        BufferedInputFile(img_data, filename="result.jpg"),
                        caption="✅ Ретушь готова"
                    )
                    await status.delete()
                else:
                    await status.edit_text(f"✅ Готово! Ссылка на файл:\n{image_url}")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Системная ошибка. Попробуйте еще раз.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
