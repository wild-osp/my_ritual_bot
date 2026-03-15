import os
import asyncio
import logging
import base64
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

# Список актуальных ID моделей для генерации (в порядке приоритета)
IMAGE_MODELS = [
    "black-forest-labs/flux-schnell", 
    "openai/dall-e-3",
    "stabilityai/stable-diffusion-xl"
]

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🚀 **Premium Nano Banana v18.0**\nСистема авто-подбора модели активна. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Шаг 1: Распознавание лиц...")
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        # Анализ Gemini (работает стабильно)
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Detailed face description: age, features, expression. Max 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        
        # ШАГ 2: ЦИКЛ ПЕРЕБОРА МОДЕЛЕЙ
        generated_url = None
        for model_id in IMAGE_MODELS:
            try:
                await status.edit_text(f"🎨 Пробую модель: {model_id.split('/')[-1]}...")
                image_gen = await client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": f"Professional studio memorial portrait of {desc}, formal black suit, neutral grey background, 8k"}]
                )
                
                res_text = image_gen.choices[0].message.content.strip()
                urls = re.findall(r'(https?://[^\s)\]]+)', res_text)
                if urls:
                    generated_url = urls[0]
                    break # Успех! Выходим из цикла
            except Exception as e:
                logging.warning(f"Модель {model_id} не ответила: {e}")
                continue # Пробуем следующую модель из списка

        if generated_url:
            await bot.send_photo(message.chat.id, photo=URLInputFile(generated_url), caption="✨ Готово! (Платная генерация)")
            await status.delete()
        else:
            # Если ВСЕ платные модели выдали ошибку 400, значит у OpenRouter глобальный затык с картинками
            # Включаем экстренный резерв через независимый шлюз
            await status.edit_text("⚠️ Платные модели OpenRouter недоступны. Использую аварийный канал...")
            emergency_url = f"https://image.pollinations.ai/prompt/portrait%20{desc.replace(' ', '%20')}%20black%20suit?nologo=true"
            await bot.send_photo(message.chat.id, photo=URLInputFile(emergency_url), caption="✨ Готово! (Аварийный канал)")
            await status.delete()

    except Exception as e:
        logging.error(f"Global Error: {e}")
        await message.answer(f"❌ Системная ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
