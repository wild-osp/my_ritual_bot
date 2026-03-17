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
# Твой оплаченный клиент
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🚀 Платный режим активирован. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Анализ лица...")
    try:
        # 1. Анализ через Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Age, hair, glasses. 5 words max."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        await status.edit_text("🎨 Генерирую премиум-портрет (SDXL)...")

        # 2. Платная генерация через Stability AI (SDXL)
        # Мы используем API OpenRouter для создания изображения
        # Примечание: Мы просим модель вернуть изображение в формате b64_json
        image_response = await client.images.generate(
            model="stabilityai/stable-diffusion-xl",
            prompt=f"Professional studio portrait of {desc}, wearing a black formal suit, neutral grey background, high resolution, photorealistic",
            n=1,
            size="1024x1024",
            response_format="b64_json"
        )
        
        # 3. Извлекаем данные и отправляем
        image_data = base64.b64decode(image_response.data[0].b64_json)
        photo_file = BufferedInputFile(image_data, filename="result.jpg")
        
        await bot.send_photo(message.chat.id, photo=photo_file, caption=f"✨ Готово (SDXL)!\nОписание: {desc}")
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        # Если SDXL не сработал по ID, попробуем через универсальный промпт
        await status.edit_text("⚠️ Ошибка платной модели. Проверьте баланс или попробуйте позже.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
