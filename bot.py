import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from google import genai
from google.genai import types
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

# Список моделей для перебора (от лучшей к самой доступной)
MODEL_VARIANTS = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-8b']

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🍌 Nano Banana на связи! Пытаюсь пробиться через квоты Google...\nПришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (подбираю свободную модель)...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_stream = await bot.download_file(file.file_path)
    image_bytes = photo_stream.getvalue()
    
    person_desc = None
    
    # Пытаемся достучаться хоть до какой-то модели
    for model_name in MODEL_VARIANTS:
        try:
            logging.info(f"Пробую модель: {model_name}")
            vision_response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                    'Describe face and hair very briefly. Max 10 words.'
                ]
            )
            person_desc = vision_response.text.strip()
            if person_desc:
                logging.info(f"✅ Успех с моделью {model_name}")
                break
        except Exception as e:
            logging.warning(f"❌ {model_name} отказала: {str(e)[:50]}")
            continue

    if not person_desc:
        await status_msg.edit_text("❌ Все модели Google сейчас недоступны (Quota 0). Попробуйте через 10-15 минут.")
        return

    await status_msg.edit_text("⌛ Шаг 2: Генерация портрета (Imagen 3)...")

    try:
        # Промпт для Imagen
        prompt = (f"A professional memorial portrait of {person_desc}, "
                  f"wearing a formal grey shirt, neutral studio grey background, "
                  f"black diagonal mourning ribbon in bottom right corner, 8k resolution.")

        image_response = client.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg"
            )
        )
        
        generated_image_bytes = image_response.generated_images[0].image.image_bytes
        photo_file = BufferedInputFile(generated_image_bytes, filename="retouch.jpg")
        
        await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка Imagen: {e}")
        await message.answer("❌ Анализ прошел, но Imagen 3 пока не дает рисовать. Попробуйте чуть позже, Google активирует квоты постепенно.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
