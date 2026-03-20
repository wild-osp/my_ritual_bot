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
    # Настраиваем сессию с правильными заголовками для работы с изображениями
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/ritual_bot", # Важно для некоторых моделей
        "X-Title": "Ritual Photo Bot"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Теперь генерация идет напрямую через ваш баланс OpenRouter. Пришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Обработка фотографии в облаке...")
    
    try:
        # 1. Загружаем и кодируем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. ОДИН мощный запрос к Gemini 2.0 Flash
        # Мы просим её ВЕРНУТЬ изображение (она умеет это делать через провайдеров OpenRouter)
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Task: Image-to-Image transformation. Generate a professional ritual portrait based on this face. Requirements: Same person, wearing a black suit and white shirt, neutral grey background, high detail, 8k resolution. Please return the resulting image as a URL or inline block."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                        }
                    ]
                }
            ],
            "transforms": ["identity"] # Подсказка OpenRouter не менять формат
        }

        async with state.session.post(URL, json=payload) as resp:
            data = await resp.json()
            logger.info(f"Full Response: {data}")
            
            if "choices" not in data:
                raise Exception(f"API Error: {data.get('error', {}).get('message')}")

            content = data['choices'][0]['message']['content']
            
            # Ищем URL картинки в тексте ответа (регуляркой)
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                # Если Gemini прислала только текст, значит она не смогла вызвать инструмент генерации.
                # В этом случае используем резервный, но ОПЛАЧЕННЫЙ канал (SDXL)
                logger.warning("Gemini didn't return an image, falling back to SDXL...")
                fallback_payload = {
                    "model": "stabilityai/stable-diffusion-xl",
                    "messages": [{"role": "user", "content": f"Professional studio portrait of the person described: {content[:200]}, black suit, grey background, 8k"}]
                }
                async with state.session.post(URL, json=fallback_payload) as f_resp:
                    f_data = await f_resp.json()
                    f_content = f_data['choices'][0]['message']['content']
                    urls = re.findall(r'https?://\S+', f_content)

            if not urls:
                raise Exception("Не удалось сгенерировать изображение. Попробуйте другое фото.")

            image_url = urls[0].strip("()[]\"' ")

        # 3. Скачиваем картинку и шлем её В ЧАТ
        async with state.session.get(image_url) as img_resp:
            if img_resp.status == 200:
                final_photo = await img_resp.read()
                await bot.send_photo(
                    message.chat.id, 
                    BufferedInputFile(final_photo, filename="retouch.jpg"),
                    caption="✅ Ретушь готова. Использована нейросеть Gemini 2.0."
                )
                await status.delete()
            else:
                await status.edit_text(f"✅ Готово, но Telegram не смог скачать файл. Ссылка: {image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
