import os
import asyncio
import logging
import base64
import urllib.parse
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana готов! Пришлите фото (полностью бесплатно).")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ фото (бесплатные модели)...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    # Список БЕСПЛАТНЫХ моделей на OpenRouter
    free_models = [
        "google/gemini-2.0-flash-001", 
        "google/gemini-flash-1.5-8b",
        "meta-llama/llama-3.2-11b-vision-instruct:free"
    ]
    
    person_desc = None
    for model_id in free_models:
        try:
            logging.info(f"Пробую бесплатную модель: {model_id}")
            analysis = await client.chat.completions.create(
                model=model_id,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this person's face very briefly for a portrait. Max 30 words."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }],
                timeout=20.0
            )
            person_desc = analysis.choices[0].message.content
            if person_desc:
                break
        except Exception as e:
            logging.warning(f"Модель {model_id} не сработала: {e}")
            continue

    if not person_desc:
        await status_msg.edit_text("❌ Не удалось проанализировать фото через бесплатные модели. Проверьте ключ OpenRouter.")
        return

    try:
        await status_msg.edit_text("⌛ Шаг 2: Генерация портрета (Pollinations AI)...")

        # Формируем промпт для рисования
        prompt = (f"Professional studio memorial portrait of {person_desc}, "
                  f"wearing formal grey shirt, neutral grey background, "
                  f"black mourning ribbon in bottom right corner, highly detailed, 8k.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        # Используем модель FLUX (самая современная бесплатная)
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={message.message_id}&model=flux"

        await bot.send_photo(
            message.chat.id, 
            photo=image_url, 
            caption="✨ Ретушь выполнена!\n\nЕсли лицо не похоже, попробуйте еще раз с более четким исходным фото."
        )
        await status_msg.delete()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка на шаге генерации: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
