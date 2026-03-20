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
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/ritual_retouch_bot", # Нужно для OpenRouter
        "X-Title": "Ritual AI"
    }
    state.session = aiohttp.ClientSession(headers=headers)

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Используем платный канал Stability AI.\nПришлите фото.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("🔍 Анализ лица...")
    
    try:
        # 1. Получаем описание лица (Gemini 2.0 работает отлично, судя по логам)
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        analysis_payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe age, gender, hair and face features in 10 words. No intro."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post(URL, json=analysis_payload) as resp:
            res = await resp.json()
            description = res['choices'][0]['message']['content'].strip()

        await status.edit_text(f"🎨 Генерирую ритуальный портрет...\n(База: {description})")

        # 2. ГЕНЕРАЦИЯ КАРТИНКИ через Stability AI (Платная, стабильная)
        # Мы используем SDXL, так как она лучше всего понимает формат 'черный костюм'
        gen_payload = {
            "model": "stabilityai/stable-diffusion-xl",
            "messages": [
                {
                    "role": "user",
                    "content": f"Professional photorealistic studio portrait of {description}, wearing formal black suit and white shirt, solid neutral dark grey background, cinematic lighting, 8k, sharp focus."
                }
            ]
        }

        async with state.session.post(URL, json=gen_payload) as resp:
            gen_res = await resp.json()
            logger.info(f"Gen Response: {gen_res}")
            
            if "choices" not in gen_res:
                raise Exception(f"Ошибка генерации: {gen_res.get('error', {}).get('message')}")

            content = gen_res['choices'][0]['message']['content']
            
            # Ищем ссылку в ответе (OpenRouter часто возвращает Markdown ссылку)
            urls = re.findall(r'https?://\S+', content)
            
            if not urls:
                raise Exception("Модель не вернула ссылку на изображение. Попробуйте еще раз.")

            image_url = urls[0].strip("()[]\"' ")

        # 3. Скачиваем и отправляем
        async with state.session.get(image_url) as img_resp:
            if img_resp.status == 200:
                final_bytes = await img_resp.read()
                await bot.send_photo(
                    message.chat.id,
                    BufferedInputFile(final_bytes, filename="result.jpg"),
                    caption="✅ Ретушь готова (Stability AI)"
                )
                await status.delete()
            else:
                await status.edit_text(f"✅ Готово! Ссылка на результат:\n{image_url}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)[:150]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
