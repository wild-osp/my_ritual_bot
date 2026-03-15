import os
import asyncio
import logging
import base64
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ **Ритуальная Ретушь 12.0**\nПришлите фото для обработки.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status_msg = await message.answer("🔍 Шаг 1: Анализ...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        photo_content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(photo_content.getvalue()).decode('utf-8')
        
        # 1. Анализ через Gemini
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe age, hair, and face features. No punctuation. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }]
        )
        # Очищаем описание от лишних знаков, чтобы не ломать URL
        description = analysis.choices[0].message.content.strip().replace(".", "").replace(",", "")
        logger.info(f"Clean description: {description}")
        
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация...\n({description})")

        # 2. Формируем безопасный промпт
        raw_prompt = f"Professional studio portrait of {description} wearing black suit grey background photorealistic 8k"
        safe_prompt = urllib.parse.quote(raw_prompt)

        # 3. Пытаемся через OpenRouter (SDXL)
        try:
            image_gen = await client.chat.completions.create(
                model="stabilityai/stable-diffusion-xl", 
                messages=[{"role": "user", "content": raw_prompt}]
            )
            res_url = image_gen.choices[0].message.content.strip()
            if "http" in res_url:
                final_url = "http" + res_url.split("http")[-1].split()[0].strip("()[]")
                await bot.send_photo(message.chat.id, photo=URLInputFile(final_url), caption="✨ Готово (OpenRouter)")
                await status_msg.delete()
                return
        except Exception as api_e:
            logger.warning(f"Платный канал не сработал: {api_e}")

        # 4. Резерв через Pollinations (с исправленным URL)
        fallback_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
        await bot.send_photo(message.chat.id, photo=URLInputFile(fallback_url), caption="✨ Готово (Резерв)")
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка при обработке. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
