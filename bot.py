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

API_KEY = os.getenv("OPENROUTER_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AppState:
    session: aiohttp.ClientSession = None

state = AppState()

async def on_startup():
    state.session = aiohttp.ClientSession(
        headers={
            "Authorization": f"Bearer {API_KEY.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/my_bot",
        }
    )

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Бот готов. Пришлите фото. Использую FLUX Schnell (самая быстрая и стабильная модель).")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Работаю...")
    
    try:
        # 1. Фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Анализ
        await status.edit_text("🔍 Анализ внешности...")
        analysis_body = {
            "model": "google/gemini-2.0-flash-001", # Заменил на Gemini, она дешевле и быстрее для анализа
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face, hair, and age. Max 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=analysis_body) as resp:
            data = await resp.json()
            if 'choices' not in data:
                raise Exception(f"Gemini Error: {data}")
            description = data['choices'][0]['message']['content']

        # 3. Генерация (FLUX Schnell - самая стабильная версия на OpenRouter)
        await status.edit_text("🎨 Генерирую портрет (FLUX)...")
        
        flux_body = {
            "model": "black-forest-labs/flux-1-schnell", # Эта модель ID точно работает
            "messages": [{
                "role": "user", 
                "content": f"A professional photorealistic studio portrait of {description}, wearing a black formal suit, solid neutral grey background, high detail, 8k."
            }]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=flux_body) as resp:
            gen_data = await resp.json()
            logger.info(f"OpenRouter Response: {gen_data}") # Логируем для отладки
            
            if "choices" not in gen_data:
                error_msg = gen_data.get('error', {}).get('message', 'Unknown Error')
                raise Exception(f"Генерация не удалась: {error_msg}")
            
            content = gen_data['choices'][0]['message']['content']
            
            # Поиск URL в ответе
            urls = re.findall(r'(https?://\S+)', content)
            if not urls:
                # Иногда ссылка приходит без протокола или в специальном поле
                raise Exception("AI не вернул ссылку на изображение. Попробуйте еще раз.")
            
            image_url = urls[0].split(')')[0].split(']')[0].strip()

        # 4. Скачивание и отправка
        async with state.session.get(image_url) as img_resp:
            if img_resp.status != 200:
                raise Exception("Не удалось скачать готовое изображение по ссылке.")
            final_image_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_image_bytes, filename="result.jpg"),
            caption=f"✅ Готово!\n\n_{description}_",
            parse_mode="Markdown"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Глобальная ошибка: {e}")
        await status.edit_text(f"❌ Ошибка: {str(e)}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
