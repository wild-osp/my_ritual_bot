import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
# Используем твой оплаченный OpenRouter для всего
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🚀 **Premium Mode Active**\nПришлите фото для создания ритуального портрета.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Шаг 1: Анализ черт лица (Gemini)...")
    try:
        # 1. Анализ фото
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Detailed face description: age, hair, features. Max 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        await status.edit_text("🎨 Шаг 2: Генерация премиум-портрета (SDXL)...")

        # 2. Платная генерация через Stability AI
        # Мы запрашиваем картинку прямо в коде
        image_response = await client.images.generate(
            model="stabilityai/stable-diffusion-xl",
            prompt=f"Professional memorial studio portrait of {desc}, formal black suit, neutral grey background, high resolution, photorealistic, 8k",
            size="1024x1024",
            response_format="b64_json"
        )
        
        # 3. Декодируем и отправляем
        image_data = base64.b64decode(image_response.data[0].b64_json)
        photo_file = BufferedInputFile(image_data, filename="portrait.jpg")
        
        await bot.send_photo(message.chat.id, photo=photo_file, caption=f"✨ Готово!\nОписание: {desc}")
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"⚠️ Ошибка API: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
