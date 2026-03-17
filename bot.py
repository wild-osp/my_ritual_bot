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
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )

async def on_shutdown():
    if state.session:
        await state.session.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Отправьте фото. Теперь используем FLUX через корректный эндпоинт.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Анализ...")
    
    try:
        # 1. Скачиваем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Описание лица (Claude 3.5 Sonnet)
        await status.edit_text("🔍 Описываю внешность...")
        analysis_body = {
            "model": "anthropic/claude-3.5-sonnet",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face and hair very concisely (10 words)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=analysis_body) as resp:
            data = await resp.json()
            description = data['choices'][0]['message']['content']

        # 3. Генерация через FLUX (ВАЖНО: через chat/completions)
        await status.edit_text("🎨 Генерирую портрет...")
        
        flux_body = {
            "model": "black-forest-labs/flux-1-dev",
            "messages": [{
                "role": "user", 
                "content": f"Generate a professional photorealistic studio portrait of {description}, wearing a black suit, grey background. High resolution."
            }]
        }

        async with state.session.post("https://openrouter.ai/api/v1/chat/completions", json=flux_body) as resp:
            # FLUX на OpenRouter возвращает JSON со ссылкой на изображение в тексте или в вложениях
            gen_data = await resp.json()
            
            if "choices" not in gen_data:
                raise Exception(f"Ошибка OpenRouter: {gen_data}")
            
            # Извлекаем URL картинки (он обычно в контенте или в поле 'url')
            # В случае FLUX OpenRouter часто отдает URL
            content = gen_data['choices'][0]['message']['content']
            
            # Если API вернул URL (что чаще всего для FLUX), скачиваем его
            import re
            urls = re.findall(r'(https?://\S+)', content)
            if not urls:
                raise Exception("Не удалось найти ссылку на изображение в ответе AI")
            
            image_url = urls[0].replace(')', '').replace(']', '') # Очистка от Markdown

        # 4. Загрузка готовой картинки и отправка
        async with state.session.get(image_url) as img_resp:
            final_image_bytes = await img_resp.read()

        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(final_image_bytes, filename="result.jpg"),
            caption=f"✅ Готово\nОписание: {description}"
        )
        await status.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status.edit_text(f"❌ Ошибка API: {str(e)[:100]}")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
